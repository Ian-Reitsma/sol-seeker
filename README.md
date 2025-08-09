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
* **Solana** – manages RPC and WebSocket connections. `EventStream` subscribes to program logs and yields parsed events.
* **Rustcore** – placeholder for performance-critical parsing routines compiled from Rust.

## Recent Updates

The current iteration introduces a configurable backtesting pipeline and major dashboard improvements:

- **Backtesting API:** A new `/backtest` endpoint spins up a temporary `TradeEngine` and executes historical simulations against CSV data. The request accepts fee, slippage, and starting capital parameters, returning PnL, drawdown, and Sharpe metrics.
- **Dashboard Enhancements:** Settings now auto-save with a transient “Saving…” indicator, disabled controls, and toast notifications on failure. WebSocket reconnect logic tracks attempts per endpoint with exponential backoff, and polling/websocket connections pause when the tab is hidden. The positions list diffs DOM nodes to minimise reflows.

### Next Steps for Contributors

1. **Test Coverage:** Add unit tests for the new `/backtest` route and front‑end helpers. Ensure the web client has a working Jest setup so `npm test` passes.
2. **Backtest UX:** Persist recent backtest configurations and surface runtime errors to the UI. Consider streaming progress for long simulations.
3. **Resilience:** Harden auto‑save and reconnection routines with retry limits and user feedback when the server remains unreachable.
4. **Performance:** Profile the DOM diffing and WebSocket reconnection paths under heavy load and document any bottlenecks.

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

This connects to the public Solana websocket and prints parsed `Event` objects. By
default it listens for generic swap and liquidity logs; provide specific program
IDs via command line for targeted streams.

4. Run the unit tests:

```bash
pytest -q
```

5. Start the local trading API server:

```bash
python -m src.server --wallet YOUR_WALLET --db-path ~/.solbot/state.db
```

The entrypoint automatically adds ``src`` to ``PYTHONPATH`` so no extra setup is
required. The server launches a FastAPI app on `http://127.0.0.1:8000` exposing
JSON endpoints for dashboards and paper trading. Orders and positions are
persisted to the SQLite database specified by `--db-path` so the UI remains
available offline. If ``YOUR_WALLET`` matches the ``LICENSE_AUTHORITY``
environment variable, the server starts without requiring a license token. Demo
wallets still start but emit a warning that trading is disabled. The `/status`
endpoint reports bootstrap progress and `/version` returns the running git
commit and schema hash.

### Dashboard API

Front-end clients interact with the server via JSON resources and WebSocket feeds. Every dashboard control should communicate with these endpoints so the UI always reflects backend state:

* `GET /` – resource index with a map of endpoints, TradingView template URL, timestamp, and schema hash
* `GET /features` – latest normalized feature vector with timestamp
* `GET /posterior` – most recent posterior probabilities over market regimes with timestamp
* `GET /license` – license status for the configured wallet
* `GET /state` – combined license mode and bootstrap status
* `POST /state` – update runtime trading state (start/pause trading, emergency stop, and custom settings)
* `GET /positions` – open positions *(requires `X-API-Key` header)*
* `POST /orders` – place paper trade order *(requires `X-API-Key` header)*
* `GET /orders` – list recent orders, optionally filtered by `status` (`open` or `closed`) *(requires `X-API-Key` header)*
* `GET /features/schema` – mapping of feature indices to names with schema hash and timestamp metadata
* `GET /dashboard` – consolidated view containing the latest feature vector, posterior probabilities, open positions, open orders, risk metrics, and timestamp
* `GET /chart/{symbol}` – price history points or a TradingView URL for embedding charts
* `GET /manifest` – machine-readable listing of REST and WebSocket routes with version and timestamp
* `GET /tv` – simple TradingView iframe for manual inspection
* `WS /ws` – streams newly executed orders and closures in real time *(requires `X-API-Key` header; legacy alias: `/orders/ws`)*
* `WS /features/ws` – streams objects with `event` metadata and associated `features` array
* `WS /posterior/ws` – streams posterior probability updates alongside event metadata
* `WS /positions/ws` – streams position snapshots after each order *(requires `X-API-Key` header)*
* `WS /dashboard/ws` – streams combined dashboard updates with features, posterior, positions, orders, risk metrics, and timestamp whenever new events arrive *(requires `X-API-Key` header)*

The dashboard derives open-position metrics and position‑detail modals by fetching `/positions` and listening on `/positions/ws`, while the trading feed and History tab stream new executions and closures from `/ws` and load past trades via `/orders?status=closed`.
Users may configure the API base URL and API key in the settings panel; these values are stored in local storage and appended to all REST and WebSocket requests.

Example usage:

