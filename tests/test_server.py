from fastapi.testclient import TestClient

from solbot.utils import BotConfig
from solbot.engine import (
    RiskManager,
    TradeEngine,
    PyFeatureEngine,
    PosteriorEngine,
    Event,
    EventKind,
)
from solbot.types import Side
from solbot.server import create_app
from solbot.bootstrap import BootstrapCoordinator
import hashlib, os
from solbot.persistence import DAL
from solbot.persistence.assets import AssetService
import tempfile
from solbot.exchange import PaperConnector
from solbot.oracle import CoingeckoOracle


class DummyLM:
    def __init__(self) -> None:
        self.called = False

    def license_mode(self, wallet: str) -> str:
        self.called = True
        return "full"


def test_api_order_flow():
    tmp = tempfile.NamedTemporaryFile(delete=False)
    cfg = BotConfig(rpc_ws="wss://api.mainnet-beta.solana.com/", log_level="INFO", wallet="111", db_path=tmp.name, bootstrap=False)
    lm = DummyLM()
    dal = DAL(cfg.db_path)
    class DummyOracle(CoingeckoOracle):
        async def price(self, token: str) -> float:
            return 10.0

    oracle = DummyOracle(dal)
    connector = PaperConnector(dal, oracle)
    risk = RiskManager()
    trade = TradeEngine(risk, connector, dal)
    fe = PyFeatureEngine()
    fe.update(Event(kind=EventKind.SWAP, amount_in=1.0), slot=1)
    posterior = PosteriorEngine(n_features=6)
    class DummyAssets(AssetService):
        def refresh(self):
            return self.list_assets()

    assets = DummyAssets(dal)
    assets.dal.save_assets([{"symbol": "SOL"}])
    bootstrap = BootstrapCoordinator()
    os.environ["API_KEY_HASH"] = hashlib.sha256(b"test").hexdigest()
    app = create_app(cfg, lm, risk, trade, assets, bootstrap, fe, posterior)
    with TestClient(app) as client:
        assert lm.called

        resp = client.get("/")
        assert resp.status_code == 200
        assert "sol-bot dashboard" in resp.text
        assert "/features" in resp.text
        assert "/posterior" in resp.text

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

        resp = client.get("/features")
        assert resp.status_code == 200
        assert len(resp.json()) == 256

        resp = client.get("/posterior")
        assert resp.status_code == 200
        probs = resp.json()
        assert set(probs) == {"rug", "trend", "revert", "chop"}

        with client.websocket_connect("/features/ws") as ws:
            fe.update(Event(kind=EventKind.SWAP, amount_in=2.0), slot=1)
            data = ws.receive_json()
            assert len(data) == 256
