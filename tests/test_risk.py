import pytest

from solbot.engine import RiskManager
from solbot.types import Side


def test_token_drawdown_limit_enforced():
    rm = RiskManager()
    rm.record_trade("SOL", 1.0, 100.0, Side.BUY)
    rm.update_market_price("SOL", 100.0)
    rm.set_token_drawdown_limit("SOL", 0.1)
    rm.update_market_price("SOL", 80.0)
    assert rm.token_drawdown("SOL") == pytest.approx(0.2)
    with pytest.raises(ValueError):
        rm.record_trade("SOL", 0.1, 80.0, Side.BUY)


def test_token_drawdown_reset():
    rm = RiskManager()
    rm.record_trade("SOL", 1.0, 100.0, Side.BUY)
    rm.update_market_price("SOL", 100.0)
    rm.set_token_drawdown_limit("SOL", 0.1)
    rm.update_market_price("SOL", 50.0)
    with pytest.raises(ValueError):
        rm.record_trade("SOL", 0.1, 50.0, Side.BUY)
    rm.reset()
    rm.set_token_drawdown_limit("SOL", 0.1)
    rm.record_trade("SOL", 1.0, 100.0, Side.BUY)
