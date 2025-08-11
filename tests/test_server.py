from fastapi.testclient import TestClient
import pytest
from starlette.websockets import WebSocketDisconnect
from prometheus_client import REGISTRY

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
from solbot.oracle.coingecko import PriceOracle
from solbot.schema import SCHEMA_HASH


class DummyLM:
    def __init__(self) -> None:
        self.called = False

    def license_mode(self, wallet: str) -> str:
        self.called = True
        return "full"


def test_api_order_flow():
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
            return 10.0
        async def volume(self, token: str) -> float:  # type: ignore[override]
            return 1_000_000.0

    oracle = DummyOracle()
    connector = PaperConnector(dal, oracle)

    async def no_fee():
        return 0.0

    connector._get_fees = no_fee  # type: ignore[attr-defined]
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

        resp = client.get("/", allow_redirects=False)
        assert resp.status_code in (302, 307)
        assert resp.headers["location"] == "/static/dashboard.html"
        resp = client.get("/api")
        assert resp.status_code == 200
        root_data = resp.json()
        assert (
            root_data["tradingview"]
            == "https://www.tradingview.com/widgetembed/?symbol=<sym>USDT"
        )
        assert root_data["endpoints"]["health"] == app.url_path_for("health")
        assert root_data["endpoints"]["status"] == app.url_path_for("status")
        assert root_data["endpoints"]["assets"] == app.url_path_for("assets_endpoint")
        assert root_data["endpoints"]["features"] == app.url_path_for("features_endpoint")
        assert (
            root_data["endpoints"]["features_schema"]
            == app.url_path_for("features_schema_endpoint")
        )
        assert root_data["endpoints"]["posterior"] == app.url_path_for("posterior_endpoint")
        assert root_data["endpoints"]["positions"] == app.url_path_for("positions")
        assert root_data["endpoints"]["orders"] == app.url_path_for("orders")
        assert root_data["endpoints"]["chart"] == app.url_path_for("chart", symbol="<sym>")
        assert root_data["endpoints"]["version"] == app.url_path_for("version")
        assert root_data["endpoints"]["docs"] == app.url_path_for("swagger_ui_html")
        assert root_data["endpoints"]["redoc"] == app.url_path_for("redoc_html")
        assert root_data["endpoints"]["openapi"] == app.url_path_for("openapi")
        assert root_data["endpoints"]["metrics"] == app.url_path_for("metrics")
        assert root_data["endpoints"]["orders_ws"] == app.url_path_for("ws")
        assert root_data["endpoints"]["features_ws"] == app.url_path_for("features_ws")
        assert root_data["endpoints"]["posterior_ws"] == app.url_path_for("posterior_ws")
        assert root_data["endpoints"]["positions_ws"] == app.url_path_for("positions_ws")
        assert root_data["endpoints"]["dashboard_ws"] == app.url_path_for("dashboard_ws")
        assert root_data["endpoints"]["logs_ws"] == app.url_path_for("logs_ws")
        assert root_data["endpoints"]["dashboard"] == app.url_path_for("dashboard")
        assert root_data["endpoints"]["manifest"] == app.url_path_for("manifest")
        assert root_data["endpoints"]["tv"] == app.url_path_for("tradingview_page")
        assert root_data["endpoints"]["license"] == app.url_path_for("license_info")
        assert root_data["endpoints"]["state"] == app.url_path_for("state")
        assert root_data["license"]["mode"] == "full"
        assert root_data["license"]["wallet"] == cfg.wallet
        assert "timestamp" in root_data
        assert root_data["schema"] == SCHEMA_HASH

        with client.websocket_connect("/ws") as ws:
            assert ws.receive_json() == {"error": "unauthorized"}
        with client.websocket_connect("/positions/ws") as ws:
            assert ws.receive_json() == {"error": "unauthorized"}
        with client.websocket_connect("/dashboard/ws") as ws:
            assert ws.receive_json() == {"error": "unauthorized"}

        resp = client.get("/license")
        assert resp.status_code == 200
        lic = resp.json()
        assert lic["mode"] == "full"
        assert lic["wallet"] == cfg.wallet

        resp = client.get("/state")
        assert resp.status_code == 200
        st = resp.json()
        assert st["license"]["mode"] == "full"
        assert st["license"]["wallet"] == cfg.wallet
        assert "status" in st
        assert "timestamp" in st

        resp = client.post("/state", json={"running": False, "settings": {"x": 1}})
        assert resp.status_code == 200
        st2 = resp.json()
        assert st2["running"] is False
        assert st2["settings"] == {"x": 1}
        resp = client.post(
            "/orders",
            json={"token": "SOL", "qty": 1, "side": "buy"},
            headers={"X-API-Key": "test"},
        )
        assert resp.status_code == 400
        resp = client.post("/state", json={"running": True})
        assert resp.status_code == 200
        resp = client.post("/state", json={"emergency_stop": True})
        assert resp.status_code == 200
        resp = client.post(
            "/orders",
            json={"token": "SOL", "qty": 1, "side": "buy"},
            headers={"X-API-Key": "test"},
        )
        assert resp.status_code == 400
        resp = client.post("/state", json={"emergency_stop": False})
        assert resp.status_code == 200

        resp = client.get("/tv")
        assert resp.status_code == 200
        assert "<iframe" in resp.text

        with client.websocket_connect("/ws?key=test") as order_ws, \
            client.websocket_connect("/positions/ws?key=test") as pos_ws:
            resp = client.post(
                "/orders",
                json={"token": "SOL", "qty": 1, "side": "buy"},
                headers={"X-API-Key": "test"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["token"] == "SOL"
            assert data["quantity"] == 1
            assert data["slippage"] >= 0.0
            assert data["status"] == "closed"
            assert "timestamp" in data
            order_data = order_ws.receive_json()
            assert order_data["token"] == "SOL"
            assert "fee" in order_data and "slippage" in order_data
            assert order_data["status"] == "closed"
            assert "timestamp" in order_data
            pos_data = pos_ws.receive_json()
            assert "SOL" in pos_data

        resp = client.get("/positions", headers={"X-API-Key": "test"})
        assert resp.status_code == 200
        positions = resp.json()
        assert "SOL" in positions

        resp = client.get("/orders?status=closed", headers={"X-API-Key": "test"})
        assert resp.status_code == 200
        closed = resp.json()
        assert closed and closed[0]["status"] == "closed"
        resp = client.get("/orders?status=open", headers={"X-API-Key": "test"})
        assert resp.status_code == 200
        assert resp.json() == []

        resp = client.get("/features")
        assert resp.status_code == 200
        feats = resp.json()
        assert len(feats["features"]) == 256
        assert "timestamp" in feats

        resp = client.get("/posterior")
        assert resp.status_code == 200
        probs = resp.json()
        assert set(probs) == {"rug", "trend", "revert", "chop", "timestamp"}

        resp = client.get("/features/schema")
        assert resp.status_code == 200
        schema_resp = resp.json()
        assert "timestamp" in schema_resp
        assert schema_resp["schema"] == root_data["schema"]
        assert schema_resp["version"] == 1
        schema = schema_resp["features"]
        first = next((f for f in schema if f["index"] == 0), None)
        assert first and first["name"] == "liquidity_delta"

        with client.websocket_connect("/features/ws") as ws:
            fe.update(Event(kind=EventKind.SWAP, amount_in=2.0), slot=1)
            data = ws.receive_json()
            assert set(data) == {"event", "features"}
            assert data["event"]["kind"] == 1
            assert len(data["features"]) == 256

        with client.websocket_connect("/posterior/ws") as ws:
            fe.update(Event(kind=EventKind.SWAP, amount_in=4.0), slot=1)
            data = ws.receive_json()
            assert set(data) == {"event", "posterior"}
            assert set(data["posterior"]) == {"rug", "trend", "revert", "chop"}


        resp = client.get("/dashboard")
        assert resp.status_code == 200
        dash = resp.json()
        assert len(dash["features"]) == 256
        assert set(dash["posterior"]) == {"rug", "trend", "revert", "chop"}
        assert "SOL" in dash["positions"]
        assert len(dash["orders"]) == 1
        assert dash["orders"][0]["token"] == "SOL"
        assert dash["risk"]["equity"] == risk.equity
        assert dash["risk"]["unrealized"] == 0.0
        assert dash["risk"]["drawdown"] == risk.drawdown
        assert dash["risk"]["realized"] == risk.total_realized()
        assert dash["risk"]["var"] == risk.var
        assert dash["risk"]["es"] == risk.es
        assert dash["risk"]["sharpe"] == risk.sharpe

        resp = client.get("/manifest")
        assert resp.status_code == 200
        manifest = resp.json()
        assert manifest["version"] == 1
        assert "timestamp" in manifest
        ws_paths = manifest["websocket"]
        assert "/ws" in ws_paths
        assert "/features/ws" in ws_paths and "/posterior/ws" in ws_paths
        assert "/positions/ws" in ws_paths
        assert "/dashboard/ws" in ws_paths
        rest_paths = [r["path"] for r in manifest["rest"]]
        assert "/dashboard" in rest_paths
        assert "/tv" in rest_paths
        assert "/state" in rest_paths
