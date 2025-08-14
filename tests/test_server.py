from fastapi.testclient import TestClient
import pytest
from starlette.websockets import WebSocketDisconnect
from starlette.routing import WebSocketRoute
from prometheus_client import REGISTRY
import asyncio
import time
import csv
from backtest import BacktestResult

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
from collections import deque


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
    risk.update_equity(1000.0)
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
        assert root_data["endpoints"]["events_catalysts"] == app.url_path_for("catalysts_endpoint")
        assert root_data["endpoints"]["risk_security"] == app.url_path_for("risk_security_endpoint")
        assert root_data["endpoints"]["whales"] == app.url_path_for("whales_endpoint")
        assert root_data["endpoints"]["smart_money_flow"] == app.url_path_for("smart_money_flow_endpoint")
        assert root_data["endpoints"]["copy_trading"] == app.url_path_for("copy_trading_endpoint")
        assert root_data["endpoints"]["strategies"] == app.url_path_for("strategies_endpoint")
        assert root_data["endpoints"]["arbitrage"] == app.url_path_for("arbitrage_endpoint")
        assert root_data["endpoints"]["strategy_performance"] == app.url_path_for("strategy_performance")
        assert root_data["endpoints"]["strategy_breakdown"] == app.url_path_for("strategy_breakdown")
        assert root_data["endpoints"]["strategy_risk"] == app.url_path_for("strategy_risk")
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

        resp = client.get("/risk/security")
        assert resp.status_code == 200
        sec = resp.json()
        assert {
            "rug_pull",
            "liquidity",
            "contract_verified",
            "holder_distribution",
            "trading_patterns",
        } <= sec.keys()

        resp = client.get("/sentiment/trending")
        assert resp.status_code == 200
        trending = resp.json()
        assert trending and {"symbol", "mentions", "sentiment", "change_pct"} <= trending[0].keys()

        resp = client.get("/sentiment/influencers")
        assert resp.status_code == 200
        infl = resp.json()
        assert infl and {"handle", "message", "followers", "stance"} <= infl[0].keys()

        resp = client.get("/sentiment/pulse")
        assert resp.status_code == 200
        pulse = resp.json()
        assert {"fear_greed", "fear_greed_pct", "social_volume", "social_volume_pct", "fomo", "fomo_pct"} <= pulse.keys()

        resp = client.get("/news")
        assert resp.status_code == 200
        news = resp.json()
        assert news and {"id", "title", "source", "confidence"} <= news[0].keys()

        resp = client.get("/whales")
        assert resp.status_code == 200
        whale = resp.json()
        assert set(whale) == {"following", "success_rate", "copied_today", "profit"}

        resp = client.get("/smart-money-flow")
        assert resp.status_code == 200
        flow = resp.json()
        assert set(flow) == {"net_inflow", "trend"}

        resp = client.get("/copy-trading")
        assert resp.status_code == 200
        trades = resp.json()
        assert all({"whale", "profit"} <= set(t.keys()) for t in trades)

        resp = client.get("/strategies")
        assert resp.status_code == 200
        strats = resp.json()
        assert all({"name", "trades", "pnl", "confidence", "targets", "success"} <= set(s.keys()) for s in strats)

        resp = client.get("/arbitrage")
        assert resp.status_code == 200
        arb = resp.json()
        assert set(arb) == {"status", "trades", "pnl", "spread", "opportunities", "latency"}

        resp = client.get("/strategy/performance")
        assert resp.status_code == 200
        perf = resp.json()
        assert perf and {"name", "pnl", "win_rate"} <= perf[0].keys()

        resp = client.get("/strategy/breakdown")
        assert resp.status_code == 200
        br = resp.json()
        assert br and {"name", "pnl", "win_rate"} <= br[0].keys()

        resp = client.get("/strategy/risk")
        assert resp.status_code == 200
        risk_stats = resp.json()
        assert {"sharpe", "max_drawdown", "volatility", "calmar"} <= risk_stats.keys()

        resp = client.get("/api")
        assert resp.status_code == 200
        smap = resp.json()
        eps = smap.get("endpoints", {})
        for key in (
            "risk_security",
            "sentiment_trending",
            "sentiment_influencers",
            "sentiment_pulse",
            "news",
            "whales",
            "smart_money_flow",
            "strategies",
            "arbitrage",
            "strategy_performance",
            "strategy_breakdown",
            "strategy_risk",
        ):
            assert key in eps

        resp = client.get("/license")
        assert resp.status_code == 200
        lic = resp.json()
        assert lic["mode"] == "full"
        assert lic["wallet"] == cfg.wallet

        resp = client.get("/events/catalysts")
        assert resp.status_code == 200
        cats = resp.json()
        assert isinstance(cats, list)
        assert {"name", "eta", "severity"} <= set(cats[0].keys())
        assert all("$NOVA" not in c["name"] for c in cats)

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
        assert dash["risk"]["position_size"] == risk.position_size
        assert dash["risk"]["leverage"] == risk.leverage
        assert dash["risk"]["exposure"] == risk.exposure

        risk.update_equity(1100.0)
        resp = client.get("/chart/portfolio")
        assert resp.status_code == 200
        assert resp.json()["series"] == [list(t) for t in risk.equity_history]

        import solbot.server.api as api

        async def fake_run_backtest(engine, cfg, strategy=None):
            await asyncio.sleep(0.05)
            return BacktestResult(pnl=10.0, drawdown=0.05, sharpe=1.2)
        api.run_backtest = fake_run_backtest

        resp = client.post(
            "/backtest",
            json={"period": "1D", "capital": 1000, "strategy_mix": "mix"},
        )
        assert resp.status_code == 200
        job_id = resp.json()["id"]
        with client.websocket_connect(f"/backtest/ws/{job_id}") as ws:
            msg = ws.receive_json()
            assert msg["progress"] == 0
            msg = ws.receive_json()
            assert msg["progress"] == 100 and "pnl" in msg
            with pytest.raises(WebSocketDisconnect):
                ws.receive_json()

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
        assert "/strategies" in rest_paths
        assert "/arbitrage" in rest_paths
        assert "/sentiment/trending" in rest_paths
        assert "/sentiment/influencers" in rest_paths
        assert "/sentiment/pulse" in rest_paths
        assert "/news" in rest_paths


