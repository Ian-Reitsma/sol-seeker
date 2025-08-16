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


class DummyOracle(PriceOracle):
    async def price(self, token: str) -> float:  # type: ignore[override]
        return 25.0

    async def volume(self, token: str) -> float:  # type: ignore[override]
        return 0.0


class DummyLM:
    def license_mode(self, wallet: str) -> str:
        return "full"


def _clear_registry() -> None:
    for collector in list(REGISTRY._collector_to_names.keys()):
        try:
            REGISTRY.unregister(collector)
        except KeyError:
            pass


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
    dal = DAL(cfg.db_path)
    oracle = DummyOracle()
    connector = PaperConnector(dal, oracle)
    risk = RiskManager()
    trade = TradeEngine(risk, connector, dal)
    fe = PyFeatureEngine()
    posterior = PosteriorEngine(n_features=fe.dim)
    assets = AssetService(dal)
    bootstrap = BootstrapCoordinator()
    lm = DummyLM()
    app = create_app(cfg, lm, risk, trade, assets, bootstrap, fe, posterior)
    api_module.oracle = connector.oracle
    return app


def test_strategy_performance_periods():
    app = build_app()
    with TestClient(app) as client:
        r7 = client.get("/strategy/performance?period=7d")
        r30 = client.get("/strategy/performance?period=30d")
        assert r7.status_code == 200 and r30.status_code == 200
        data7 = r7.json()
        data30 = r30.json()
        assert data7 != data30
        assert all("name" in s and "pnl" in s for s in data7)
