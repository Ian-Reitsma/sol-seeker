from __future__ import annotations

"""Lightweight stand-in for generated ``event_pb2`` module.

The original project generated protobuf bindings for ``event.proto`` at
runtime using ``protoc``.  The execution environment for the kata does not
provide the compiler which caused imports of :mod:`solbot.schema` to fail.
This module provides minimal ``Event`` and ``EventKind`` implementations
sufficient for the tests without requiring the external dependency.
"""

from dataclasses import dataclass
from enum import IntEnum


class EventKind(IntEnum):
    """Enumeration of supported event types."""

    NONE = 0
    SWAP = 1
    ADD_LIQUIDITY = 2
    REMOVE_LIQUIDITY = 3
    MINT = 4


@dataclass
class Event:
    """Simplified protobuf-style event message."""

    ts: int = 0
    kind: EventKind = EventKind.NONE
    amount_in: float = 0.0
    amount_out: float = 0.0
    reserve_a: float = 0.0
    reserve_b: float = 0.0
    fee: float = 0.0
    volume: float = 0.0
