import asyncio
import pytest

from solbot.exchange import PaperConnector
from solbot.engine import RiskManager, TradeEngine
from solbot.persistence import DAL
from solbot.types import Side
from solbot.oracle.coingecko import PriceOracle


class DummyOracle(PriceOracle):
    def __init__(self, price: float, volume: float) -> None:
        self._price = price
        self._volume = volume

    async def price(self, token: str) -> float:  # type: ignore[override]
        return self._price

    async def volume(self, token: str) -> float:  # type: ignore[override]
        return self._volume


def test_connector_returns_fee_and_slippage(tmp_path):
    dal = DAL(str(tmp_path / "db.sqlite"))
    oracle = DummyOracle(10.0, 1_000_000.0)
    connector = PaperConnector(dal, oracle)
    res = asyncio.run(connector.place_order("SOL", 1, Side.BUY))
    assert res.price >= 10.0
    assert res.fee == pytest.approx(res.price * 0.001)


def test_fee_affects_equity(tmp_path):
    dal = DAL(str(tmp_path / "db.sqlite"))
    oracle = DummyOracle(10.0, 1_000_000.0)
    connector = PaperConnector(dal, oracle)
    risk = RiskManager()
    engine = TradeEngine(risk, connector, dal)
    order = asyncio.run(engine.place_order("SOL", 1, Side.BUY))
    assert risk.equity == pytest.approx(order.price * order.quantity - order.fee)
