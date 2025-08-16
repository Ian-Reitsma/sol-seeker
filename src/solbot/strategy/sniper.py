"""Listing sniper that buys immediately on new token listings."""

from __future__ import annotations

from dataclasses import dataclass
from .typing import RiskManagerLike


@dataclass
class SniperConfig:
    max_slippage: float = 0.01
    stake: float = 0.1  # fraction of equity


class SniperStrategy:
    def __init__(self, risk: RiskManagerLike, cfg: SniperConfig | None = None) -> None:
        self.risk = risk
        self.cfg = cfg or SniperConfig()

    def should_buy(self, price_impact: float) -> bool:
        return price_impact <= self.cfg.max_slippage

    def size(self, equity: float) -> float:
        return equity * self.cfg.stake
