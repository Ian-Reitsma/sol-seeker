"""Backtest runner to replay historical data and evaluate strategies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Tuple

from solbot.engine.trade import TradeEngine
from solbot.types import Side
from solbot.exchange import ExecutionResult


@dataclass
class TradeBar:
    """Minimal price/volume record."""

    timestamp: float
    price: float
    volume: float


@dataclass
class BacktestResult:
    """Aggregate metrics from a backtest run."""

    pnl: float
    drawdown: float
    sharpe: float


class FeeModel:
    """Percentage-based trading fee."""

    def __init__(self, rate: float = 0.0) -> None:
        self.rate = rate

    def apply(self, price: float, side: Side) -> float:
        return price * (1 + self.rate) if side is Side.BUY else price * (1 - self.rate)


class SlippageModel:
    """Simple proportional slippage model."""

    def __init__(self, rate: float = 0.0) -> None:
        self.rate = rate

    def apply(self, price: float, side: Side) -> float:
        return price * (1 + self.rate) if side is Side.BUY else price * (1 - self.rate)


class BacktestConnector:
    """Connector stub whose price is externally assigned."""

    def __init__(self) -> None:
        self.price: float = 0.0

    async def place_order(
        self, token: str, qty: float, side: Side, limit: Optional[float] = None
    ) -> ExecutionResult:
        return ExecutionResult(price=self.price, slippage=0.0, fee=0.0)


def load_csv(path: str) -> List[TradeBar]:
    """Load historical trade data from a CSV file."""

    import csv

    bars: List[TradeBar] = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            bars.append(
                TradeBar(
                    timestamp=float(row["timestamp"]),
                    price=float(row["price"]),
                    volume=float(row.get("volume", 0)),
                )
            )
    return bars


class BacktestRunner:
    """Replay price data and evaluate strategy performance."""

    def __init__(
        self,
        engine: TradeEngine,
        fee_model: FeeModel | None = None,
        slippage_model: SlippageModel | None = None,
        initial_cash: float = 0.0,
    ) -> None:
        self.engine = engine
        self.fee_model = fee_model or FeeModel()
        self.slippage_model = slippage_model or SlippageModel()
        self.initial_cash = initial_cash

    async def run(
        self,
        data: Iterable[TradeBar],
        strategy: Callable[[TradeBar], Optional[Tuple[Side, float]]],
        token: str = "SOL",
    ) -> BacktestResult:
        cash = self.initial_cash
        position = 0.0
        equity_curve: List[float] = [cash]

        for bar in data:
            price = bar.price
            equity = cash + position * price
            action = strategy(bar)
            if action:
                side, qty = action
                exec_price = self.slippage_model.apply(price, side)
                exec_price = self.fee_model.apply(exec_price, side)
                setattr(self.engine.connector, "price", exec_price)
                await self.engine.place_order(token, qty, side)
                if side is Side.BUY:
                    cash -= exec_price * qty
                    position += qty
                else:
                    cash += exec_price * qty
                    position -= qty
                equity = cash + position * price
            equity_curve.append(equity)

        final_equity = equity_curve[-1]
        pnl = final_equity - self.initial_cash

        peak = equity_curve[0]
        max_dd = 0.0
        for eq in equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak if peak else 0.0
            if dd > max_dd:
                max_dd = dd

        returns: List[float] = []
        for i in range(1, len(equity_curve)):
            prev = equity_curve[i - 1]
            curr = equity_curve[i]
            returns.append((curr - prev) / prev if prev else 0.0)

        if returns:
            mean = sum(returns) / len(returns)
            var = sum((r - mean) ** 2 for r in returns) / len(returns)
            sharpe = mean / (var ** 0.5) if var > 0 else 0.0
        else:
            sharpe = 0.0

        return BacktestResult(pnl=pnl, drawdown=max_dd, sharpe=sharpe)
