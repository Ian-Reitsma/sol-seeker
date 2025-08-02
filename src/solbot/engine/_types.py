"""Public feature engine interface definitions."""

from __future__ import annotations

from typing import NewType, Protocol

import numpy as np

from solbot.schema import Event

FeatureVector = NewType("FeatureVector", np.ndarray)  # shape=(256,), dtype=float32


class FeatureEngine(Protocol):
    """Protocol for feature engines.

    Implementations must update internal state from events and expose a
    concatenated feature vector of length 256.  All arrays are expected to be
    ``np.float32`` for downstream compatibility.
    """

    def update(self, event: Event, slot: int) -> FeatureVector:
        """Update internal state with ``event`` for ``slot`` and return vector."""

    def snapshot(self) -> FeatureVector:
        """Return the current concatenated feature vector."""

    def reset(self) -> None:
        """Reset internal buffers and statistics."""
