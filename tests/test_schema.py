from solbot.schema import PositionState, SCHEMA_HASH
from solbot.persistence import DAL
import tempfile


def test_round_trip():
    pos = PositionState(token="SOL", qty=1.0, cost=10.0, unrealized=0.0)
    tmp = tempfile.NamedTemporaryFile(delete=False)
    dal = DAL(tmp.name)
    dal.upsert_position(pos)
    loaded = dal.load_positions()["SOL"]
    assert pos.SerializeToString() == loaded.SerializeToString()
    assert dal.get_meta("schema_hash") == SCHEMA_HASH
