import asyncio
import pytest

from solbot.exchange import PaperConnector
from solbot.engine import TradeEngine, RiskManager
from solbot.persistence import DAL
from solbot.types import Side
from solbot.oracle.coingecko import PriceOracle


class StubOracle(PriceOracle):
    def __init__(self, price: float, volume: float) -> None:
        self._price = price
        self._volume = volume

    async def price(self, token: str) -> float:  # type: ignore[override]
        return self._price

    async def volume(self, token: str) -> float:  # type: ignore[override]
        return self._volume


def test_slippage_adjusts_price(tmp_path):
    async def run(volume: float):
        dal = DAL(str(tmp_path / f"{volume}.db"))
        rm = RiskManager()
        oracle = StubOracle(100.0, volume)
        connector = PaperConnector(dal, oracle)
        engine = TradeEngine(risk=rm, connector=connector, dal=dal)
        order = await engine.place_order("SOL", 10, Side.BUY)
        assert rm.equity == pytest.approx(order.price * order.quantity - order.fee)
        return order

    high = asyncio.run(run(1_000_000))
    low = asyncio.run(run(10))
    assert low.price > high.price
    assert low.slippage > high.slippage