def test_backtest_complete(tmp_path):
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
    risk = RiskManager()
    trade = TradeEngine(risk, connector, dal)
    fe = PyFeatureEngine()
    posterior = PosteriorEngine()
    bootstrap = BootstrapCoordinator()
    assets = AssetService(dal)
    assets.dal.save_assets([{"symbol": "SOL"}])
    app = create_app(cfg, lm, risk, trade, assets, bootstrap, fe, posterior)
    csv_path = tmp_path / "data.csv"
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "price", "volume"])
        writer.writeheader()
        writer.writerow({"timestamp": 1, "price": 100, "volume": 0})
        writer.writerow({"timestamp": 2, "price": 110, "volume": 0})
        writer.writerow({"timestamp": 3, "price": 100, "volume": 0})

    with TestClient(app) as client:
        resp = client.post(
            "/backtest",
            json={"period": str(csv_path), "capital": 1000, "strategy_mix": "momentum"},
        )
        assert resp.status_code == 200
        job_id = resp.json()["id"]
        with client.websocket_connect(f"/backtest/ws/{job_id}") as ws:
            msg = ws.receive_json()
            assert msg["progress"] == 0
            msg = ws.receive_json()
            assert msg["progress"] == 100 and abs(msg["pnl"]) == pytest.approx(10.0)
            with pytest.raises(WebSocketDisconnect):
                ws.receive_json()


def test_backtest_cancel():
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
    risk = RiskManager()
    trade = TradeEngine(risk, connector, dal)
    fe = PyFeatureEngine()
    posterior = PosteriorEngine()
    bootstrap = BootstrapCoordinator()
    assets = AssetService(dal)
    assets.dal.save_assets([{ "symbol": "SOL" }])
    app = create_app(cfg, lm, risk, trade, assets, bootstrap, fe, posterior)
    with TestClient(app) as client:
        import solbot.server.api as api

        async def long_run_backtest(engine, cfg, strategy=None):
            await asyncio.sleep(10)
            return BacktestResult(pnl=0.0, drawdown=0.0, sharpe=0.0)
        api.run_backtest = long_run_backtest

        resp = client.post(
            "/backtest",
            json={"period": "1D", "capital": 1000, "strategy_mix": "mix"},
        )
        assert resp.status_code == 200
        job_id = resp.json()["id"]
        with client.websocket_connect(f"/backtest/ws/{job_id}") as ws:
            msg = ws.receive_json()
            assert msg["progress"] == 0
            ws.send_json({"action": "cancel"})
            msg = ws.receive_json()
            assert msg["progress"] == 100 and msg.get("cancelled")
            with pytest.raises(WebSocketDisconnect):
                ws.receive_json()


