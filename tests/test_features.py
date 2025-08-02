from solbot.engine import FeatureVector
from solbot.schema import Event, EventKind


def test_feature_update():
    fv = FeatureVector()
    ev = Event(ts=0, kind=EventKind.SWAP, amount_in=10)
    fv.update(ev)
    fv.decay(1.0)
    assert fv.x[0] > 0
