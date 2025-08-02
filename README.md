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
* **Solana** – manages RPC and WebSocket connections. `EventStream` builds on the previous `SlotStreamer` and yields parsed events.
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

3. Run the event stream demo:

```bash
python -m src.main
```

This connects to the public Solana websocket and prints parsed `Event` objects. The default demo emits a placeholder event when run without a real RPC endpoint.
WARNING: No real events yet, use only for CLI smoke.

Ensure `src` is on your `PYTHONPATH` when running examples:

```bash
export PYTHONPATH=$(pwd)/src
```

4. Run the unit tests:

```bash
pytest -q
```

5. Start the local trading API server:

```bash
python -m src.server --wallet YOUR_WALLET --db-path ~/.solbot/state.db
```

This launches a FastAPI app on `http://127.0.0.1:8000` exposing endpoints for
paper trading and viewing positions. Orders and positions are persisted to the
SQLite database specified by `--db-path` so the UI remains available offline.
The `/status` endpoint reports bootstrap progress and `/version` returns the
running git commit and schema hash.

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
or the `WALLET_ADDR` environment variable. The mint and authority addresses are
configured via environment variables:

```bash
export LICENSE_MINT=<FULL_LICENSE_MINT>
export DEMO_MINT=<DEMO_LICENSE_MINT>
export LICENSE_AUTHORITY=<ISSUER_PUBLIC_KEY>
export LICENSE_KEYPAIR_PATH=/secure/location/authority.json.enc
export LICENSE_KEYPAIR_KEY=<BASE64_FERNET_KEY>
```

If the wallet contains `LICENSE_MINT` the bot runs in full mode. Holding only
`DEMO_MINT` enables read-only demo mode.

```bash
python -m src.main --wallet YOUR_WALLET --rpc-ws wss://api.mainnet-beta.solana.com/
```

If no license token is detected the program exits with a message. A legacy
command line distributor exists for internal automation but is **deprecated**
and not documented publicly.

### License Issuer Service

For production deployments a dedicated **License Issuer** service handles token
distribution so that private keys never reside on developer machines. The
service exposes a single authenticated endpoint:

```http
POST /issue
Authorization: Bearer <JWT>
{
  "wallet": "DEST_WALLET",
  "demo": false
}
```

Requests must supply a short-lived JWT issued by the corporate identity
provider. The encrypted authority keypair is loaded on demand and wiped from
memory after signing.

## Operations

Deployment and operational procedures are documented internally. Contact the Security/DevOps team for access.
## Agent Workflow

All contributors (human or AI) must document their actions in `AGENTS.md`. Each commit should reference the section describing the work performed. Continuous integration runs lint and tests on push.

## FAQ

**Q:** Why combine Python and Rust?

**A:** Python offers rapid development for strategy logic, while Rust provides deterministic performance for core data parsing.


## License

This project is proprietary software. All rights reserved. Usage of the source code is governed by the terms in the `LICENSE` file. Contact the authors for commercial licensing options.

\nBuild a deterministic image with:\n```bash\ndocker build --build-arg COMMIT_SHA=$(git rev-parse HEAD) --build-arg SCHEMA_HASH=$(python -m solbot.schema) -t solbot:latest .\n```
