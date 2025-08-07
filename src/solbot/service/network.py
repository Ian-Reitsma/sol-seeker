"""Background polling of network metrics."""

from __future__ import annotations

import asyncio
from typing import Callable, Tuple

from ..engine.features import PyFeatureEngine
from ..solana import fetch_volume_and_fees

Fetcher = Callable[[str], Tuple[float, float]]


async def _poll_loop(
    features: PyFeatureEngine,
    rpc_http_url: str,
    interval: float,
    fetcher: Fetcher,
) -> None:
    slot = 0
    while True:
        try:
            tps, fee = fetcher(rpc_http_url)
            slot += 1
            features.update_network_metrics(tps, fee, slot)
        except Exception:
            pass
        await asyncio.sleep(interval)


def start_network_poller(
    features: PyFeatureEngine,
    rpc_http_url: str,
    interval: float = 60.0,
    fetcher: Fetcher = fetch_volume_and_fees,
) -> asyncio.Task:
    """Start background task updating network metrics."""
    loop = asyncio.get_running_loop()
    return loop.create_task(_poll_loop(features, rpc_http_url, interval, fetcher))
