"""Python shim around the Rust feature engine."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Any, Tuple

from .spec import idx

try:  # Attempt to import the compiled rustcore extension.
    import rustcore  # type: ignore
except Exception as exc:  # pragma: no cover - import error surface early
    raise ImportError(
        "rustcore extension module not built. Run `maturin build` and `pip install` the wheel first."
    ) from exc


@dataclass
class PyEvent:
    """Typed event passed to :class:`FeatureEngine`.

    This reduces runtime key lookups compared to raw ``dict`` usage.
    ``None`` fields are ignored by the Rust layer.
    """

    tag: str
    delta: float | None = None
    prev: float | None = None
    amount: float | None = None
    timestamp_ms: int | None = None


class FeatureEngine:
    """High level interface used by the Python event pipeline.

    All heavy lifting occurs inside the compiled Rust module. The returned
    memoryview from :meth:`on_slot_end` is valid until the next slot boundary
    rotation.
    """

    def __init__(self) -> None:
        self._core = rustcore.FeatureEngine()

    def push_event(self, evt: PyEvent | Dict[str, Any]) -> None:
        """Push a parsed event into the engine.

        ``evt`` may be a ``PyEvent`` or raw ``dict``; in both cases a mapping
        with the expected keys is forwarded to the Rust core.
        """

        if isinstance(evt, PyEvent):
            self._core.push_event(asdict(evt))
        else:
            self._core.push_event(evt)

    def on_slot_end(self, slot: int) -> memoryview:
        """Rotate lag buffers and return a view of the feature stack.

        The resulting memoryview spans 768 ``float32`` values representing
        ``[t0 | t1 | t2]``. The view is invalidated on the next call.
        """

        arr = self._core.on_slot_end(slot)
        return memoryview(arr)

    def stats(self, key: str) -> Tuple[float, float]:
        """Return (mean, variance) for a feature key."""

        return self._core.get_stats(idx(key))
