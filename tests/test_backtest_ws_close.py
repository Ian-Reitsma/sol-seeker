import csv
import tempfile
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from prometheus_client import REGISTRY

from solbot.utils import BotConfig
from solbot.engine import RiskManager, TradeEngine
from solbot.bootstrap import BootstrapCoordinator
from solbot.persistence import DAL
from solbot.persistence.assets import AssetService
from solbot.exchange import PaperConnector
from solbot.oracle.coingecko import PriceOracle
from solbot.server import create_app


class DummyLM:
    def license_mode(self, wallet: str) -> str:
        return "full"


def create_test_app() -> TestClient:
    for collector in list(REGISTRY._collector_to_names.keys()):
        REGISTRY.unregister(collector)
    tmp = tempfile.NamedTemporaryFile(delete=False)
    cfg = BotConfig(
        rpc_ws="ws://localhost:8900",
        rpc_http="http://localhost:8900",
        log_level="INFO",
        wallet="111",
        db_path=tmp.name,
        bootstrap=False,
    )
    lm = DummyLM()
    dal = DAL(cfg.db_path)

    class DummyOracle(PriceOracle):
        async def price(self, token: str) -> float:  # type: ignore[override]
            return 1.0

        async def volume(self, token: str) -> float:  # type: ignore[override]
            return 1_000.0

    oracle = DummyOracle()
    connector = PaperConnector(dal, oracle)
    risk = RiskManager()
    trade = TradeEngine(risk, connector, dal)
    bootstrap = BootstrapCoordinator()

    class DummyAssets(AssetService):
        def refresh(self):
            return self.list_assets()

    assets = DummyAssets(dal)
    assets.dal.save_assets([{"symbol": "SOL"}])
    app = create_app(cfg, lm, risk, trade, assets, bootstrap)
    return TestClient(app)


def test_backtest_ws_close(tmp_path):
    csv_path = tmp_path / "data.csv"
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "price", "volume"])
        writer.writeheader()
        writer.writerow({"timestamp": 1, "price": 100, "volume": 0})
        writer.writerow({"timestamp": 2, "price": 110, "volume": 0})
    with create_test_app() as client:
        resp = client.post(
            "/backtest",
            json={"period": str(csv_path), "capital": 0.0, "strategy_mix": "momentum"},
        )
        assert resp.status_code == 200
        job_id = resp.json()["id"]
        with client.websocket_connect(f"/backtest/ws/{job_id}") as ws:
            while True:
                msg = ws.receive_json()
                if msg.get("finished"):
                    assert "pnl" in msg
                    break
            with pytest.raises(WebSocketDisconnect):
                ws.receive_text()
