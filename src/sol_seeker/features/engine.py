"""Python shim around the Rust feature engine."""
from __future__ import annotations


from typing import Any, Dict, Tuple, Union
from .spec import idx

try:  # Attempt to import the compiled rustcore extension.
    import rustcore  # type: ignore
except Exception as exc:  # pragma: no cover - import error surface early
    raise ImportError(
        "rustcore extension module not built. Run `maturin build` and `pip install` the wheel first."
    ) from exc



class FeatureEngine:
    """High level interface used by the Python event pipeline.

    All heavy lifting occurs inside the compiled Rust module. The returned
    memoryview from :meth:`on_slot_end` is valid until the next slot boundary
    rotation.
    """

    def __init__(self) -> None:
        self._core = rustcore.FeatureEngine()

    def push_event(self, evt: Union[rustcore.PyEvent, Dict[str, Any]]) -> None:
        """Push a parsed event into the engine."""

        if isinstance(evt, rustcore.PyEvent):
            self._core.push_event(evt)
        else:
            self._core.push_event(rustcore.PyEvent(**evt))

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