```bash
# fetch latest feature vector
curl http://127.0.0.1:8000/features

# fetch posterior probabilities
curl http://127.0.0.1:8000/posterior

# list open positions (API key required)
curl -H "X-API-Key: $API_KEY" http://127.0.0.1:8000/positions

# place paper trade order (API key required)
curl -X POST -H "Content-Type: application/json" -H "X-API-Key: $API_KEY" \
  -d '{"token":"SOL","qty":1,"side":"buy"}' http://127.0.0.1:8000/orders

# check license status
curl http://127.0.0.1:8000/license

# fetch combined state snapshot
curl http://127.0.0.1:8000/state

# pause trading
curl -X POST -H "Content-Type: application/json" -d '{"running":false}' http://127.0.0.1:8000/state

# fetch price chart or TradingView URL for SOL
curl http://127.0.0.1:8000/chart/SOL

# trigger emergency stop
curl -X POST -H "Content-Type: application/json" -d '{"emergency_stop":true}' http://127.0.0.1:8000/state

# fetch combined dashboard snapshot
curl http://127.0.0.1:8000/dashboard

# stream dashboard updates
websocat -H "X-API-Key: $API_KEY" ws://127.0.0.1:8000/dashboard/ws

# stream position updates
websocat -H "X-API-Key: $API_KEY" ws://127.0.0.1:8000/positions/ws

# stream order updates
websocat -H "X-API-Key: $API_KEY" ws://127.0.0.1:8000/ws
```

Example responses:

```json
// GET /license
{"wallet":"11111111111111111111111111111111","mode":"full","timestamp":1697040000}

// GET /state
{
  "running": true,
  "emergency_stop": false,
  "settings": {},
  "license": {"wallet":"11111111111111111111111111111111","mode":"full","timestamp":1697040000},
  "status": {"state":"RUNNING"},
  "timestamp": 1697040000
}

// GET /dashboard
{
  "features": [0.0, 1.2, 0.3, ...],
  "posterior": {"rug":0.05,"trend":0.7,"revert":0.2,"chop":0.05},
  "positions": {"SOL":{"qty":1,"px":10.0}},
  "orders": [{"id":1,"token":"SOL","quantity":1,"side":"buy","price":10.0,"slippage":0.1,"fee":0.01,"timestamp":1697040000,"status":"closed"}],
  "risk": {"equity":1000.0,"unrealized":0.0,"drawdown":0.0},
  "timestamp": 1697040000
}

// WS /dashboard/ws message
{
  "event": {"slot":123,"kind":1},
  "features": [0.0, 1.2, 0.3, ...],
  "posterior": {"rug":0.05,"trend":0.7,"revert":0.2,"chop":0.05},
  "positions": {"SOL":{"qty":1,"px":10.0}},
  "orders": [{"id":1,"token":"SOL","quantity":1,"side":"buy","price":10.0,"slippage":0.1,"fee":0.01,"timestamp":1697040000,"status":"closed"}],
  "risk": {"equity":1000.0,"unrealized":0.0,"drawdown":0.0},
  "timestamp": 1697040000
}
```

## Configuration

Command line options control connection URLs and logging levels. Example:

```bash
python -m src.main --rpc-ws wss://my.rpc/ws --log-level INFO
```

Environment variables with the same name override defaults. See `--help` for all options.
```


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

## Feature Engine

The `sol_seeker.features.FeatureEngine` module provides a deterministic,
lag-stacked 256‑dimensional state vector used by the posterior model. Events
are pushed one-by-one via ``push_event`` and at each slot boundary
``on_slot_end`` returns a ``memoryview`` of 768 ``float32`` values
corresponding to the current slot and two lags. The Rust core maintains running
means and variances using an exponential-weighted moving average (EWMA)
Welford update with population semantics (λ=0.995) for normalized features.

To build the extension and run tests:

```bash
pip install maturin
cd rustcore && maturin develop --release
cd .. && pytest -q
```

The initial spec implements nine high-impact features; remaining slots are
tombstoned to preserve index stability. Additional features can be added by
extending ``spec.py`` and registering the corresponding Rust functor.

### Active Features

The project begins with a small subset of six normalized features derived from
DEX events. Each feature occupies a fixed index in the 256‑dimensional vector
and is z-score normalised via the exponentially decaying Welford update.

| Index | Name               | Event Kinds                         | Units     |
|------:|-------------------|-------------------------------------|-----------|
| 0     | `liquidity_delta`  | `ADD_LIQUIDITY`, `REMOVE_LIQUIDITY` | token     |
| 1     | `log_cum_liquidity`| `ADD_LIQUIDITY`, `REMOVE_LIQUIDITY` | log_token |
| 2     | `signed_volume`    | `SWAP`                              | token     |
| 3     | `abs_volume`       | `SWAP`                              | token     |
| 4     | `swap_frequency`   | `SWAP`                              | per_ms    |
| 5     | `minted_amount`    | `MINT`                              | token     |

Normalization: all features use z-score normalization with λ=0.995 and ε=1e‑8.

