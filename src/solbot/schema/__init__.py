"""Schema bindings with runtime proto generation."""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path
import hashlib

from . import position_pb2

ROOT = Path(__file__).resolve().parents[3]
POSITION_PROTO = Path(__file__).with_name("position.proto")
EVENT_PROTO = ROOT / "proto" / "event.proto"


def _ensure_event_pb2() -> None:
    out = Path(__file__).with_name("event_pb2.py")
    if not out.exists() or out.stat().st_mtime < EVENT_PROTO.stat().st_mtime:
        subprocess.check_call(
            [
                "protoc",
                f"--proto_path={EVENT_PROTO.parent}",
                f"--python_out={out.parent}",
                EVENT_PROTO.name,
            ]
        )


_ensure_event_pb2()
event_pb2 = importlib.import_module(f"{__name__}.event_pb2")

SCHEMA_HASH = hashlib.sha256(
    POSITION_PROTO.read_bytes() + EVENT_PROTO.read_bytes()
).hexdigest()

PositionState = position_pb2.PositionState
PnLState = position_pb2.PnLState
Event = event_pb2.Event
EventKind = event_pb2.EventKind

__all__ = ["PositionState", "PnLState", "Event", "EventKind", "SCHEMA_HASH"]
