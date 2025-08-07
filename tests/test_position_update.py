
import hashlib
import os
import tempfile

from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from solbot.utils import BotConfig
from solbot.engine import RiskManager, TradeEngine, PyFeatureEngine, PosteriorEngine
from solbot.server import create_app
from solbot.exchange import PaperConnector
from solbot.persistence import DAL
from solbot.persistence.assets import AssetService
from solbot.oracle import CoingeckoOracle
from solbot.bootstrap import BootstrapCoordinator


class DummyLM:
    def license_mode(self, wallet: str) -> str:
        return "full"


class DummyOracle(CoingeckoOracle):
    async def price(self, token: str) -> float:
        return 10.0
    async def volume(self, token: str) -> float:
        return 1_000_000.0


class DummyAssets(AssetService):
    def refresh(self):
        return self.list_assets()


def build_client() -> TestClient:
    for collector in list(REGISTRY._collector_to_names.keys()):
        REGISTRY.unregister(collector)
    tmp = tempfile.NamedTemporaryFile(delete=False)
    cfg = BotConfig(
        rpc_ws="wss://api.mainnet-beta.solana.com/",
        log_level="INFO",
        wallet="111",
        db_path=tmp.name,
        bootstrap=False,
    )
    lm = DummyLM()
    dal = DAL(cfg.db_path)
    oracle = DummyOracle(dal)
    connector = PaperConnector(dal, oracle)

    async def no_fee():
        return 0.0

    connector._get_fees = no_fee  # type: ignore[attr-defined]
    risk = RiskManager()
    trade = TradeEngine(risk, connector, dal)
    fe = PyFeatureEngine()
    posterior = PosteriorEngine(n_features=6)
    assets = DummyAssets(dal)
    assets.dal.save_assets([{"symbol": "SOL"}])
    bootstrap = BootstrapCoordinator()
    os.environ["API_KEY_HASH"] = hashlib.sha256(b"test").hexdigest()
    app = create_app(cfg, lm, risk, trade, assets, bootstrap, fe, posterior)
    return TestClient(app)


def test_order_triggers_position_update():
    with build_client() as client:
        with client.websocket_connect("/positions/ws?key=test") as ws:
            resp = client.post(
                "/orders",
                json={"token": "SOL", "qty": 1, "side": "buy"},
                headers={"X-API-Key": "test"},
            )
            assert resp.status_code == 200
            data = ws.receive_json()
            assert data["SOL"]["qty"] == 1.0
