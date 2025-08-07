"""Trading strategy utilities and network-aware heuristics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from .posterior import PosteriorEngine, PosteriorOutput
from .risk import RiskManager


@dataclass
class TradeSignal:
    """Suggested trade signal containing quantity and edge."""

    qty: float
    edge: float


class Strategy:
    """Simple probability/fee based strategy with risk controls."""

    def __init__(
        self,
        risk: RiskManager,
        stop_loss: float = 0.02,
        take_profit: float = 0.04,
    ) -> None:
        self.risk = risk
        self.stop_loss = stop_loss
        self.take_profit = take_profit

    # ------------------------------------------------------------------
    # Edge and sizing
    # ------------------------------------------------------------------
    def expected_edge(self, post: PosteriorOutput, fee: float) -> float:
        """Return expected edge after fees."""

        return post.trend - post.revert - fee

    def qty_suggestion(
        self,
        edge: float,
        equity: float,
        volatility: float = 0.05,
    ) -> float:
        """Size position using Kelly fraction with volatility targeting."""

        if edge <= 0:
            return 0.0
        vol = max(volatility, 1e-6)
        kelly = edge / (vol ** 2)
        kelly = max(0.0, min(kelly, 1.0))
        return equity * kelly

    def evaluate(
        self,
        post: PosteriorOutput,
        fee: float,
        equity: float,
        volatility: float = 0.05,
    ) -> Optional[TradeSignal]:
        """Return trade signal if edge positive after fees."""

        edge = self.expected_edge(post, fee)
        qty = self.qty_suggestion(edge, equity, volatility)
        if qty <= 0:
            return None
        return TradeSignal(qty=qty, edge=edge)

    # ------------------------------------------------------------------
    # Risk controls
    # ------------------------------------------------------------------
    def check_exit(self, token: str, price: float) -> None:
        """Close positions hitting stop-loss or take-profit."""

        pos = self.risk.positions.get(token)
        if not pos:
            return
        if price <= pos.cost * (1 - self.stop_loss):
            self.risk.remove_position(token, pos.qty, price)
        elif price >= pos.cost * (1 + self.take_profit):
            self.risk.remove_position(token, pos.qty, price)


@dataclass
class VolumeAwareStrategy:
    """Decide entries/exits using posterior and network signals."""

    posterior: PosteriorEngine
    vol_idx: int = 6
    fee_idx: int = 7

    def should_enter(self, features: Sequence[float]) -> bool:
        post = self.posterior.predict(features)
        volume = features[self.vol_idx] if len(features) > self.vol_idx else 0.0
        fee = features[self.fee_idx] if len(features) > self.fee_idx else 0.0
        score = post.trend + 0.1 * (volume + fee) - post.rug
        return score > 0.5

    def should_exit(self, features: Sequence[float]) -> bool:
        post = self.posterior.predict(features)
        volume = features[self.vol_idx] if len(features) > self.vol_idx else 0.0
        fee = features[self.fee_idx] if len(features) > self.fee_idx else 0.0
        score = post.rug - post.trend + 0.1 * (-volume - fee)
        return score > 0.5

