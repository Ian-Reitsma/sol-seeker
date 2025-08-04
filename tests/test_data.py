import asyncio
import logging

import pytest

from solbot.solana import data
from solbot.solana.data import DROPPED_LOGS, LogStreamer, reset_metrics
from solbot.schema import EventKind


def test_event_stream_from_logs():
    logs = ['{"type":"swap","ts":1,"amount_in":2.0,"amount_out":1.0}']
    stream = data.EventStream(logs=logs)
    ev = next(stream.stream_events())
    assert ev.kind == EventKind.SWAP
    assert ev.amount_in == 2.0


def test_event_stream_throughput():
    log = '{"type":"swap","ts":1,"amount_in":1.0,"amount_out":1.0}'
    logs = [log] * 5000
    stream = data.EventStream(logs=logs)
    import time

    gen = stream.stream_events()
    start = time.perf_counter()
    for _ in range(5000):
        next(gen)
    elapsed = time.perf_counter() - start
    gen.close()
    assert elapsed < 2.0


def test_log_streamer_metrics_and_backpressure():
    class Dummy(LogStreamer):
        async def _connect(self):
            for i in range(10):
                yield f"log{i}"

    reset_metrics()
    logging.getLogger().setLevel(logging.CRITICAL)

    async def run() -> float:
        streamer = Dummy(queue_size=2)
        agen = streamer.subscribe()
        await agen.__anext__()  # start producer
        await asyncio.sleep(0.1)
        drops = DROPPED_LOGS.labels("main", "none")._value.get()
        await agen.aclose()
        return drops

    drops = asyncio.run(run())
    assert drops > 0


def test_log_streamer_fail_fast():
    class Infinite(LogStreamer):
        async def _connect(self):
            while True:
                yield "log"

    async def run() -> None:
        streamer = Infinite(queue_size=4)
        agen = streamer.subscribe()
        await agen.__anext__()  # consume one
        await asyncio.sleep(1.5)
        with pytest.raises(RuntimeError):
            await agen.__anext__()
        await agen.aclose()

    asyncio.run(run())
