from solbot.engine import RiskManager


def test_var_updates_with_prices():
    risk = RiskManager()
    risk.add_position("SOL", 1.0, 100.0)
    risk.update_market_price("SOL", 100.0)
    risk.update_market_price("SOL", 90.0)
    assert risk.var > 0


def test_es_and_sharpe():
    risk = RiskManager()
    risk.add_position("SOL", 1.0, 100.0)
    for price in [100.0, 90.0, 80.0, 70.0]:
        risk.update_market_price("SOL", price)
    assert risk.es >= risk.var > 0
    assert risk.sharpe < 0
