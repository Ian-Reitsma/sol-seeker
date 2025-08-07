"""Helpers for network volume and prioritization fees."""

from __future__ import annotations

from statistics import median
from typing import Tuple

from solana.rpc.api import Client


def fetch_volume_and_fees(rpc_http_url: str, window: int = 60) -> Tuple[float, float]:
    """Return recent transaction volume and median prioritization fee.

    Parameters
    ----------
    rpc_http_url:
        HTTP RPC endpoint.
    window:
        Number of recent samples to aggregate for volume. Each sample covers
        ``samplePeriodSecs`` seconds as returned by
        ``get_recent_performance_samples``.

    Returns
    -------
    tuple
        ``(tps, median_fee)`` where ``tps`` is transactions per second and
        ``median_fee`` the median prioritization fee in lamports.
    """

    client = Client(rpc_http_url)

    perf = client.get_recent_performance_samples(window)
    samples = perf.get("result", [])
    txs = sum(s.get("numTransactions", 0) for s in samples)
    secs = sum(s.get("samplePeriodSecs", 0) for s in samples)
    tps = txs / secs if secs else 0.0

    try:
        resp = client.get_recent_prioritization_fees()  # type: ignore[attr-defined]
    except Exception:
        resp = client._provider.make_request("getRecentPrioritizationFees")
    fees = [e.get("prioritizationFee", 0) for e in resp.get("result", [])]
    med_fee = float(median(fees)) if fees else 0.0

    return tps, med_fee

