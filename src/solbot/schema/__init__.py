"""Schema bindings without runtime proto compilation.

Historically the project generated ``event_pb2`` at import time using the
``protoc`` binary.  The execution environment for the kata does not ship with
that compiler which caused imports of :mod:`solbot.schema` to fail.  The module
now ships with a lightweight ``event_pb2`` implementation and simply loads it
directly.
"""

from __future__ import annotations

from pathlib import Path
import hashlib

from . import position_pb2, event_pb2

ROOT = Path(__file__).resolve().parents[3]
POSITION_PROTO = Path(__file__).with_name("position.proto")
EVENT_PROTO = ROOT / "proto" / "event.proto"

SCHEMA_HASH = hashlib.sha256(
    POSITION_PROTO.read_bytes() + EVENT_PROTO.read_bytes()
).hexdigest()

PositionState = position_pb2.PositionState
PnLState = position_pb2.PnLState
Event = event_pb2.Event
EventKind = event_pb2.EventKind

__all__ = ["PositionState", "PnLState", "Event", "EventKind", "SCHEMA_HASH"]
