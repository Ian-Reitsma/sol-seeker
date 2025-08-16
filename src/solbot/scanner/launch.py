import asyncio
import contextlib
from typing import Optional


class TokenLaunchScanner:
    """Background task that watches for new token launches.

    This is a lightweight placeholder implementation used for integration
    testing. The real scanner would connect to on-chain sources and emit
    events whenever a new memecoin launches.
    """

    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None

    async def _run(self) -> None:
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    def start(self) -> None:
        if self._task is None or self._task.done():
            loop = asyncio.get_event_loop()
            self._task = loop.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
