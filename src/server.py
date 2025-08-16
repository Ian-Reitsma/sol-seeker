"""Run the sol-bot trading API server.

This entrypoint boots the HTTP and WebSocket API used by the dashboard.

TODO[AGENTS-AUDIT §8]: Extend server init so the engine **never** auto-starts
trading; require explicit `/state` POST to begin processing. Persist any
machine-learning state to disk so a restart resumes with prior knowledge.
TODO[AGENTS-AUDIT §8]: Add chain-wide memecoin watcher that subscribes to new
token launches and on-chain transactions to feed the listing sniper and rug
protection modules.
"""

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
    lm = LicenseManager(rpc_http=cfg.rpc_http)
    check_ntp()
    disk_iops_test(cfg.db_path + ".tmp")
    # TODO[AGENTS-AUDIT §7]: expose system health metrics (uptime, CPU, RAM, RPC latency, WS status)
    # via `/metrics` so settings can diagnose high CPU (204%), 1.2 GB memory and latency stalls.
    dal = DAL(cfg.db_path)
    oracle = CoingeckoOracle(dal)
    connector = PaperConnector(dal, oracle)
    risk = RiskManager()
    trade = TradeEngine(risk, connector, dal)
    features = PyFeatureEngine()
    posterior = PosteriorEngine(n_features=features.dim)
    # TODO[AGENTS-AUDIT §8]: Plug in persistent RL/ML model that updates with
    # every new block; allow pluggable model path via config.
    assets = AssetService(dal)
    bootstrap = BootstrapCoordinator()

    app = create_app(cfg, lm, risk, trade, assets, bootstrap, features, posterior)
    # TODO[AGENTS-AUDIT §6]: ensure backtest websocket tasks shut down cleanly so
    # terminal prompt returns without manual kill.
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
