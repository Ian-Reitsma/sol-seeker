import asyncio
import pytest

from backtest import BacktestConnector, BacktestRunner, FeeModel, SlippageModel, load_csv
from solbot.engine.trade import TradeEngine
from solbot.engine.risk import RiskManager
from solbot.persistence.dal import DAL
from solbot.types import Side


def test_zero_return_baseline(tmp_path):
    data = load_csv("tests/fixtures/sample_trades.csv")
    dal = DAL(str(tmp_path / "test.db"))
    risk = RiskManager()
    connector = BacktestConnector()
    engine = TradeEngine(risk=risk, connector=connector, dal=dal)
    runner = BacktestRunner(engine, initial_cash=1000.0)

    def strategy(bar):
        return None

    result = asyncio.run(runner.run(data, strategy))
    assert result.pnl == 0
    assert result.drawdown == 0
    assert result.sharpe == 0


def test_fee_impact(tmp_path):
    data = load_csv("tests/fixtures/sample_trades.csv")
    dal = DAL(str(tmp_path / "test.db"))
    risk = RiskManager()
    connector = BacktestConnector()
    engine = TradeEngine(risk=risk, connector=connector, dal=dal)
    runner = BacktestRunner(engine, fee_model=FeeModel(0.01), initial_cash=1000.0)

    def strategy(bar):
        if bar.timestamp == 1:
            return (Side.BUY, 1.0)
        if bar.timestamp == 2:
            return (Side.SELL, 1.0)
        return None

    result = asyncio.run(runner.run(data, strategy))
    assert result.pnl == pytest.approx(-2.0)
    assert result.drawdown > 0


def test_execution_result_parity(tmp_path):
    data = load_csv("tests/fixtures/sample_trades.csv")
    dal = DAL(str(tmp_path / "test.db"))
    risk = RiskManager()
    connector = BacktestConnector()
    engine = TradeEngine(risk=risk, connector=connector, dal=dal)
    runner = BacktestRunner(
        engine,
        fee_model=FeeModel(0.01),
        slippage_model=SlippageModel(0.05),
        initial_cash=1000.0,
    )

    def strategy(bar):
        if bar.timestamp == 1:
            return (Side.BUY, 1.0)
        if bar.timestamp == 2:
            return (Side.SELL, 1.0)
        return None

    asyncio.run(runner.run(data, strategy))
    buy = engine.orders[0]
    assert buy.slippage == pytest.approx(5.0)
    assert buy.fee == pytest.approx(105 * 0.01)
