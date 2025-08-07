"""Simplistic in-memory trade engine for paper trading."""

from dataclasses import dataclass, field
from typing import List, Optional
import asyncio

from google.protobuf.json_format import MessageToDict

from .risk import RiskManager
from ..exchange import AbstractConnector, ExecutionResult
from ..persistence import DAL, DBOrder
from ..types import Side




@dataclass
class Order:
    token: str
    quantity: float
    price: float
    slippage: float
    fee: float
    side: Side
    id: int


@dataclass
class TradeEngine:
    """Execute trades via connector and track orders."""

    risk: RiskManager
    connector: AbstractConnector
    dal: DAL
    next_id: int = 1
    orders: List[Order] = field(default_factory=list)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def __post_init__(self) -> None:
        for token, pos in self.dal.load_positions().items():
            self.risk.positions[token] = pos

    async def place_order(
        self, token: str, qty: float, side: Side, limit: Optional[float] = None
    ) -> Order:
        async with self.lock:
            execution: ExecutionResult = await self.connector.place_order(token, qty, side, limit)
            order = Order(
                token=token,
                quantity=qty,
                price=execution.price,
                slippage=execution.slippage,
                fee=execution.fee,
                side=side,
                id=self.next_id,
            )
            self.next_id += 1
            self.orders.append(order)
            self.dal.add_order(
                DBOrder(
                    id=None,
                    token=token,
                    quantity=qty,
                    side=side.value,
                    price=order.price,
                    fee=order.fee,
                    slippage=order.slippage,
                )
            )
            self.risk.record_trade(token, qty, execution.price, side, execution.fee)
            self.dal.upsert_position(self.risk.positions.get(token))
            return order

    def list_orders(self) -> List[Order]:
        return list(self.orders)

    def list_positions(self) -> dict:
        return {k: MessageToDict(v) for k, v in self.risk.positions.items()}
