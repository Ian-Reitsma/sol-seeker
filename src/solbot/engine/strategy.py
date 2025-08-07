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
        max_position_size: float = float("inf"),
        liquidity_cap: float = 0.1,
    ) -> None:
        self.risk = risk
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.max_position_size = max_position_size
        self.liquidity_cap = liquidity_cap

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
        liquidity: float = float("inf"),
        price: float = 1.0,
    ) -> float:
        """Size position using Kelly fraction with risk and liquidity clamps."""

        if edge <= 0:
            return 0.0
        vol = max(volatility, 1e-6)
        kelly = max(0.0, min(edge / (vol ** 2), 1.0))
        sharpe = self.risk.sharpe
        if sharpe <= 0:
            return 0.0
        kelly *= min(sharpe, 1.0)
        notional = equity * kelly
        qty = notional / max(price, 1e-9)
        qty = min(qty, self.max_position_size)
        qty = min(qty, self.liquidity_cap * liquidity)
        var_limit = min(self.risk.var, self.risk.es) if self.risk.equity > 0 else equity * 0.1
        if var_limit > 0:
            qty = min(qty, var_limit / (vol * price))
        return max(qty, 0.0)

    def evaluate(
        self,
        post: PosteriorOutput,
        fee: float,
        equity: float,
        volatility: float = 0.05,
        liquidity: float = float("inf"),
        price: float = 1.0,
    ) -> Optional[TradeSignal]:
        """Return trade signal if edge positive after fees."""

        edge = self.expected_edge(post, fee)
        qty = self.qty_suggestion(edge, equity, volatility, liquidity, price)
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

