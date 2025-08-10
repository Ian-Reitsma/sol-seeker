from __future__ import annotations

import asyncio
from typing import List


class BootstrapCoordinator:
    def __init__(self) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        self.ready = asyncio.Event()
        self.progress = 0

    async def run(self, assets, oracle) -> None:
        symbols = assets.refresh()
        step = 100 // max(len(symbols), 1)
        for sym in symbols[:5]:
            try:
                await oracle.price(sym.get("symbol"))
            except Exception:
                pass
            self.progress += step
        self.progress = 100
        self.ready.set()

    def is_ready(self) -> bool:
        return self.ready.is_set()

    def status(self) -> dict:
        state = "READY" if self.is_ready() else "BOOTSTRAPPING"
        return {"state": state, "progress": self.progress}
