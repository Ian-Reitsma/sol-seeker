"""Entry point for sol-bot orchestration."""

import logging

from solbot.solana import data
from solbot.engine import (
    PosteriorEngine,
    RiskManager,
    PyFeatureEngine,
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
    fe = PyFeatureEngine()

    for event in streamer.stream_events():
        vec = fe.update(event, slot=int(event.ts))
        features = vec[: posterior.n_features]
        post = posterior.predict(features)
        print(f"event {event.kind.name}: trend={post.trend:.2f}")
        risk.update_equity(risk.equity + 0.0)  # placeholder for real P&L tracking


if __name__ == "__main__":
    main()
