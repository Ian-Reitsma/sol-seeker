import pytest

from solbot.engine import RiskManager
from solbot.types import Side


def test_pnl_tracking():
    rm = RiskManager()
    rm.set_max_exposure("SOL", 1000.0)
    rm.record_trade("SOL", 1.0, 10.0, Side.BUY)
    rm.update_market_price("SOL", 12.0)
    assert rm.positions["SOL"].cost == pytest.approx(10.0)
    assert rm.pnl["SOL"].unrealized == pytest.approx(2.0)
    rm.record_trade("SOL", 0.5, 12.0, Side.SELL)
    assert rm.pnl["SOL"].realized == pytest.approx(1.0)
    assert rm.pnl["SOL"].unrealized == pytest.approx(1.0)


def test_max_exposure():
    rm = RiskManager()
    rm.set_max_exposure("SOL", 100.0)
    rm.record_trade("SOL", 5.0, 10.0, Side.BUY)
    with pytest.raises(ValueError):
        rm.record_trade("SOL", 6.0, 10.0, Side.BUY)

