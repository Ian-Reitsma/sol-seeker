from pathlib import Path
import hashlib

from . import position_pb2

PROTO_PATH = Path(__file__).with_name('position.proto')
SCHEMA_HASH = hashlib.sha256(PROTO_PATH.read_bytes()).hexdigest()

PositionState = position_pb2.PositionState
PnLState = position_pb2.PnLState

__all__ = ["PositionState", "PnLState", "SCHEMA_HASH"]