def test_backtest_error():
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
    risk = RiskManager()
    trade = TradeEngine(risk, connector, dal)
    fe = PyFeatureEngine()
    posterior = PosteriorEngine()
    bootstrap = BootstrapCoordinator()
    assets = AssetService(dal)
    assets.dal.save_assets([{ "symbol": "SOL" }])
    app = create_app(cfg, lm, risk, trade, assets, bootstrap, fe, posterior)
    with TestClient(app) as client:
        import solbot.server.api as api

        async def failing_backtest(engine, cfg, strategy=None):
            await asyncio.sleep(0.1)
            raise RuntimeError("boom")

        api.run_backtest = failing_backtest

        resp = client.post(
            "/backtest",
            json={"period": "1D", "capital": 1000, "strategy_mix": "mix"},
        )
        assert resp.status_code == 200
        job_id = resp.json()["id"]
        with client.websocket_connect(f"/backtest/ws/{job_id}") as ws:
            msg = ws.receive_json()
            if msg.get("progress") == 0:
                msg = ws.receive_json()
            assert msg["error"] == "boom"
            with pytest.raises(WebSocketDisconnect):
                ws.receive_json()


def test_dashboard_ws_heartbeat_timeout():
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
    fe = PyFeatureEngine()
    posterior = PosteriorEngine()
    bootstrap = BootstrapCoordinator()
    assets = AssetService(dal)
    assets.dal.save_assets([{ "symbol": "SOL" }])
    app = create_app(cfg, lm, risk, trade, assets, bootstrap, fe, posterior)

    async def stalled_ws(ws):
        await ws.accept()
        await asyncio.sleep(60)

    for i, route in enumerate(app.router.routes):
        if isinstance(route, WebSocketRoute) and route.path == "/dashboard/ws":
            app.router.routes[i] = WebSocketRoute("/dashboard/ws", stalled_ws)
            break

    with TestClient(app) as client:
        with client.websocket_connect("/dashboard/ws"):
            hb_ts = time.time() * 1000 - 11000
            is_live = time.time() * 1000 - hb_ts <= 10000
            assert not is_live


def test_demo_mode_and_emergency_stop():
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
    fe = PyFeatureEngine()
    posterior = PosteriorEngine()
    bootstrap = BootstrapCoordinator()
    assets = AssetService(dal)
    assets.dal.save_assets([{"symbol": "SOL"}])
    app = create_app(cfg, lm, risk, trade, assets, bootstrap, fe, posterior)
    with TestClient(app) as client:
        # enable demo mode with paper config
        resp = client.post(
            "/state",
            json={"mode": "demo", "paper_assets": ["SOL"], "paper_capital": 1000},
        )
        assert resp.status_code == 200
        st = resp.json()
        assert st["mode"] == "demo"
        assert st["paper"]["assets"] == ["SOL"]
        assert st["paper"]["capital"] == 1000

        # orders blocked in demo mode
        resp = client.post(
            "/orders",
            json={"token": "SOL", "qty": 1, "side": "buy"},
            headers={"X-API-Key": "test"},
        )
        assert resp.status_code == 403

        # switch to live and place order
        resp = client.post("/state", json={"mode": "live"})
        assert resp.status_code == 200
        assert resp.json()["mode"] == "live"
        resp = client.post(
            "/orders",
            json={"token": "SOL", "qty": 1, "side": "buy"},
            headers={"X-API-Key": "test"},
        )
        assert resp.status_code == 200
        assert "SOL" in risk.positions

        # trigger emergency stop and ensure positions cleared
        resp = client.post("/state", json={"emergency_stop": True})
        assert resp.status_code == 200
    assert risk.positions == {}


def test_state_paper_assets_validation():
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
    assets.dal.save_assets([{ "symbol": "SOL" }])
    app = create_app(cfg, lm, risk, trade, assets, bootstrap)
    with TestClient(app) as client:
        resp = client.post("/state", json={"paper_assets": ["BAD"]})
        assert resp.status_code == 400

        resp = client.post(
            "/state", json={"paper_assets": ["SOL"], "paper_capital": 500}
        )
        assert resp.status_code == 200
        st = resp.json()
        assert st["paper"]["assets"] == ["SOL"]
        assert st["paper"]["capital"] == 500

        resp = client.get("/state")
        assert resp.status_code == 200
        st2 = resp.json()
        assert st2["paper"]["assets"] == ["SOL"]
        assert st2["paper"]["capital"] == 500


def test_state_paper_assets_dedup_and_allocation():
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
    assets.dal.save_assets([{ "symbol": "SOL" }, { "symbol": "ETH" }])
    app = create_app(cfg, lm, risk, trade, assets, bootstrap)

    with TestClient(app) as client:
        resp = client.post(
            "/state",
            json={
                "mode": "demo",
                "paper_assets": [" sol ", "SOL", "eth", " ETH ", ""],
                "paper_capital": 100,
            },
        )
        assert resp.status_code == 200
        st = resp.json()
        assert st["paper"]["assets"] == ["SOL", "ETH"]
        assert risk.equity == 100
        assert set(risk.positions.keys()) == {"SOL", "ETH"}
        assert risk.positions["SOL"].qty == 50
        assert risk.positions["ETH"].qty == 50


