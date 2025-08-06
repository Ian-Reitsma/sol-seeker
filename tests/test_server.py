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
from solbot.schema import SCHEMA_HASH


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
        root_data = resp.json()
        assert (
            root_data["tradingview"]
            == "https://www.tradingview.com/widgetembed/?symbol=<sym>USDT"
        )
        assert root_data["endpoints"]["features"] == "/features"
        assert root_data["endpoints"]["features_schema"] == "/features/schema"
        assert root_data["endpoints"]["posterior"] == "/posterior"
        assert root_data["endpoints"]["dashboard"] == "/dashboard"
        assert root_data["endpoints"]["manifest"] == "/manifest"
        assert "timestamp" in root_data
        assert root_data["schema"] == SCHEMA_HASH

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

        resp = client.get("/features/schema")
        assert resp.status_code == 200
        schema = resp.json()["features"]
        first = next((f for f in schema if f["index"] == 0), None)
        assert first and first["name"] == "liquidity_delta"

        with client.websocket_connect("/features/ws") as ws:
            fe.update(Event(kind=EventKind.SWAP, amount_in=2.0), slot=1)
            data = ws.receive_json()
            assert set(data) == {"event", "features"}
            assert data["event"]["kind"] == 1
            assert len(data["features"]) == 256
        # push another update to trigger server cleanup after websocket closes
        fe.update(Event(kind=EventKind.SWAP, amount_in=3.0), slot=1)

        with client.websocket_connect("/posterior/ws") as ws:
            fe.update(Event(kind=EventKind.SWAP, amount_in=4.0), slot=1)
            data = ws.receive_json()
            assert set(data) == {"event", "posterior"}
            assert set(data["posterior"]) == {"rug", "trend", "revert", "chop"}
        fe.update(Event(kind=EventKind.SWAP, amount_in=5.0), slot=1)

        resp = client.get("/dashboard")
        assert resp.status_code == 200
        dash = resp.json()
        assert len(dash["features"]) == 256
        assert set(dash["posterior"]) == {"rug", "trend", "revert", "chop"}
        assert "SOL" in dash["positions"]

        resp = client.get("/manifest")
        assert resp.status_code == 200
        manifest = resp.json()
        ws_paths = manifest["websocket"]
        assert "/features/ws" in ws_paths and "/posterior/ws" in ws_paths
        rest_paths = [r["path"] for r in manifest["rest"]]
        assert "/dashboard" in rest_paths
