import time
import types
import pytest

try:  # pragma: no cover - prefer the real plugin when available
    import pytest_benchmark.plugin  # type: ignore  # noqa: F401
except Exception:  # pragma: no cover - executed when plugin missing
    @pytest.fixture
    def benchmark():
        class DummyBenchmark:
            def __init__(self) -> None:
                self.stats = types.SimpleNamespace(stats=types.SimpleNamespace(mean=0.0))

            def pedantic(self, func, iterations: int = 1, rounds: int = 1) -> None:
                start = time.perf_counter()
                for _ in range(rounds):
                    for _ in range(iterations):
                        func()
                total = time.perf_counter() - start
                self.stats.stats.mean = total / (iterations * rounds)

        return DummyBenchmark()
