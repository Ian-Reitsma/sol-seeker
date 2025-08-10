"""Solana WebSocket log streaming and event parsing utilities."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import random
from typing import AsyncIterator, Optional, Sequence

import websockets
from prometheus_client import Counter, Gauge

from rustcore import ParsedEvent, parse_log


QUEUE_DEPTH = Gauge(
    "log_queue_depth", "Log queue depth ratio", ["feed", "program_id"]
)
DROPPED_LOGS = Counter(
    "dropped_logs", "Dropped logs due to full queue", ["feed", "program_id"]
)


def reset_metrics(feed: str = "main", program_id: str = "none") -> None:
    """Reset Prometheus metrics for tests."""

    QUEUE_DEPTH.labels(feed, program_id).set(0)
    # Counter has no public setter; use internal value for test isolation
    DROPPED_LOGS.labels(feed, program_id)._value.set(0)


class LogStreamer:
    """Stream Solana program logs with automatic reconnect and backoff.

    Parameters
    ----------
    rpc_ws_url:
        WebSocket RPC endpoint.
    program_ids:
        Sequence of program ids whose logs should be subscribed to.
    queue_size:
        Maximum number of logs to buffer locally when the consumer is slower
        than the producer.  A large buffer prevents transient backpressure from
        dropping messages during bursts.
    """

    def __init__(
        self,
        rpc_ws_url: str = "wss://api.mainnet-beta.solana.com/",
        program_ids: Optional[Sequence[str]] = None,
        queue_size: int = 10000,
    ) -> None:
        self.rpc_ws_url = rpc_ws_url
        self.program_ids = list(program_ids or [])
        self._queue_size = queue_size

    async def _connect(self) -> AsyncIterator[str]:
        async with websockets.connect(self.rpc_ws_url) as ws:
            for i, pid in enumerate(self.program_ids, start=1):
                msg = {
                    "jsonrpc": "2.0",
                    "id": i,
                    "method": "logsSubscribe",
                    "params": [{"mentions": [pid]}, {"commitment": "confirmed"}],
                }
                await ws.send(json.dumps(msg))
            async for raw in ws:
                data = json.loads(raw)
                if "params" not in data or "result" not in data["params"]:
                    continue
                value = data["params"]["result"].get("value", {})
                for log in value.get("logs", []):
                    yield log

    async def subscribe(self) -> AsyncIterator[str]:
        """Yield log strings with backpressure metrics and jittered reconnect."""

        queue: asyncio.Queue[str] = asyncio.Queue(self._queue_size)
        program_label = self.program_ids[0] if self.program_ids else "none"
        depth_metric = QUEUE_DEPTH.labels("main", program_label)
        drop_metric = DROPPED_LOGS.labels("main", program_label)

        stop_event = asyncio.Event()

        async def producer() -> None:
            backoff = 1.0
            above_since: Optional[float] = None
            loop = asyncio.get_running_loop()
            while not stop_event.is_set():
                try:
                    stable_start = loop.time()
                    async for log in self._connect():
                        try:
                            queue.put_nowait(log)
                        except asyncio.QueueFull:
                            drop_metric.inc()
                            logging.warning("log queue full; dropping log")
                            # Queue is at capacity; update metrics and check for
                            # sustained backpressure before yielding.
                            depth_metric.set(1.0)
                            if above_since is None:
                                above_since = loop.time()
                            elif loop.time() - above_since > 1.0:
                                logging.error("log queue depth >75%%; stopping stream")
                                stop_event.set()
                                return
                            # Yield to the event loop so other tasks can run.
                            # Without this the producer can spin aggressively when
                            # the queue is full, starving consumers and tests.
                            await asyncio.sleep(0)
                            continue
                        depth = queue.qsize() / self._queue_size
                        depth_metric.set(depth)
                        if depth > 0.75:
                            if above_since is None:
                                above_since = loop.time()
                            elif loop.time() - above_since > 1.0:
                                logging.error("log queue depth >75%%; stopping stream")
                                stop_event.set()
                                return
                        else:
                            above_since = None
                        if loop.time() - stable_start > 10.0:
                            backoff = 1.0
                    backoff = 1.0
                except Exception as exc:  # pragma: no cover - network dependent
                    logging.warning(
                        "log stream error: %s; reconnecting in %.1fs", exc, backoff
                    )
                    await asyncio.sleep(random.uniform(0, backoff))
                    backoff = min(backoff * 2.0, 32.0)

        task = asyncio.create_task(producer())
        try:
            while not stop_event.is_set():
                yield await queue.get()
            raise RuntimeError("log stream halted due to backpressure")
        finally:
            stop_event.set()
            task.cancel()
            # Cancel the producer task and wait for it to exit. In Python 3.11+
            # asyncio.CancelledError is no longer a subclass of Exception, so
            # we explicitly suppress it alongside other exceptions.
            with contextlib.suppress(Exception, asyncio.CancelledError):
                await task
            # Drain any remaining logs to avoid stale metrics on restart
            while not queue.empty():
                queue.get_nowait()


def _parsed_to_event(pe: ParsedEvent):
    from solbot.schema import Event, EventKind

    kind = pe.kind.lower()
    if kind == "swap":
        return Event(
            ts=pe.ts,
            kind=EventKind.SWAP,
            amount_in=pe.amount_in,
            amount_out=pe.amount_out,
        )
    if kind == "add_liquidity":
        return Event(
            ts=pe.ts,
            kind=EventKind.ADD_LIQUIDITY,
            reserve_a=pe.reserve_a,
            reserve_b=pe.reserve_b,
        )
    if kind == "remove_liquidity":
        return Event(
            ts=pe.ts,
            kind=EventKind.REMOVE_LIQUIDITY,
            reserve_a=pe.reserve_a,
            reserve_b=pe.reserve_b,
        )
    if kind == "mint":
        return Event(ts=pe.ts, kind=EventKind.MINT, amount_out=pe.amount_out)
    return Event(ts=pe.ts, kind=EventKind.NONE)


class EventStream:
    """Wrapper yielding parsed :class:`solbot.schema.Event` objects."""

    def __init__(
        self,
        rpc_ws_url: str = "wss://api.mainnet-beta.solana.com/",
        program_ids: Optional[Sequence[str]] = None,
        logs: Optional[Sequence[str]] = None,
    ) -> None:
        self.rpc_ws_url = rpc_ws_url
        self._program_ids = program_ids or []
        self._logs = logs
        self._streamer: Optional[LogStreamer] = None

    async def __aiter__(self) -> AsyncIterator["Event"]:
        if self._logs is not None:
            for log in self._logs:
                parsed = parse_log(log)
                if parsed is not None:
                    logging.debug("raw_log=%s", log)
                    ev = _parsed_to_event(parsed)
                    logging.debug("parsed_event=%s", ev)
                    yield ev
            return

        if self._streamer is None:
            self._streamer = LogStreamer(self.rpc_ws_url, self._program_ids)

        queue: asyncio.Queue[str] = asyncio.Queue(10000)

        async def producer() -> None:
            assert self._streamer is not None
            async for log in self._streamer.subscribe():
                await queue.put(log)

        asyncio.create_task(producer())
        loop = asyncio.get_running_loop()
        while True:
            log = await queue.get()
            parsed = await loop.run_in_executor(None, parse_log, log)
            if parsed is not None:
                logging.debug("raw_log=%s", log)
                ev = _parsed_to_event(parsed)
                logging.debug("parsed_event=%s", ev)
                yield ev

    def stream_events(self):
        """Synchronous wrapper yielding events."""

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        queue: asyncio.Queue["Event"] = asyncio.Queue()

        async def run() -> None:
            async for ev in self:
                await queue.put(ev)

        task = loop.create_task(run())
        try:
            while True:
                ev = loop.run_until_complete(queue.get())
                yield ev
        finally:
            task.cancel()
            with contextlib.suppress(Exception):
                loop.run_until_complete(task)
            loop.close()

