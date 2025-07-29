"""Risk management primitives."""

from dataclasses import dataclass


@dataclass
class Position:
    token: str
    quantity: float
    cost_basis: float


class RiskManager:
    """Tracks simple positions and computes drawdown."""

    def __init__(self) -> None:
        self.positions: dict[str, Position] = {}
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
        self.positions[token] = Position(token, qty, price)
        self.update_equity(self.equity + qty * price)

    def remove_position(self, token: str, price: float) -> None:
        pos = self.positions.pop(token, None)
        if pos:
            self.update_equity(self.equity - pos.quantity * price)

    def portfolio_value(self) -> float:
        return self.equity
