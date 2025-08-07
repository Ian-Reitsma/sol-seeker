"""Entry point for sol-bot orchestration."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))

import logging

from solbot.solana import data
from solbot.engine import (
    PosteriorEngine,
    RiskManager,
    PyFeatureEngine,
    Strategy,
)
from solbot.utils import (
    parse_args,
    BotConfig,
    LicenseManager,
)


def main() -> None:
    """Run the main event loop with basic orchestration."""
    args = parse_args()
    cfg = BotConfig.from_args(args)
    logging.basicConfig(level=getattr(logging, cfg.log_level.upper(), logging.INFO))

    lm = LicenseManager(rpc_http=cfg.rpc_ws.replace("wss://", "https://"))
    if not cfg.wallet:
        print("--wallet is required")
        return
    mode = lm.verify_or_exit(cfg.wallet)
    if mode == "demo":
        logging.warning("Demo mode active: trading disabled")

    streamer = data.EventStream(cfg.rpc_ws)
    posterior = PosteriorEngine()
    risk = RiskManager()
    strategy = Strategy(risk)
    fe = PyFeatureEngine()

    for event in streamer.stream_events():
        vec = fe.update(event, slot=int(event.ts))
        features = vec[: posterior.n_features]
        post = posterior.predict(features)
        fee = 0.001  # placeholder fee estimate
        equity = risk.portfolio_value() or 0.0
        signal = strategy.evaluate(post, fee, equity)
        if signal:
            print(f"event {event.kind.name}: edge={signal.edge:.3f} qty={signal.qty:.3f}")
            risk.add_position("SOL", signal.qty, 1.0)
        strategy.check_exit("SOL", 1.0)


if __name__ == "__main__":
    main()
