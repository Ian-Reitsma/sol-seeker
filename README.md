# sol-bot

Sol-bot is a modular, multi-agent trading engine for Solana designed for high-frequency trading and on-chain fraud detection. The project is structured to support future extensions such as smart contracts, machine learning, and distributed agent collaboration.

## Architecture Overview

```
sol-bot/
├── src/
│   ├── main.py          # top-level entrypoint
│   ├── engine/          # trading and inference engine
│   ├── solana/          # blockchain data interfaces
│   ├── utils/           # helper utilities
│   └── rustcore/        # performance-critical Rust code
├── tests/               # unit tests
├── scripts/             # helper scripts
├── notebooks/           # research notebooks
└── .github/workflows/   # CI configuration
```

### Components
* **Engine** – orchestrates trading logic, risk management, and posterior inference. Includes a `PosteriorEngine` stub and a `RiskManager` that tracks drawdown.
* **Solana** – manages RPC and WebSocket connections. The `SlotStreamer` demonstrates live event ingestion with automatic reconnect.
* **Rustcore** – placeholder for performance-critical parsing routines compiled from Rust.

## Quickstart

1. Create and activate a Python virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Install Node dependencies (for future TypeScript modules):

```bash
npm install
```

3. Run the basic slot streamer:

```bash
python -m src.main
```

This will connect to the public Solana websocket and print slot numbers as they arrive.

Ensure `src` is on your `PYTHONPATH` when running examples:

```bash
export PYTHONPATH=$(pwd)/src
```

4. Run the unit tests:

```bash
pytest -q
```

## Configuration

Command line options control connection URLs and logging levels. Example:

```bash
python -m src.main --rpc-ws wss://my.rpc/ws --log-level INFO
```

Environment variables with the same name override defaults. See `--help` for all options.
```

### License Verification

Before full functionality is enabled the bot verifies that your wallet holds a
valid license token on Solana. Provide your wallet public key with `--wallet`
or the `WALLET_ADDR` environment variable. The default mint and authority
addresses are placeholders in `solbot.utils.license` and must be updated by the
project owner.

```bash
python -m src.main --wallet YOUR_WALLET --rpc-ws wss://api.mainnet-beta.solana.com/
```

If no license token is detected the program exits with a message. A minimal
license distributor is included to send license tokens from the authority
wallet.

## Agent Workflow

All contributors (human or AI) must document their actions in `AGENTS.md`. Each commit should reference the section describing the work performed. Continuous integration runs lint and tests on push.

## FAQ

**Q:** Why combine Python and Rust?

**A:** Python offers rapid development for strategy logic, while Rust provides deterministic performance for core data parsing.


## License

This project is proprietary software. All rights reserved. Usage of the source code is governed by the terms in the `LICENSE` file. Contact the authors for commercial licensing options.

