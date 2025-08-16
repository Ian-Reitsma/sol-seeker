from fastapi.testclient import TestClient

from src.solbot.risk import RugDetector
from solbot.utils import BotConfig
from solbot.engine import RiskManager, TradeEngine, PyFeatureEngine, PosteriorEngine
from solbot.server import create_app
from solbot.persistence import DAL
from solbot.persistence.assets import AssetService
from solbot.exchange import PaperConnector
from solbot.oracle.coingecko import PriceOracle
from solbot.bootstrap import BootstrapCoordinator


class DummyLM:
    def license_mode(self, wallet: str) -> str:
        return "full"


class DummyOracle(PriceOracle):
    async def price(self, token: str) -> float:  # type: ignore[override]
        return 1.0

    async def volume(self, token: str) -> float:  # type: ignore[override]
        return 0.0


def build_app():
    cfg = BotConfig(
        rpc_ws="ws://localhost:8900",
        rpc_http="http://localhost:8900",
        log_level="INFO",
        wallet="111",
        db_path=":memory:",
        bootstrap=False,
    )
    lm = DummyLM()
    dal = DAL(cfg.db_path)
    oracle = DummyOracle()
    connector = PaperConnector(dal, oracle)
    risk = RiskManager()
    trade = TradeEngine(risk, connector, dal)
    fe = PyFeatureEngine()
    posterior = PosteriorEngine(n_features=fe.dim)
    assets = AssetService(dal)
    bootstrap = BootstrapCoordinator()
    app = create_app(cfg, lm, risk, trade, assets, bootstrap, fe, posterior)
    return app


def test_rug_detector_logic():
    det = RugDetector()
    det.update({"token": "RUG", "liquidity_removed": 0.8})
    det.update({"token": "SAFE", "liquidity_removed": 0.1})
    det.update({"token": "OWNER", "owner_withdraw": True})
    det.update({"token": "MINT", "mint_paused": True})
    tokens = {a.token for a in det.alerts()}
    assert tokens == {"RUG", "OWNER", "MINT"}


def test_risk_rug_endpoint():
    app = build_app()
    with TestClient(app) as client:
        # Initially no alerts
        resp = client.get("/risk/rug")
        assert resp.status_code == 200
        assert resp.json()["alerts"] == []
        # Simulate suspicious event
        app.state.rug_detector.update({"token": "XYZ", "liquidity_removed": 0.9})  # type: ignore
        resp = client.get("/risk/rug")
        data = resp.json()
        assert data["alerts"][0]["token"] == "XYZ"
