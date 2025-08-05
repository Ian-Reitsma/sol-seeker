"""Pure Python fallback for the `rustcore` extension.

This module provides a minimal implementation of the APIs exposed by the real
Rust extension used in production.  It implements the small subset required by
our unit tests so that the package can be exercised without compiling the
native module.  The implementation intentionally mirrors the behaviour of the
Rust code but favours clarity over absolute performance.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import json
import numpy as np

# ---------------------------------------------------------------------------
# Parsed log objects
# ---------------------------------------------------------------------------

@dataclass
class ParsedEvent:
    """Structured representation of a parsed log entry."""

    ts: int
    kind: str
    amount_in: float
    amount_out: float
    reserve_a: float
    reserve_b: float


def parse_log(log: str) -> Optional[ParsedEvent]:
    """Parse a JSON log string.

    The real implementation lives in the Rust extension; this version simply
    deserialises JSON and populates default values for missing fields.  Invalid
    JSON returns ``None`` rather than raising an exception.
    """
    try:
        raw = json.loads(log)
    except Exception:
        return None

    return ParsedEvent(
        ts=int(raw.get("ts", 0) or 0),
        kind=str(raw.get("type", "")),
        amount_in=float(raw.get("amount_in", 0.0) or 0.0),
        amount_out=float(raw.get("amount_out", 0.0) or 0.0),
        reserve_a=float(raw.get("reserve_a", 0.0) or 0.0),
        reserve_b=float(raw.get("reserve_b", 0.0) or 0.0),
    )

# ---------------------------------------------------------------------------
# Event and feature engine
# ---------------------------------------------------------------------------

@dataclass
class PyEvent:
    """Event container matching the Rust ``PyEvent`` class."""

    tag: str
    delta: Optional[float] = None
    prev: Optional[float] = None
    amount: Optional[float] = None
    timestamp_ms: Optional[int] = None


class FeatureEngine:
    """Light‑weight Python implementation of the Rust feature engine."""

    LAMBDA = 0.995
    IDX_LIQ_DELTA_ABS = 0
    IDX_LIQ_DELTA_RATIO = 1
    IDX_OF_SIGNED_VOL = 64
    IDX_OF_TRADE_COUNT = 65
    IDX_OF_IA_TIME_MS = 66

    def __init__(self) -> None:
        self.data = np.zeros(256, dtype=np.float32)
        self.means = np.zeros(256, dtype=np.float64)
        self.vars = np.zeros(256, dtype=np.float64)
        self.lag1 = np.zeros(256, dtype=np.float32)
        self.lag2 = np.zeros(256, dtype=np.float32)
        self.out = np.zeros(256 * 3, dtype=np.float32)
        self.last_swap_ts: Optional[int] = None

    # ------------------------------ internal helpers ---------------------
    def _update(self, idx: int, value: float) -> None:
        mu_prev = self.means[idx]
        var_prev = self.vars[idx]
        lam = self.LAMBDA
        mu = lam * mu_prev + (1.0 - lam) * value
        var = lam * (var_prev + (1.0 - lam) * (value - mu_prev) ** 2)
        self.means[idx] = mu
        self.vars[idx] = var

    # ------------------------------ public API ---------------------------
    def push_event(self, evt: PyEvent) -> None:
        tag = evt.tag
        if tag == "Liquidity":
            if evt.delta is None or evt.prev is None:
                raise ValueError("missing delta or prev for Liquidity event")
            delta = evt.delta
            prev = evt.prev
            abs_delta = abs(delta)
            self.data[self.IDX_LIQ_DELTA_ABS] += abs_delta
            self._update(self.IDX_LIQ_DELTA_ABS, abs_delta)
            ratio = delta / prev if abs(prev) > 1e-12 else 0.0
            self.data[self.IDX_LIQ_DELTA_RATIO] += ratio
            self._update(self.IDX_LIQ_DELTA_RATIO, ratio)
        elif tag == "Swap":
            if evt.amount is None or evt.timestamp_ms is None:
                raise ValueError("missing amount or timestamp for Swap event")
            amt = evt.amount
            ts = evt.timestamp_ms
            self.data[self.IDX_OF_SIGNED_VOL] += amt
            self._update(self.IDX_OF_SIGNED_VOL, amt)
            self.data[self.IDX_OF_TRADE_COUNT] += 1.0
            self._update(self.IDX_OF_TRADE_COUNT, 1.0)
            if self.last_swap_ts is not None:
                dt = ts - self.last_swap_ts
                self.data[self.IDX_OF_IA_TIME_MS] = float(dt)
            else:
                dt = 0.0
            self.last_swap_ts = ts
            self._update(self.IDX_OF_IA_TIME_MS, float(dt))
        else:
            raise ValueError(f"unknown event tag: {tag}")

    def on_slot_end(self, slot: int) -> np.ndarray:  # slot arg kept for parity
        self.out[:256] = self.data
        self.out[256:512] = self.lag1
        self.out[512:] = self.lag2
        # rotate lag buffers
        self.lag2[:] = self.lag1
        self.lag1[:] = self.data
        self.data.fill(0.0)
        return self.out

    def get_stats(self, idx: int) -> tuple[float, float]:
        return float(self.means[idx]), float(self.vars[idx])


__all__ = [
    "ParsedEvent",
    "parse_log",
    "PyEvent",
    "FeatureEngine",
]
