"""Exchange connector abstractions."""

from __future__ import annotations

import abc

from ..types import Side
from ..persistence import DAL
from ..oracle import PriceOracle


class AbstractConnector(abc.ABC):
    """Abstract exchange connector."""

    def __init__(self, dal: DAL, oracle: PriceOracle) -> None:
        self.dal = dal
        self.oracle = oracle

    @abc.abstractmethod
    async def place_order(self, token: str, qty: float, side: Side, limit: float | None = None) -> float:
        """Execute order and return executed price."""


class PaperConnector(AbstractConnector):
    """Paper trading connector using the price oracle."""

    async def place_order(self, token: str, qty: float, side: Side, limit: float | None = None) -> float:
        price = await self.oracle.price(token)
        if limit and ((side is Side.BUY and price > limit) or (side is Side.SELL and price < limit)):
            raise ValueError("limit not reached")
        return price


class SolanaConnector(AbstractConnector):
    async def place_order(self, token: str, qty: float, side: Side, limit: float | None = None) -> float:
        raise NotImplementedError


class BinanceConnector(AbstractConnector):
    async def place_order(self, token: str, qty: float, side: Side, limit: float | None = None) -> float:
        raise NotImplementedError
