import numpy as np
import pytest

from solbot.engine.features import PyFeatureEngine
from solbot.schema import Event, EventKind


def _mk_event(kind: EventKind, **kwargs) -> Event:
    return Event(kind=kind, ts=kwargs.get("ts", 0), amount_in=kwargs.get("amount_in", 0.0),
                 amount_out=kwargs.get("amount_out", 0.0), reserve_a=kwargs.get("reserve_a", 0.0),
                 reserve_b=kwargs.get("reserve_b", 0.0))


def test_f01_add_liquidity_updates():
    fe = PyFeatureEngine()
    ev = _mk_event(EventKind.ADD_LIQUIDITY, reserve_a=2, reserve_b=3)
    vec = fe.update(ev, slot=1)
    assert fe.curr[0] == 5
    assert np.isclose(fe.curr[1], np.log(5))
    assert vec.shape == (256,)
    assert vec.dtype == np.float32


def test_f02_swap_sequence_inter_arrival():
    fe = PyFeatureEngine()
    ts = 0
    for i in range(100):
        ts += 10
        ev = _mk_event(EventKind.SWAP, ts=ts, amount_in=1.0)
        fe.update(ev, slot=1)
    assert fe.curr[2] == 100.0
    assert fe.curr[3] == 100.0  # absolute accumulation
    assert fe.curr[4] == 100.0  # 1000/10 from last inter-arrival


def test_f03_welford_decay_converges():
    fe = PyFeatureEngine()
    for _ in range(10000):
        ev = _mk_event(EventKind.ADD_LIQUIDITY, reserve_a=5, reserve_b=5)
        fe.update(ev, slot=1)
    assert abs(fe.mean[0] - 10.0) < 0.1
    assert fe.var[0] < 1e-6


def test_f04_lag_rotation_integrity():
    fe = PyFeatureEngine()
    ev1 = _mk_event(EventKind.SWAP, amount_in=1.0)
    fe.update(ev1, slot=1)
    first_norm = fe.norm.copy()
    ev2 = _mk_event(EventKind.SWAP, amount_in=2.0)
    fe.update(ev2, slot=2)  # triggers rotation
    assert np.allclose(fe.prev1[:fe.dim], first_norm)


@pytest.mark.benchmark
def test_f05_update_latency_benchmark(benchmark):
    fe = PyFeatureEngine()
    ts = 0

    def run() -> None:
        nonlocal ts
        ts += 1
        ev = _mk_event(EventKind.SWAP, ts=ts, amount_in=1.0)
        fe.update(ev, slot=1)

    benchmark.pedantic(run, iterations=10000, rounds=1)
    stats = getattr(benchmark, "stats", None)
    if stats is None:
        pytest.skip("benchmark disabled")
    mean = stats.stats.mean
    assert mean * 1e6 < 80


def test_f06_snapshot_immutability():
    fe = PyFeatureEngine()
    ev = _mk_event(EventKind.SWAP, amount_in=1.0)
    fe.update(ev, slot=1)
    snap = fe.snapshot()
    snap_before = snap.copy()
    fe.update(_mk_event(EventKind.SWAP, amount_in=1.0), slot=1)
    assert np.array_equal(snap, snap_before)
    assert not np.shares_memory(snap, fe.snapshot())


def test_norm_decay_on_inactive_indices():
    fe = PyFeatureEngine()
    ev = _mk_event(EventKind.ADD_LIQUIDITY, reserve_a=5, reserve_b=5)
    fe.update(ev, slot=1)
    mu1, var1 = fe.mean[0], fe.var[0]
    # advance slot with unrelated event
    fe.update(_mk_event(EventKind.MINT, amount_out=1.0), slot=2)
    expected = -(mu1 * 0.995) / np.sqrt(var1 * 0.995 + 1e-8)
    assert np.isclose(fe.norm[0], expected, atol=1e-6)
    # advance many slots
    final_slot = 2
    for s in range(3, 10):
        fe.update(_mk_event(EventKind.MINT, amount_out=1.0), slot=s)
        final_slot = s
    delta = final_slot - 1
    expected_final = -(mu1 / np.sqrt(var1)) * np.sqrt(0.995 ** delta)
    assert np.isclose(fe.norm[0], expected_final, atol=1e-6)


def test_history_ring_buffer():
    fe = PyFeatureEngine()
    ev = _mk_event(EventKind.SWAP, amount_in=1.0)
    for _ in range(3):
        fe.update(ev, slot=1)
    hist = fe.history()
    assert len(hist) == 3
    assert hist[-1][0].kind == EventKind.SWAP


def test_pubsub_queue_nonblocking():
    fe = PyFeatureEngine()
    q = fe.subscribe(maxsize=1)
    fe.update(_mk_event(EventKind.SWAP, amount_in=1.0), slot=1)
    assert not q.empty()
    first = q.get()
    fe.update(_mk_event(EventKind.SWAP, amount_in=2.0), slot=1)
    assert q.qsize() == 1
    latest = q.get()
    assert latest[2] != first[2]


def test_unsubscribe_removes_queue():
    fe = PyFeatureEngine()
    q = fe.subscribe()
    assert q in fe._subs
    fe.unsubscribe(q)
    assert q not in fe._subs
