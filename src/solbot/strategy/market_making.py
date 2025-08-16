"""Naive market making strategy providing bids and asks."""

from __future__ import annotations

from dataclasses import dataclass
from .typing import RiskManagerLike


@dataclass
class Quote:
    price: float
    size: float


class MarketMakingStrategy:
    def __init__(self, risk: RiskManagerLike, spread: float = 0.002) -> None:
        self.risk = risk
        self.spread = spread

    def quotes(self, mid: float) -> tuple[Quote, Quote]:
        size = self.risk.equity * 0.01 / mid
        bid = Quote(price=mid * (1 - self.spread), size=size)
        ask = Quote(price=mid * (1 + self.spread), size=size)
        return bid, ask
