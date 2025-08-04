import numpy as np
from sol_seeker.features.engine import FeatureEngine
from sol_seeker.features.spec import FEATURES

def welford_py(values, lam):
    mean = 0.0
    var = 0.0
    for x in values:
        delta = x - mean
        mean += (1 - lam) * delta
        var = lam * (var + (1 - lam) * delta * delta)
    return mean, var


def test_spec_unique_indices():
    assert len(FEATURES) == 256
    assert len({m.index for m in FEATURES.values()}) == 256


def test_determinism():
    events = [
        {"tag": "Swap", "amount": 1.0, "timestamp_ms": 1},
        {"tag": "Liquidity", "delta": 5.0, "prev": 100.0},
        {"tag": "Swap", "amount": -0.5, "timestamp_ms": 2},
    ]

    fe1 = FeatureEngine()
    for e in events:
        fe1.push_event(e)
    out1 = bytes(fe1.on_slot_end(1))

    fe2 = FeatureEngine()
    for e in events:
        fe2.push_event(e)
    out2 = bytes(fe2.on_slot_end(1))

    assert out1 == out2


def test_welford_accuracy():
    lam = 0.995
    rng = np.random.default_rng(0)
    vals = rng.standard_normal(1000)

    fe = FeatureEngine()
    for i, v in enumerate(vals):
        fe.push_event({"tag": "Swap", "amount": float(v), "timestamp_ms": i})

    mean, var = fe.stats("of_signed_volume")
    ref_mean, ref_var = welford_py(vals, lam)
    assert np.isclose(mean, ref_mean, atol=1e-6)
    assert np.isclose(var, ref_var, atol=1e-6)
