import pytest
from rustcore import parse_log


@pytest.mark.benchmark
def test_parse_log_latency(benchmark):
    log = '{"type":"swap","ts":1,"amount_in":2.0,"amount_out":1.0}'

    def run():
        assert parse_log(log) is not None

    benchmark.pedantic(run, iterations=10000, rounds=1)
    stats = getattr(benchmark, "stats", None)
    if stats is None:
        pytest.skip("benchmark disabled")
    mean = stats.stats.mean
    assert mean * 1e6 < 100
