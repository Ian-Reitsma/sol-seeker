"""Exchange connector abstractions."""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Optional

from ..types import Side
from ..persistence import DAL
from ..oracle import PriceOracle


@dataclass
class ExecutionResult:
    price: float
    slippage: float
    fee: float


class AbstractConnector(abc.ABC):
    """Abstract exchange connector."""

    def __init__(self, dal: DAL, oracle: PriceOracle) -> None:
        self.dal = dal
        self.oracle = oracle

    @abc.abstractmethod
    async def place_order(
        self, token: str, qty: float, side: Side, limit: Optional[float] = None
    ) -> ExecutionResult:
        """Execute order and return execution details."""


class PaperConnector(AbstractConnector):
    """Paper trading connector using the price oracle."""

    async def place_order(
        self, token: str, qty: float, side: Side, limit: Optional[float] = None
    ) -> ExecutionResult:
        price = await self.oracle.price(token)
        volume = await self.oracle.volume(token)
        if limit and ((side is Side.BUY and price > limit) or (side is Side.SELL and price < limit)):
            raise ValueError("limit not reached")
        slippage_pct = min(0.05, 0 if volume <= 0 else qty / volume)
        slip = price * slippage_pct
        fill = price + slip if side is Side.BUY else price - slip
        fee = fill * qty * 0.001
        return ExecutionResult(price=fill, slippage=slip, fee=fee)


class SolanaConnector(AbstractConnector):
    async def place_order(
        self, token: str, qty: float, side: Side, limit: Optional[float] = None
    ) -> ExecutionResult:
        raise NotImplementedError


class BinanceConnector(AbstractConnector):
    async def place_order(
        self, token: str, qty: float, side: Side, limit: Optional[float] = None
    ) -> ExecutionResult:
        raise NotImplementedError
