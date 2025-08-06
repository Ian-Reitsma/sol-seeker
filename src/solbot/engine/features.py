"""Feature vector management with decay and lag stack.

This module implements a small feature engine in pure Python that mirrors the
contract expected by downstream modules.  It maintains three 256 length buffers
(`fv_curr`, `fv_prev1`, `fv_prev2`) and exposes a concatenated view updated on
every event.  Online mean and variance statistics are kept per-dimension using
an exponentially decaying variant of Welford's algorithm.  Only touched indices
are updated to keep the per-event cost ``O(k)`` where ``k`` is the number of
affected dimensions.

The implementation favours clarity over ultimate performance but avoids
per-event allocations so it can act as a CI fall-back until the Rust version
lands.
"""

from __future__ import annotations

import contextlib
import logging
import os
import time
import queue
from collections import deque
from pathlib import Path
from typing import Deque, Dict, List, Optional, Tuple

import numpy as np
from prometheus_client import Gauge, Summary

from solbot.schema import Event, EventKind
from ._types import FeatureEngine, FeatureVector


# ----------------------------------------------------------------------------
# Feature configuration
# ----------------------------------------------------------------------------

SCHEMA_VERSION = 0x01
_FEATURE_CFG = Path(__file__).resolve().parents[3] / "features.yaml"
_YAML: Dict = {}
if _FEATURE_CFG.exists():
    import yaml

    with open(_FEATURE_CFG, "r", encoding="utf-8") as fh:
        _YAML = yaml.safe_load(fh)

if _YAML.get("version") != SCHEMA_VERSION:
    raise ValueError("feature schema version mismatch")

FEATURES: List[Dict] = _YAML.get("features", [])
# we touch indices up to 5, ensure base dim is at least 6 so the vector is
# forward compatible with the spec's initial 64 dimensional subset
BASE_DIM = max(len(FEATURES), 6)
TOTAL_DIM = 256
LAM = 0.995
EPS = 1e-8

_TRACE = os.getenv("FEATURE_TRACE", "0") == "1"
TRACE_BUFFER = deque(maxlen=100) if _TRACE else None
HISTORY_SIZE = int(os.getenv("FEATURE_HISTORY", "1000"))
fv_nan_count = Gauge("fv_nan_count", "number of NaNs encountered in normalization")
update_latency_us = Summary(
    "feature_update_latency_us", "feature update latency in microseconds"
)


