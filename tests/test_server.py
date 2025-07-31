from fastapi.testclient import TestClient

from solbot.utils import BotConfig
from solbot.engine import RiskManager, TradeEngine
from solbot.types import Side
from solbot.server import create_app
from solbot.bootstrap import BootstrapCoordinator
import hashlib, os
from solbot.persistence import DAL
from solbot.persistence.assets import AssetService
from solbot.exchange import PaperConnector
from solbot.oracle import CoingeckoOracle


class DummyLM:
    def __init__(self) -> None:
        self.called = False

    def has_license(self, wallet: str) -> bool:
        self.called = True
        return True


def test_api_order_flow():
    cfg = BotConfig(rpc_ws="wss://api.mainnet-beta.solana.com/", log_level="INFO", wallet="111", db_path="/tmp/test.db", bootstrap=False)
    lm = DummyLM()
    dal = DAL(cfg.db_path)
    class DummyOracle(CoingeckoOracle):
        async def price(self, token: str) -> float:
            return 10.0

    oracle = DummyOracle(dal)
    connector = PaperConnector(dal, oracle)
    risk = RiskManager()
    trade = TradeEngine(risk, connector, dal)
    class DummyAssets(AssetService):
        def refresh(self):
            return self.list_assets()

    assets = DummyAssets(dal)
    assets.dal.save_assets([{"symbol": "SOL"}])
    bootstrap = BootstrapCoordinator()
    os.environ["API_KEY_HASH"] = hashlib.sha256(b"test").hexdigest()
    app = create_app(cfg, lm, risk, trade, assets, bootstrap)
    with TestClient(app) as client:
        assert lm.called

        resp = client.post(
            "/orders",
            json={"token": "SOL", "qty": 1, "side": "buy"},
            headers={"X-API-Key": "test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["token"] == "SOL"
        assert data["quantity"] == 1

        resp = client.get("/positions", headers={"X-API-Key": "test"})
        assert resp.status_code == 200
        positions = resp.json()
        assert "SOL" in positions
