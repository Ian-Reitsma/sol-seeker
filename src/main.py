"""Entry point for sol-bot orchestration.

This is the lightweight CLI runner used primarily during development.
TODO[AGENTS-AUDIT §8]: Replace placeholder strategy loop with full engine that
ingests all Solana token launches, applies rug checks, and feeds a learning
model that persists across sessions.
TODO[AGENTS-AUDIT §1]: Ensure the engine starts in a paused state and only
processes trades after `/state` or dashboard toggle triggers a start event.
"""

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

    lm = LicenseManager(rpc_http=cfg.rpc_http)
    if not cfg.wallet:
        print("--wallet is required")
        return
    mode = lm.verify_or_exit(cfg.wallet)
    if mode == "demo":
        logging.warning("Demo mode active: trading disabled")
    # TODO[AGENTS-AUDIT §3]: when running headless, respect demo/live mode and
    # starting capital from settings; wire to `/state` endpoint.

    streamer = data.EventStream(cfg.rpc_ws)
    posterior = PosteriorEngine()
    risk = RiskManager()
    strategy = Strategy(risk)
    fe = PyFeatureEngine()
    # TODO[AGENTS-AUDIT §8]: persist `fe` and `posterior` state to disk so
    # learning continues between sessions; reload on startup.

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
        # TODO[AGENTS-AUDIT §8]: capture outcome of each action for RL reward and
        # periodically save model checkpoints.


if __name__ == "__main__":
    main()
