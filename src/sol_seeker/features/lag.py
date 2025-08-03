"""Lag stack utilities for pure Python fallbacks.

Currently unused but kept for API parity with the Rust implementation."""
from __future__ import annotations

from collections import deque
from typing import Iterable, Deque


class LagStack:
    """Simple three-element ring buffer for feature vectors."""

    def __init__(self, width: int) -> None:
        self._width = width
        self._buf: Deque[list[float]] = deque([[0.0] * width for _ in range(3)], maxlen=3)

    def rotate(self) -> None:
        self._buf.appendleft([0.0] * self._width)

    def view(self) -> list[float]:
        out: list[float] = []
        for arr in self._buf:
            out.extend(arr)
        return out
