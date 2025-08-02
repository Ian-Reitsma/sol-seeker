"""Feature vector management."""
from pathlib import Path
from typing import Dict, List

import numpy as np

from solbot.schema import Event, EventKind

# load feature registry
_FEATURE_CFG = Path(__file__).resolve().parents[3] / "features.yaml"
_YAML = {}  # type: Dict
if _FEATURE_CFG.exists():
    import yaml

    with open(_FEATURE_CFG, "r") as fh:
        _YAML = yaml.safe_load(fh)

FEATURES: List[Dict] = _YAML.get("features", [])
DIM = len(FEATURES) if FEATURES else 256


class FeatureVector:
    """Maintain a 256-dimensional feature tensor with decay and Welford stats."""

    def __init__(self, buffer_size: int = 10) -> None:
        self.x = np.zeros(DIM, dtype=np.float64)
        self.count = np.zeros(DIM, dtype=np.int64)
        self.mean = np.zeros(DIM, dtype=np.float64)
        self.M2 = np.zeros(DIM, dtype=np.float64)
        self.buffer = [np.zeros(DIM, dtype=np.float64) for _ in range(buffer_size)]
        self._buf_idx = 0

    def update(self, event: Event) -> None:
        """Update features based on event type."""
        if event.kind == EventKind.SWAP:
            idx = [0, 1]
            deltas = [event.amount_in, event.amount_in]
        elif event.kind == EventKind.ADD_LIQUIDITY:
            idx = [2]
            deltas = [event.reserve_a + event.reserve_b]
        elif event.kind == EventKind.REMOVE_LIQUIDITY:
            idx = [3]
            deltas = [event.reserve_a + event.reserve_b]
        elif event.kind == EventKind.MINT:
            idx = [4]
            deltas = [event.amount_out]
        else:
            return

        for i, d in zip(idx, deltas):
            new_val = self.x[i] + d
            self.x[i] = new_val
            self._welford(i, new_val)

    def decay(self, lam: float = 0.995) -> None:
        self.x *= lam

    def step(self) -> np.ndarray:
        """Decay and publish normalized snapshot."""
        self.decay()
        return self.snapshot()

    def _welford(self, idx: int, value: float) -> None:
        self.count[idx] += 1
        delta = value - self.mean[idx]
        self.mean[idx] += delta / self.count[idx]
        self.M2[idx] += delta * (value - self.mean[idx])

    def normalized(self) -> np.ndarray:
        std = np.sqrt(self.M2 / np.maximum(self.count, 1))
        return (self.x - self.mean) / (std + 1e-6)

    def snapshot(self) -> np.ndarray:
        vec = self.normalized().copy()
        self.buffer[self._buf_idx] = vec
        self._buf_idx = (self._buf_idx + 1) % len(self.buffer)
        return vec
