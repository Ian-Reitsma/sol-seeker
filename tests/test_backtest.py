import csv
import os
import tempfile
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from backtest import BacktestConfig, BacktestConnector, run_backtest
from solbot.engine import TradeEngine, RiskManager
from solbot.types import Side
from solbot.persistence import DAL


@pytest.mark.asyncio
async def test_run_backtest_basic(tmp_path):
    csv_path = tmp_path / "data.csv"
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "price", "volume"])
        writer.writeheader()
        writer.writerow({"timestamp": 1, "price": 100, "volume": 0})
        writer.writerow({"timestamp": 2, "price": 110, "volume": 0})

    connector = BacktestConnector()
    risk = RiskManager()
    dal = DAL(str(tmp_path / "bt.db"))
    engine = TradeEngine(risk=risk, connector=connector, dal=dal)

    def strat(bar):
        if bar.timestamp == 1:
            return (Side.BUY, 1.0)
        if bar.timestamp == 2:
            return (Side.SELL, 1.0)
        return None

    cfg = BacktestConfig(source=str(csv_path), initial_cash=0.0)
    res = await run_backtest(engine, cfg, strat)
    assert res.pnl == pytest.approx(10.0)
    assert res.drawdown == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_run_backtest_missing_file(tmp_path):
    connector = BacktestConnector()
    risk = RiskManager()
    dal = DAL(str(tmp_path / "bt.db"))
    engine = TradeEngine(risk=risk, connector=connector, dal=dal)
    cfg = BacktestConfig(source=str(tmp_path / "missing.csv"))
    with pytest.raises(FileNotFoundError):
        await run_backtest(engine, cfg)


class BTRequest(BaseModel):
    source: str
    fee: float = 0.0
    slippage: float = 0.0
    initial_cash: float = 0.0


class BTResponse(BaseModel):
    pnl: float
    drawdown: float
    sharpe: float


def create_test_app() -> FastAPI:
    app = FastAPI()

    @app.post("/backtest", response_model=BTResponse)
    async def bt(req: BTRequest) -> BTResponse:
        try:
            with tempfile.TemporaryDirectory() as tmp:
                dal = DAL(os.path.join(tmp, "bt.db"))
                bt_risk = RiskManager()
                connector = BacktestConnector()
                engine_bt = TradeEngine(risk=bt_risk, connector=connector, dal=dal)
                cfg = BacktestConfig(
                    source=req.source,
                    fee_rate=req.fee,
                    slippage_rate=req.slippage,
                    initial_cash=req.initial_cash,
                )
                res = await run_backtest(engine_bt, cfg)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="source not found")
        return BTResponse(pnl=res.pnl, drawdown=res.drawdown, sharpe=res.sharpe)

    return app


def test_backtest_route(tmp_path):
    csv_path = tmp_path / "data.csv"
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "price", "volume"])
        writer.writeheader()
        writer.writerow({"timestamp": 1, "price": 100, "volume": 0})
        writer.writerow({"timestamp": 2, "price": 110, "volume": 0})

    app = create_test_app()
    with TestClient(app) as client:
        resp = client.post(
            "/backtest",
            json={"source": str(csv_path), "fee": 0, "slippage": 0, "initial_cash": 0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert {"pnl", "drawdown", "sharpe"} <= data.keys()
        assert isinstance(data["pnl"], float)

        resp2 = client.post(
            "/backtest",
            json={"source": str(csv_path) + "missing", "fee": 0, "slippage": 0, "initial_cash": 0},
        )
        assert resp2.status_code == 404
