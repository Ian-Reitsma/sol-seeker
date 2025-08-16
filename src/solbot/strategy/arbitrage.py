"""Simple cross-exchange arbitrage stub."""

from __future__ import annotations

from dataclasses import dataclass
from .typing import RiskManagerLike


@dataclass
class ArbOpportunity:
    spread: float
    latency_ms: int


class ArbitrageStrategy:
    def __init__(self, risk: RiskManagerLike, max_latency: int = 100) -> None:
        self.risk = risk
        self.max_latency = max_latency

    def should_trade(self, opp: ArbOpportunity, fee: float) -> bool:
        return opp.spread > fee and opp.latency_ms < self.max_latency

    def size(self, equity: float, fraction: float = 0.05) -> float:
        return equity * fraction