def test_chart_portfolio_downsample():
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
    for i in range(20):
        risk.update_equity(float(i))
    trade = TradeEngine(risk, connector, dal)
    bootstrap = BootstrapCoordinator()

    class DummyAssets(AssetService):
        def refresh(self):
            return self.list_assets()

    assets = DummyAssets(dal)
    assets.dal.save_assets([{"symbol": "SOL"}])
    app = create_app(cfg, lm, risk, trade, assets, bootstrap)
    with TestClient(app) as client:
        resp = client.get("/chart/portfolio?limit=5")
        assert resp.status_code == 200
        series = resp.json()["series"]
        assert len(series) == 5
        assert series[0][1] == 0.0
        assert series[-1][1] == 19.0


def test_chart_portfolio_pagination():
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
    for i in range(20):
        risk.update_equity(float(i))
    trade = TradeEngine(risk, connector, dal)
    bootstrap = BootstrapCoordinator()

    class DummyAssets(AssetService):
        def refresh(self):
            return self.list_assets()

    assets = DummyAssets(dal)
    assets.dal.save_assets([{"symbol": "SOL"}])
    app = create_app(cfg, lm, risk, trade, assets, bootstrap)
    with TestClient(app) as client:
        page1 = client.get("/chart/portfolio?offset=0&limit=5").json()["series"]
        page2 = client.get("/chart/portfolio?offset=5&limit=5").json()["series"]
        assert [p[1] for p in page1] == [0.0, 1.0, 2.0, 3.0, 4.0]
        assert [p[1] for p in page2] == [5.0, 6.0, 7.0, 8.0, 9.0]


def test_chart_portfolio_cursor_pagination():
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
    risk.equity_history = deque(( (i, float(i)) for i in range(20) ), maxlen=10_000)
    trade = TradeEngine(risk, connector, dal)
    bootstrap = BootstrapCoordinator()

    class DummyAssets(AssetService):
        def refresh(self):
            return self.list_assets()

    assets = DummyAssets(dal)
    assets.dal.save_assets([{"symbol": "SOL"}])
    app = create_app(cfg, lm, risk, trade, assets, bootstrap)
    with TestClient(app) as client:
        series = client.get("/chart/portfolio?cursor=4&limit=5").json()["series"]
        assert [p[1] for p in series] == [5.0, 6.0, 7.0, 8.0, 9.0]


def test_chart_portfolio_invalid_limit():
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
    risk.update_equity(1.0)
    trade = TradeEngine(risk, connector, dal)
    bootstrap = BootstrapCoordinator()

    class DummyAssets(AssetService):
        def refresh(self):
            return self.list_assets()

    assets = DummyAssets(dal)
    assets.dal.save_assets([{ "symbol": "SOL" }])
    app = create_app(cfg, lm, risk, trade, assets, bootstrap)
    with TestClient(app) as client:
        resp = client.get("/chart/portfolio?limit=-1")
        assert resp.status_code == 400
        resp = client.get("/chart/portfolio?limit=1001")
        assert resp.status_code == 400


def test_chart_portfolio_start_after_end():
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
    for i in range(5):
        risk.update_equity(float(i))
    trade = TradeEngine(risk, connector, dal)
    bootstrap = BootstrapCoordinator()

    class DummyAssets(AssetService):
        def refresh(self):
            return self.list_assets()

    assets = DummyAssets(dal)
    assets.dal.save_assets([{ "symbol": "SOL" }])
    app = create_app(cfg, lm, risk, trade, assets, bootstrap)
    with TestClient(app) as client:
        resp = client.get("/chart/portfolio?start=10&end=5")
        assert resp.status_code == 400


def test_demo_defaults_sol_asset():
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

    class DemoLM:
        def license_mode(self, wallet: str) -> str:
            return "demo"

    lm = DemoLM()
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

    class DemoAssets(AssetService):
        def refresh(self):
            return self.list_assets()

    assets = DemoAssets(dal)
    assets.dal.save_assets([{ "symbol": "SOL" }])

    app = create_app(cfg, lm, risk, trade, assets, bootstrap)
    with TestClient(app) as client:
        state = client.get("/state").json()
        assert state["mode"] == "demo"
        assert state["paper"]["assets"] == ["SOL"]
        assert state["paper"]["capital"] == 1000.0

