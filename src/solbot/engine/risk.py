"""Risk management primitives with PnL, exposure and fee tracking."""

from __future__ import annotations

from typing import Dict, List
from collections import deque
import time

import numpy as np

from solbot.schema import PositionState, PnLState
from ..types import Side


class RiskManager:
    """Tracks positions, PnL, and portfolio risk."""

    def __init__(self) -> None:
        self.positions: Dict[str, PositionState] = {}
        self.pnl: Dict[str, PnLState] = {}
        self.market_prices: Dict[str, float] = {}
        self.max_exposure: Dict[str, float] = {}
        self.peak_equity: float = 0.0
        self.equity: float = 0.0
        self.price_history: Dict[str, List[float]] = {}
        self.equity_history: deque[tuple[int, float]] = deque(maxlen=10_000)
        self.token_peak: Dict[str, float] = {}
        self.token_equity: Dict[str, float] = {}
        self.token_drawdown_limits: Dict[str, float] = {}

    # ------------------------------------------------------------------
    # Compatibility helpers
    # ------------------------------------------------------------------
    def update_equity(self, new_equity: float) -> None:
        """Manually set equity (maintains peak tracking)."""

        self.equity = new_equity
        if new_equity > self.peak_equity:
            self.peak_equity = new_equity
        ts = int(time.time())
        self.equity_history.append((ts, new_equity))

    @property
    def drawdown(self) -> float:
        if self.peak_equity == 0:
            return 0.0
        return (self.peak_equity - self.equity) / self.peak_equity

    def reset(self) -> None:
        """Clear all state and equity history."""

        self.positions.clear()
        self.pnl.clear()
        self.market_prices.clear()
        self.price_history.clear()
        self.max_exposure.clear()
        self.token_peak.clear()
        self.token_equity.clear()
        self.token_drawdown_limits.clear()
        self.peak_equity = 0.0
        self.equity_history.clear()
        self.update_equity(0.0)

    # ------------------------------------------------------------------
    # Position and PnL tracking
    # ------------------------------------------------------------------
    def set_max_exposure(self, token: str, notional: float) -> None:
        self.max_exposure[token] = notional

    def set_token_drawdown_limit(self, token: str, limit: float) -> None:
        self.token_drawdown_limits[token] = limit

    def token_drawdown(self, token: str) -> float:
        peak = self.token_peak.get(token, 0.0)
        equity = self.token_equity.get(token, 0.0)
        if peak == 0:
            return 0.0
        return (peak - equity) / peak

    def _enforce_exposure(self, token: str, qty: float, price: float) -> None:
        limit = self.max_exposure.get(token)
        if limit is None:
            return
        current_qty = self.positions.get(token).qty if token in self.positions else 0.0
        exposure = abs((current_qty + qty) * price)
        if exposure > limit:
            raise ValueError("max exposure exceeded")

    def record_trade(self, token: str, qty: float, price: float, side: Side, fee: float = 0.0) -> None:
        """Record a filled order and update PnL and exposure."""
        limit = self.token_drawdown_limits.get(token)
        if limit is not None and self.token_drawdown(token) >= limit:
            raise ValueError("token drawdown limit exceeded")

        if side is Side.BUY:
            self.add_position(token, qty, price, fee)
        else:
            self.remove_position(token, qty, price, fee)
        self.update_market_price(token, price)

    def add_position(self, token: str, qty: float, price: float, fee: float = 0.0) -> None:
        self._enforce_exposure(token, qty, price)
        pos = self.positions.get(token)
        if pos:
            total_qty = pos.qty + qty
            pos.cost = (pos.qty * pos.cost + qty * price) / total_qty
            pos.qty = total_qty
        else:
            pos = PositionState(token=token, qty=qty, cost=price, unrealized=0.0)
            self.pnl[token] = PnLState(realized=0.0, unrealized=0.0)
        self.positions[token] = pos
        pnl = self.pnl[token]
        pnl.realized -= fee
        self._recalc_equity()

    def remove_position(self, token: str, qty: float, price: float, fee: float = 0.0) -> None:
        pos = self.positions.get(token)
        if not pos or pos.qty < qty:
            raise ValueError("position too small")
        pnl = self.pnl.setdefault(token, PnLState(realized=0.0, unrealized=0.0))
        pnl.realized += (price - pos.cost) * qty - fee
        pos.qty -= qty
        if pos.qty == 0:
            del self.positions[token]
            self.market_prices.pop(token, None)
            pnl.unrealized = 0.0
        else:
            self.positions[token] = pos
        self._recalc_equity()

    def update_market_price(self, token: str, price: float) -> None:
        if token not in self.positions:
            return
        self.market_prices[token] = price
        pos = self.positions[token]
        pnl = self.pnl[token]
        pnl.unrealized = (price - pos.cost) * pos.qty
        pos.unrealized = pnl.unrealized
        hist = self.price_history.setdefault(token, [])
        hist.append(price)
        if len(hist) > 100:
            hist.pop(0)
        self._recalc_equity()

    def _recalc_equity(self) -> None:
        value = 0.0
        for token, pos in self.positions.items():
            price = self.market_prices.get(token, pos.cost)
            value += pos.qty * price
            self._update_token_equity(token)
        for token in self.pnl:
            if token not in self.positions:
                self._update_token_equity(token)
        realized = sum(p.realized for p in self.pnl.values())
        self.update_equity(value + realized)

    def _update_token_equity(self, token: str) -> None:
        pnl = self.pnl.get(token, PnLState(realized=0.0, unrealized=0.0))
        pos = self.positions.get(token)
        price = self.market_prices.get(token, pos.cost if pos else 0.0)
        equity = pnl.realized + (pos.qty * price if pos else 0.0)
        self.token_equity[token] = equity
        peak = self.token_peak.get(token, 0.0)
        if equity > peak:
            self.token_peak[token] = equity

    # ------------------------------------------------------------------
    # Portfolio metrics
    # ------------------------------------------------------------------
    def total_realized(self) -> float:
        return sum(p.realized for p in self.pnl.values())

    def total_unrealized(self) -> float:
        return sum(p.unrealized for p in self.pnl.values())

    def portfolio_value(self) -> float:
        return self.equity

    @property
    def var(self) -> float:
        return self.value_at_risk(self.price_history)

    @property
    def es(self) -> float:
        return self.expected_shortfall(self.price_history)

    @property
    def sharpe(self) -> float:
        return self.sharpe_ratio(self.price_history)

    def portfolio_volatility(self, price_history: Dict[str, List[float]]) -> float:
        tokens = [t for t in self.positions if t in price_history and len(price_history[t]) > 1]
        if not tokens:
            return 0.0
        returns = []
        exposures = []
        for t in tokens:
            prices = np.array(price_history[t], dtype=float)
            r = np.diff(prices) / prices[:-1]
            returns.append(r)
            exposures.append(self.positions[t].qty * prices[-1])
        min_len = min(len(r) for r in returns)
        returns = np.stack([r[-min_len:] for r in returns])
        weights = np.array(exposures)
        weights = weights / weights.sum()
        cov = np.cov(returns)
        return float(np.sqrt(weights @ cov @ weights))

    def value_at_risk(self, price_history: Dict[str, List[float]], alpha: float = 0.95) -> float:
        tokens = [t for t in self.positions if t in price_history and len(price_history[t]) > 1]
        if not tokens:
            return 0.0
        returns = []
        exposures = []
        for t in tokens:
            prices = np.array(price_history[t], dtype=float)
            r = np.diff(prices) / prices[:-1]
            returns.append(r)
            exposures.append(self.positions[t].qty * prices[-1])
        min_len = min(len(r) for r in returns)
        returns = np.stack([r[-min_len:] for r in returns])
        weights = np.array(exposures)
        weights = weights / weights.sum()
        portfolio_returns = weights @ returns
        portfolio_value = float(sum(exposures))
        var = -np.quantile(portfolio_returns, 1 - alpha) * portfolio_value
        return float(max(var, 0.0))

    def expected_shortfall(self, price_history: Dict[str, List[float]], alpha: float = 0.95) -> float:
        tokens = [t for t in self.positions if t in price_history and len(price_history[t]) > 1]
        if not tokens:
            return 0.0
        returns = []
        exposures = []
        for t in tokens:
            prices = np.array(price_history[t], dtype=float)
            r = np.diff(prices) / prices[:-1]
            returns.append(r)
            exposures.append(self.positions[t].qty * prices[-1])
        min_len = min(len(r) for r in returns)
        returns = np.stack([r[-min_len:] for r in returns])
        weights = np.array(exposures)
        weights = weights / weights.sum()
        portfolio_returns = weights @ returns
        portfolio_value = float(sum(exposures))
        threshold = np.quantile(portfolio_returns, 1 - alpha)
        tail = portfolio_returns[portfolio_returns < threshold]
        if tail.size == 0:
            return 0.0
        es = -tail.mean() * portfolio_value
        return float(max(es, 0.0))

    def sharpe_ratio(self, price_history: Dict[str, List[float]]) -> float:
        tokens = [t for t in self.positions if t in price_history and len(price_history[t]) > 1]
        if not tokens:
            return 0.0
        returns = []
        exposures = []
        for t in tokens:
            prices = np.array(price_history[t], dtype=float)
            r = np.diff(prices) / prices[:-1]
            returns.append(r)
            exposures.append(self.positions[t].qty * prices[-1])
        min_len = min(len(r) for r in returns)
        returns = np.stack([r[-min_len:] for r in returns])
        weights = np.array(exposures)
        weights = weights / weights.sum()
        portfolio_returns = weights @ returns
        if portfolio_returns.size < 2:
            return 0.0
        mean = portfolio_returns.mean()
        std = portfolio_returns.std()
        if std <= 0:
            return 0.0
        return float(mean / std)

    # ------------------------------------------------------------------
    # Additional exposure metrics
    # ------------------------------------------------------------------
    def total_exposure(self) -> float:
        """Return total absolute notional exposure across all positions."""

        return sum(
            abs(pos.qty * self.market_prices.get(tok, pos.cost))
            for tok, pos in self.positions.items()
        )

    @property
    def exposure(self) -> float:
        """Portfolio exposure as a fraction of equity."""

        if self.equity == 0:
            return 0.0
        return self.total_exposure() / self.equity

    @property
    def leverage(self) -> float:
        """Simple leverage ratio based on total exposure."""

        return self.exposure

    @property
    def position_size(self) -> float:
        """Largest position notional size."""

        if not self.positions:
            return 0.0
        return max(
            abs(pos.qty * self.market_prices.get(tok, pos.cost))
            for tok, pos in self.positions.items()
        )

    def max_drawdown(self) -> float:
        """Historical peak-to-trough drawdown across equity history."""

        peak = 0.0
        max_dd = 0.0
        for _, eq in self.equity_history:
            if eq > peak:
                peak = eq
            if peak > 0:
                dd = (peak - eq) / peak
                if dd > max_dd:
                    max_dd = dd
        return max_dd

