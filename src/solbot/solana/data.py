"""Solana WebSocket event streaming utilities."""

import asyncio
import json
import logging
import contextlib
import websockets


class SlotStreamer:
    """Minimal streamer that yields new slot numbers via WebSocket."""

    def __init__(self, rpc_ws_url: str = "wss://api.mainnet-beta.solana.com/"):
        self.rpc_ws_url = rpc_ws_url

    async def _subscribe_once(self):
        async with websockets.connect(self.rpc_ws_url) as ws:
            await ws.send(
                json.dumps({"jsonrpc": "2.0", "id": 1, "method": "slotSubscribe"})
            )
            async for msg in ws:
                data = json.loads(msg)
                if "params" in data and "result" in data["params"]:
                    yield data["params"]["result"]["slot"]

    async def _subscribe(self):
        """Yield slots indefinitely, reconnecting on error."""
        while True:
            try:
                async for slot in self._subscribe_once():
                    yield slot
            except Exception as exc:  # broad catch for connection errors
                logging.warning("slot stream error: %s; reconnecting", exc)
                await asyncio.sleep(1)

    def stream_slots(self):
        """Synchronous generator yielding slots."""
        # ``asyncio.get_event_loop`` is deprecated when no loop is running.
        # Create a dedicated loop for streaming slots to avoid warnings and
        # ensure compatibility with Python 3.12+.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        queue: asyncio.Queue[int] = asyncio.Queue()

        async def run():
            async for slot in self._subscribe():
                await queue.put(slot)

        task = loop.create_task(run())
        try:
            while True:
                slot = loop.run_until_complete(queue.get())
                yield slot
        finally:
            task.cancel()
            with contextlib.suppress(Exception):
                loop.run_until_complete(task)
            loop.close()

