"""Risk management primitives using protobuf PositionState."""

from typing import Dict

from solbot.schema import PositionState


class RiskManager:
    """Tracks simple positions and computes drawdown."""

    def __init__(self) -> None:
        self.positions: Dict[str, PositionState] = {}
        self.peak_equity: float = 0.0
        self.equity: float = 0.0

    def update_equity(self, new_equity: float) -> None:
        self.equity = new_equity
        if new_equity > self.peak_equity:
            self.peak_equity = new_equity

    @property
    def drawdown(self) -> float:
        if self.peak_equity == 0:
            return 0.0
        return (self.peak_equity - self.equity) / self.peak_equity

    def add_position(self, token: str, qty: float, price: float) -> None:
        pos = self.positions.get(token)
        if pos:
            new_qty = pos.qty + qty
            avg_cost = (pos.qty * pos.cost + qty * price) / new_qty
            pos.qty = new_qty
            pos.cost = avg_cost
        else:
            pos = PositionState(token=token, qty=qty, cost=price, unrealized=0.0)
        self.positions[token] = pos
        self.update_equity(self.equity + qty * price)

    def remove_position(self, token: str, qty: float, price: float) -> None:
        pos = self.positions.get(token)
        if not pos or pos.qty < qty:
            raise ValueError("position too small")
        pos.qty -= qty
        if pos.qty == 0:
            del self.positions[token]
        else:
            self.positions[token] = pos
        self.update_equity(self.equity - qty * price)

    def portfolio_value(self) -> float:
        return self.equity
