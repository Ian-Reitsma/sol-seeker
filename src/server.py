"""Run the sol-bot trading API server."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))

import uvicorn

from solbot.utils import parse_args, BotConfig, LicenseManager
from solbot.engine import RiskManager, TradeEngine, PyFeatureEngine, PosteriorEngine
from solbot.server import create_app
from solbot.persistence import DAL
from solbot.persistence.assets import AssetService
from solbot.exchange import PaperConnector
from solbot.oracle import CoingeckoOracle
from solbot.bootstrap import BootstrapCoordinator
from solbot.utils.syschecks import check_ntp, disk_iops_test


def main() -> None:
    args = parse_args()
    cfg = BotConfig.from_args(args)
    lm = LicenseManager(rpc_http=cfg.rpc_ws.replace("wss://", "https://"))
    check_ntp()
    disk_iops_test(cfg.db_path + ".tmp")
    dal = DAL(cfg.db_path)
    oracle = CoingeckoOracle(dal)
    connector = PaperConnector(dal, oracle)
    risk = RiskManager()
    trade = TradeEngine(risk, connector, dal)
    features = PyFeatureEngine()
    posterior = PosteriorEngine(n_features=features.dim)
    assets = AssetService(dal)
    bootstrap = BootstrapCoordinator()

    app = create_app(cfg, lm, risk, trade, assets, bootstrap, features, posterior)
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
