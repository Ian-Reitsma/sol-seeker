"""Entry point for sol-bot orchestration."""

import logging

from solbot.solana import data
from solbot.engine import PosteriorEngine, RiskManager
from solbot.utils import (
    parse_args,
    BotConfig,
    LicenseManager,
    LICENSE_MINT,
)


def main() -> None:
    """Run the main event loop with basic orchestration."""
    args = parse_args()
    cfg = BotConfig.from_args(args)
    logging.basicConfig(level=getattr(logging, cfg.log_level.upper(), logging.INFO))

    lm = LicenseManager(rpc_http=cfg.rpc_ws.replace("wss://", "https://"))
    if not cfg.wallet or not lm.has_license(cfg.wallet):
        print(
            "License check failed. Provide a valid wallet with a license token."
        )
        return

    streamer = data.SlotStreamer(cfg.rpc_ws)
    posterior = PosteriorEngine()
    risk = RiskManager()

    for slot in streamer.stream_slots():
        features = [1.0] * posterior.n_features
        post = posterior.predict(features)
        print(f"slot {slot}: trend={post.trend:.2f}")
        risk.update_equity(risk.equity + 0.0)  # placeholder for real P&L tracking


if __name__ == "__main__":
    main()