class PyFeatureEngine(FeatureEngine):
    """Pure Python implementation of :class:`FeatureEngine`.

    .. note:: Not thread-safe; all methods must be invoked from a single
       thread.

    The engine maintains three lagged feature vectors and returns a concatenated
    view of length ``TOTAL_DIM`` on every update.  ``update`` returns a view
    backed by an internal buffer which remains valid only until the next
    ``update`` call.
    """

    def __init__(self) -> None:
        self.dim = BASE_DIM
        self.curr = np.zeros(self.dim, dtype=np.float32)
        self.prev1 = np.zeros(self.dim, dtype=np.float32)
        self.prev2 = np.zeros(self.dim, dtype=np.float32)
        self.mean = np.zeros(self.dim, dtype=np.float32)
        self.var = np.full(self.dim, 1e-4, dtype=np.float32)
        self.norm = np.zeros(self.dim, dtype=np.float32)
        self.out = np.zeros(TOTAL_DIM, dtype=np.float32)
        self.last_touched = np.zeros(self.dim, dtype=np.int64)
        self._decay_slot = -1
        self._slot: Optional[int] = None
        self._last_ts: Optional[int] = None
        self._cum_liq = 0.0
        self._history: Deque[Tuple[Event, np.ndarray]] = deque(maxlen=HISTORY_SIZE)
        self._subs: List["queue.Queue[Tuple[Event, np.ndarray]]"] = []

    # ------------------------------------------------------------------
    # Update routines
    # ------------------------------------------------------------------
    def update(self, event: Event, slot: int) -> FeatureVector:
        """Apply ``event`` for ``slot`` and return the feature vector."""
        start = time.perf_counter()
        if self._slot is None:
            self._slot = slot
        elif slot != self._slot:
            self._rotate(slot)
            self._slot = slot

        if self._decay_slot != slot:
            self._decay_inactive(slot)
            self._decay_slot = slot

        kind = event.kind
        if kind == EventKind.ADD_LIQUIDITY:
            delta = event.reserve_a + event.reserve_b
            self._cum_liq += delta
            self._update_idx(0, delta, slot)
            self._update_idx(1, np.log(abs(self._cum_liq) + EPS), slot)
        elif kind == EventKind.REMOVE_LIQUIDITY:
            delta = -(event.reserve_a + event.reserve_b)
            self._cum_liq += delta
            self._update_idx(0, delta, slot)
            self._update_idx(1, np.log(abs(self._cum_liq) + EPS), slot)
        elif kind == EventKind.SWAP:
            signed = event.amount_in - event.amount_out
            self._update_idx(2, self.curr[2] + signed, slot)
            self._update_idx(3, self.curr[3] + abs(signed), slot)
            if self._last_ts is not None:
                dt = max(event.ts - self._last_ts, 1)
                self._update_idx(4, 1000.0 / dt, slot)
            self._last_ts = event.ts
        elif kind == EventKind.MINT:
            self._update_idx(5, self.curr[5] + event.amount_out, slot)
        else:
            raise NotImplementedError(f"unknown EventKind: {kind}")

        vec = self._write_out()
        update_latency_us.observe((time.perf_counter() - start) * 1e6)
        if logging.getLogger(__name__).isEnabledFor(logging.DEBUG):
            logging.debug("event=%s", event)
            logging.debug("features=%s", vec[: self.dim])
        self._history.append((event, vec[: self.dim].copy()))
        for q in list(self._subs):
            try:
                q.put_nowait((event, vec.copy()))
            except queue.Full:
                with contextlib.suppress(Exception):
                    q.get_nowait()
                    q.put_nowait((event, vec.copy()))
        return vec

    def _update_idx(self, i: int, value: float, slot: int) -> None:
        self.curr[i] = value
        self.last_touched[i] = slot
        mu_prev = self.mean[i]
        var_prev = self.var[i]
        mu = LAM * mu_prev + (1 - LAM) * value
        var = LAM * (var_prev + (1 - LAM) * (value - mu_prev) ** 2)
        self.mean[i] = mu
        self.var[i] = var
        self.norm[i] = (value - mu) / (np.sqrt(var + EPS))
        if TRACE_BUFFER is not None:
            TRACE_BUFFER.append((i, value, self.norm[i]))

    # ------------------------------------------------------------------
    # Snapshot / output helpers
    # ------------------------------------------------------------------
    def _write_out(self) -> FeatureVector:
        span = self.dim
        nan_count = int(np.isnan(self.norm).sum())
        fv_nan_count.set(nan_count)
        np.nan_to_num(self.norm, copy=False)
        self.out[:span] = self.norm
        self.out[span : 2 * span] = self.prev1
        self.out[2 * span : 3 * span] = self.prev2
        if 3 * span < TOTAL_DIM:
            self.out[3 * span :] = 0.0
        return FeatureVector(self.out)

    def snapshot(self) -> FeatureVector:
        """Return a stable copy of the current concatenated feature vector."""
        self._decay_inactive(self._slot or 0)
        self._write_out()
        return FeatureVector(self.out.copy())

    def history(self) -> Tuple[Tuple[Event, np.ndarray], ...]:
        """Return a snapshot of the recent ``(event, features)`` ring buffer."""
        return tuple(self._history)

    # ------------------------------------------------------------------
    # Publish / subscribe
    # ------------------------------------------------------------------
    def subscribe(self, maxsize: int = 1) -> "queue.Queue[Tuple[Event, np.ndarray]]":
        """Return a queue receiving ``(event, features)`` tuples on every update.

        The queue is bounded and ``put_nowait`` is used to avoid blocking the
        ingestion loop.  If full, the oldest item is dropped before enqueueing
        the latest item.
        """

        q: "queue.Queue[Tuple[Event, np.ndarray]]" = queue.Queue(maxsize=maxsize)
        self._subs.append(q)
        return q

    def unsubscribe(self, q: "queue.Queue[Tuple[Event, np.ndarray]]") -> None:
        """Remove a previously subscribed queue if present."""
        with contextlib.suppress(ValueError):
            self._subs.remove(q)

    # ------------------------------------------------------------------
    # Slot rotation
    # ------------------------------------------------------------------
    def _rotate(self, slot: int) -> None:
        self.prev2[:] = self.prev1
        self.prev1[:] = self.norm
        self.curr.fill(0.0)
        self.norm.fill(0.0)
        self._cum_liq = 0.0
        self.last_touched.fill(slot - 1)

    def reset(self) -> None:
        self.curr.fill(0.0)
        self.prev1.fill(0.0)
        self.prev2.fill(0.0)
        self.mean.fill(0.0)
        self.var.fill(1e-4)
        self.norm.fill(0.0)
        self.out.fill(0.0)
        self._slot = None
        self._last_ts = None
        self._cum_liq = 0.0
        self.last_touched.fill(0)
        self._decay_slot = -1

    def _decay_inactive(self, slot: int) -> None:
        delta = slot - self.last_touched
        mask = delta > 0
        if np.any(mask):
            decay = np.power(LAM, delta[mask], dtype=np.float32)
            self.mean[mask] *= decay
            self.var[mask] *= decay
            self.norm[mask] = -self.mean[mask] / np.sqrt(self.var[mask] + EPS)
            self.curr[mask] = 0.0
            self.last_touched[mask] = slot
