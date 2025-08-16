import tempfile
from fastapi.testclient import TestClient

import tempfile
from fastapi.testclient import TestClient

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
    return app


def test_strategy_matrix_endpoint():
    app = build_app()
    with TestClient(app) as client:
        resp = client.get("/strategy/matrix")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert data and "name" in data[0]
