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
import time

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
from solbot.scanner.launch import TokenLaunchScanner
from solbot.risk.rug_detector import RugDetector


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
    model_dir = Path.home() / ".solbot" / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    posterior_path = model_dir / "posterior.npz"
    features_path = model_dir / "features.npz"

    if posterior_path.exists():
        posterior = PosteriorEngine.load(posterior_path)
    else:
        posterior = PosteriorEngine()
    if features_path.exists():
        fe = PyFeatureEngine()
        try:
            fe.load(features_path)
        except Exception:
            pass
    else:
        fe = PyFeatureEngine()

    risk = RiskManager()
    strategy = Strategy(risk)
    scanner = TokenLaunchScanner()
    rug = RugDetector()

    if not cfg.auto_start:
        try:
            input("Press Enter to start engine...")
        except EOFError:
            return

    scanner.start()

    last_save = time.time()
    try:
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
            rug.update({"token": "SOL", "liquidity_removed": 0.0})
            if time.time() - last_save > 300:
                posterior.save(posterior_path)
                fe.save(features_path)
                last_save = time.time()
    finally:
        import asyncio
        asyncio.run(scanner.stop())
        try:
            posterior.save(posterior_path)
            fe.save(features_path)
        except Exception:
            pass


if __name__ == "__main__":
    main()
