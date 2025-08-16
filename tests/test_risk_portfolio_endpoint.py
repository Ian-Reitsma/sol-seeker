import tempfile
from fastapi.testclient import TestClient

from solbot.utils import BotConfig
from solbot.engine import RiskManager, TradeEngine, PyFeatureEngine, PosteriorEngine
from solbot.server import create_app
import solbot.server.api as api_module
from solbot.persistence import DAL
from solbot.persistence.assets import AssetService
from solbot.exchange import PaperConnector
from solbot.oracle.coingecko import PriceOracle
from solbot.bootstrap import BootstrapCoordinator
from prometheus_client import REGISTRY


def _clear_registry() -> None:
    for collector in list(REGISTRY._collector_to_names.keys()):
        try:
            REGISTRY.unregister(collector)
        except KeyError:
            pass


class DummyLM:
    def license_mode(self, wallet: str) -> str:
        return "full"


class DummyOracle(PriceOracle):
    async def price(self, token: str) -> float:  # type: ignore[override]
        return 1.0

    async def volume(self, token: str) -> float:  # type: ignore[override]
        return 0.0


def build_app():
    _clear_registry()
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
    oracle = DummyOracle()
    connector = PaperConnector(dal, oracle)
    risk = RiskManager()
    trade = TradeEngine(risk, connector, dal)
    fe = PyFeatureEngine()
    posterior = PosteriorEngine(n_features=fe.dim)
    assets = AssetService(dal)
    bootstrap = BootstrapCoordinator()
    app = create_app(cfg, lm, risk, trade, assets, bootstrap, fe, posterior)
    api_module.oracle = connector.oracle
    return app, risk


def test_risk_portfolio_endpoint():
    app, risk = build_app()
    risk.update_equity(100.0)
    with TestClient(app) as client:
        resp = client.get("/risk/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert {"drawdown", "max_drawdown", "leverage", "exposure"} <= data.keys()


def test_risk_portfolio_exposure_ratio():
    app, risk = build_app()
    risk.update_equity(100.0)
    risk.add_position("SOL", qty=1.0, price=10.0)
    risk.update_equity(100.0)
    with TestClient(app) as client:
        resp = client.get("/risk/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        expected = risk.total_exposure() / risk.equity
        assert data["exposure"] == expected
