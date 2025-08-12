# AGENTS AUDIT

This file defines the immediate and near-term directives for the next development agent. The items are ordered by criticality and expected impact. Implement each item completely before moving to the next.

## Recent Accomplishment – Analytics Expansion and Security Panel Wiring (2025-08-07)

### Summary
- Introduced `StrategyStat` and `ArbitrageStat` models with `/strategies` and `/arbitrage` endpoints returning deterministic demo metrics and registering both routes in the service map.
- Added sentiment and news analytics via `/sentiment/trending`, `/sentiment/influencers`, `/sentiment/pulse`, and `/news`, each backed by Pydantic models and advertised for dashboard discovery.
- Exposed security flag elements (`#rugPull`, `#liquidity`, `#contractVerified`, `#holderDistribution`, `#tradingPatterns`) in the dashboard and updated the renderer to fetch `/risk/security`, renaming the prior market liquidity stat to avoid ID collisions.
- Expanded server tests to cover all new analytics routes and assert service-map exposure; added a Jest unit test verifying the WebSocket reconnect ceiling halts retries.

## Recent Accomplishment – Backtest Endpoint and Dashboard Enhancements (2025-08-07)

### Summary
- Added a configurable backtesting pipeline (`BacktestConfig`, `run_backtest`) and exposed a `/backtest` API route.
- Wired the dashboard with a backtest form, metrics card, auto-saving settings with toast errors, endpoint-specific WebSocket reconnects, and DOM-diffed position rendering.

### Next Agent Objectives
1. **Testing Infrastructure**
   - Implement unit and integration tests for `run_backtest`, `/backtest`, and front-end helpers. Set up Jest so `npm test` executes.
   - Add error-path tests for autosave and WebSocket reconnection logic.
   <!-- Progress: Extended `tests/test_server.py` to cover `/risk/security`, `/whales`, `/smart-money-flow`, `/strategies`, `/arbitrage`, `/sentiment/trending`, `/sentiment/influencers`, `/sentiment/pulse`, and `/news` endpoints while asserting service-map entries. Added Jest `ws_reconnect.test.ts` to confirm reconnect ceiling behavior. Autosave and reconnect error-path tests remain todo. -->
2. **Backtest UX & Persistence**
   - Persist API credentials and backtest parameters in local storage with validation and clear error messages.
   - Stream backtest progress and support cancellation for long jobs; handle and surface backend errors.
   <!-- Completed: Dashboard validates API base URL and key, restores both along with last backtest params from `localStorage`, and refuses submission until client-side schema checks pass. Missing CSV sources now raise HTTP 404 for clarity. Streaming/cancellation still pending. -->
3. **Resilience & Performance**
   - Enforce reconnect attempt limits with user notifications when an endpoint remains unreachable.
   - Profile DOM diffing and reconnection code under heavy update rates; document bottlenecks and propose optimizations.
   <!-- Completed: WebSocket manager tracks per-endpoint reconnect counts, logs attempts, and emits a toast after exceeding the ceiling before halting retries; Jest test `ws_reconnect.test.ts` exercises repeated failures to confirm the limit. Performance profiling not yet started. -->

## Recent Accomplishment – Demo Mode Toggle and Equity Chart (2025-08-09)

### Summary
- Enabled switching between live and demo trading modes with persistent paper assets and capital via `/state`.
- Blocked order placement in demo mode and reset risk state when toggling to paper trading.
- Implemented `/chart/portfolio` backed by `RiskManager.equity_history` and added websocket-driven `/backtest/ws/{id}` progress stream.
- Expanded tests to cover state transitions, portfolio chart, and backtest progress.

### Next Agent Objectives
- Replace simulated backtest data with real strategy execution and support cancellation.
- Surface equity history limits and add pagination or downsampling for long sessions.

## Dashboard-API Connectivity Gaps
The static HTML dashboard in `web/public/dashboard.html` still presents demo data. Every element below must either consume a real
endpoint or be removed. Wire items **in place** rather than creating new components so future agents can diff easily. Always
inject the stored API key and `sol_seeker_api_base` when issuing requests. After implementing each sub‑task, verify with the
browser network panel or `curl` that the request returns 2xx and the DOM updates accordingly.

### 1. Core Controls & Status

1. **Trading toggle – `#tradingToggle` (lines ~100 & ~1989)**
   - **Endpoint:** `POST /state` with `{ running: boolean }`.
   - **UI:** Text and style swap between `▶ START` and `⏸ PAUSE`.
   - **Verification:** After POST, `GET /state` and confirm `running` matches. Update tooltip to show last transition time.
   <!-- Agent Notes (2025-08-09): Implemented trading toggle button wired to `/state`. Verifies state via `GET /state` and updates
   tooltip with last change timestamp. -->

2. **Emergency stop – `.emergency-stop` (lines ~115 & ~2519)**
   - **Endpoint:** `POST /state` with `{ running: false, emergency_stop: true }`.
   - **UI:** Button flashes red, then shows `✓ STOPPED` for 3 s. Trading toggle reset to `▶ START`.
   - **Verification:** `GET /positions` must return `{}`; new `/state` reads `running=false`.
   <!-- Agent Notes (2025-08-09): Emergency stop posts `{ running:false, emergency_stop:true }`, verifies positions cleared and
   temporarily shows ✓ STOPPED before restoring button. -->

3. **RPC latency indicator – add `id="rpcLatency"` to latency span (line ~89)**
   - **Endpoint:** `GET /health` every 5 s; use `health.rpc_latency_ms`.
   - **UI:** Replace hard-coded `12ms`; tooltip shows last sample timestamp.
   - **Verification:** Introduce console log on each poll; inspect network to ensure requests stop on tab visibility change.
   <!-- Completed: Poller now runs at 5 s intervals when tab visible, writes `rpc_latency_ms` into `#rpcLatency`, and logs each sample via `console.log('RPC latency sample:', latency)` for ops troubleshooting. -->

4. **WebSocket heartbeat – add `id="wsStatus"` (line ~96)**
   - **Endpoint:** `/dashboard/ws` heartbeat messages already contain `timestamp`.
   - **UI:** When no message for >10 s, show red dot and “DISCONNECTED”; on reconnect, restore cyan dot.
   - **Verification:** Throttle network to offline in DevTools and confirm indicator flips after timeout.

5. **System status & uptime – `#systemStatus`, `#systemUptime` (lines ~129–139)**
   - **Endpoint:** `GET /status` on load and every 30 s.
   - **UI:** Replace static “OK” and “99.97%” with `status.state` and `status.uptime_pct`.
   - **Verification:** Manually alter backend to return non‑OK and ensure card turns amber with tooltip `status.detail`.

### 2. Portfolio Metrics

1. **Portfolio value / change – `#portfolioValue`, `#portfolioChange` (lines ~142–154)**
   - **Endpoint:** `GET /dashboard` and `/dashboard/ws` (fields `risk.equity` & `risk.realized`).
   - **UI:** Show `risk.equity` as dollars, compute day change using previous snapshot.
   - **Verification:** Run `curl /dashboard` twice with altered risk values and ensure live websocket updates reflect changes.

2. **Realized P&L – `#realizedPnL`, `#realizedPnLChange` (lines ~160–171)**
   - **Endpoint:** Same `/dashboard` payload (`risk.realized` & `risk.sharpe`).
   - **UI:** `realizedPnL` shows cumulative realized; `realizedPnLChange` displays intraday delta and arrows.
   - **Verification:** Execute a mock order via `POST /orders` and confirm realized P&L updates in <1 s through websocket.

3. **Open positions – `#openPositionsTotal`, `#openPositionsActive`, `#openPositionsBreakdown` (lines ~173–187)**
   - **Endpoint:** `GET /positions` on load; subscribe to `/positions/ws` for changes.
   - **UI:** Total count, “N ACTIVE”, and `L LONG • S SHORT` breakdown derived from websocket payload.
   - **Verification:** Open and close demo positions; watch counts adjust and DOM diffing avoid full re-render.

4. **Backtest P&L card – `#backtestPnL`, `#backtestStats` (lines ~202–211 & script ~2470)**
   - **Endpoint:** `POST /backtest` via form; results returned as `{ pnl, drawdown, sharpe }`.
   - **UI:** Display metrics and persist last config to `localStorage.backtest_last`.
   - **Verification:** Run backtest with known seed; confirm numbers match API JSON.
   <!-- Completed: Client persists backtest parameters and API credentials, validates inputs before posting, and renders `{pnl, drawdown, sharpe}` from the `/backtest` response. File-missing errors surface as HTTP 404 with a toast message. -->

5. **Equity curve / P&L breakdown charts (lines ~304–357)**
   - **Endpoint:** `GET /chart/portfolio?tf=1H|4H|1D` or historical `/equity` route if available.
   - **UI:** Render chart via TradingView iframe when URL returned; fallback to `<canvas>` series from price array.
   - **Verification:** Cross-check first point in chart with `risk.equity` at matching timestamp.

### 3. Risk & Security Panels

Each card (rug pull, liquidity, contract verification, holder distribution, trading patterns, and portfolio risk metrics) lives
around lines ~220–330 and currently holds placeholder text.

1. **Risk metrics – `#maxDrawdown`, `#positionSize`, `#leverageRatio`, `#exposure`**
   - **Endpoint:** `GET /dashboard` `risk.drawdown`, `risk.position_size`, `risk.leverage`, `risk.exposure`.
   - **UI:** Replace hard-coded `-5.2%`, `OPTIMAL`, `2.1X`, `78%`.
   - **Verification:** Tweak backend risk manager values and ensure cards update via websocket.

2. **Security checks – `#rugPull`, `#liquidity`, `#contractVerified`, `#holderDistribution`, `#tradingPatterns`**
   - **Endpoint:** `GET /risk/security` (to be implemented) returning boolean flags with detail strings.
   - **UI:** Show ✓/⚠/✗ icons based on flag and tooltip with `detail`.
   - **Fallback:** If endpoint not available, hide entire section to avoid misleading “SAFE” labels.
   <!-- Completed: Dashboard exposes `#rugPull`, `#liquidity`, `#contractVerified`, `#holderDistribution`, and `#tradingPatterns` IDs and `renderSecurityReport()` fetches `/risk/security` to populate status and detail; previous market liquidity stat renamed to `#marketLiquidity` to avoid ID conflicts. -->

### 4. Analytics & Strategy Modules

Widgets from “Whale Tracker” through “MEV Shield & Alpha Signals” appear between lines ~360–640 and are fully static.

1. **Whale tracker / smart money flow / copy trading**
   - **Endpoint:** Design `/whales` providing `{ following, success_rate, copied_today, profit }` and `/smart-money-flow` for net inflow.
   - **UI:** Map fields to `#following`, `#successRate`, etc. Provide loading spinners until data arrives.
   - **Verification:** Call endpoints with mock data; ensure numbers disappear when API returns 503.
   <!-- Completed: Added Pydantic models (`WhaleStats`, `SmartMoneyFlow`, `CopyTrade`) with demo data and exposed `/whales`, `/smart-money-flow`, and `/copy-trading`. Dashboard panel now shows spinners, fetches all three routes in parallel, and clears fields or displays "DATA UNAVAILABLE" on failure. -->

2. **Neural strategy matrix & arbitrage modules**
   - **Endpoint:** `/strategies` delivering per-strategy `{ trades, pnl, confidence, targets, success }`.
   - **UI:** Build rows dynamically; hide card if array empty.
   - **Verification:** Add console assertion that strategies length matches row count rendered.

   <!-- Server endpoints implemented: `/strategies` and `/arbitrage` return demo `StrategyStat` and `ArbitrageStat` arrays and are advertised in the service map. Dashboard wiring not yet started. -->

3. **Market maker / risk guardian / MEV shield / alpha signals / flash‑loan opportunities**
   - **Endpoint:** `/liquidity`, `/risk/guardian`, `/mev`, `/alpha`, `/flashloan` (to be defined).
   - **UI:** Replace text blocks with values from endpoints; include timestamp to show data freshness.
   - **Verification:** For each, simulate server downtime and ensure card displays “DATA UNAVAILABLE” rather than stale demo text.

4. **Neural trading feed – `#tradingFeed`, `#pauseFeed` (lines ~1174–1187)**
   - **Endpoint:** Subscribe to `/orders/ws` (include stored API key) and append `{ timestamp, token, qty, side, price, posterior, strategy }` events.
   - **UI:** Replace `#feedPlaceholder` with live rows; `#pauseFeed` toggles streaming and text swaps between “PAUSE” and “RESUME”.
   - **Verification:** Post demo orders and confirm feed updates in <1 s; pausing halts new messages until resumed.

### 5. Social & News Feeds

Sections “Social Sentiment Matrix”, “Influencer Alerts”, “Community Pulse”, “Trending Now”, and “Breaking News” occupy lines
~650–890 and reference `$NOVA` hard-codes.

1. **Trending tokens / sentiment**
   - **Endpoint:** `/sentiment/trending` returning array `{ symbol, mentions, change_pct, sentiment }`.
   - **UI:** Populate list; remove `$NOVA` defaults.
   - **Verification:** Ensure entries reorder when API results change; highlight negative sentiment in red.
   <!-- Server endpoint `/sentiment/trending` implemented with demo payload; UI list still static. -->

2. **Influencer alerts**
   - **Endpoint:** `/sentiment/influencers` giving `{ handle, message, followers, stance }`.
   - **UI:** Render avatars/handles dynamically; clicking opens source link.
   - **Verification:** Confirm no duplicates and stale rows purge after 1 h.
   <!-- Server endpoint `/sentiment/influencers` implemented; dashboard rendering and link handling remain TODO. -->

3. **Breaking news & community pulse**
   - **Endpoint:** `/news` for headline feed and `/sentiment/pulse` for fear/greed metrics.
   - **UI:** Replace static bullet list; store last seen article ID to avoid repeats.
   - **Verification:** Compare timestamps with backend to ensure chronology.
   <!-- `/news` and `/sentiment/pulse` endpoints added with demo data; front-end still uses placeholders. -->

4. **Upcoming catalysts – `#catalystList` (lines ~1122–1164)**
   - **Endpoint:** `GET /events/catalysts` returning `[ { name, eta, severity } ]`.
   - **UI:** Render rows with colored dots per severity and countdown timers; strip `$NOVA` demo entries.
   - **Verification:** Vary API payloads to ensure list refreshes every minute and clears when empty.

### 6. Backtesting & Optimisation Lab

1. **Run Test form – `#btRun` click handler (lines ~2340–2470)**
   - **Endpoint:** `POST /backtest` streaming progress via `/backtest/ws/{id}`.
   - **UI:** Disable form while running; show progress bar; on completion update results table and Monte Carlo chart.
   - **Verification:** Interrupt a long run to ensure cancellation logic closes WS and re-enables form.

2. **Parameter persistence**
   - **Storage:** `localStorage.backtest_params` with JSON `{ period, capital, strategy_weights }`.
   - **Verification:** Reload page and confirm fields repopulate; validate numeric ranges before POST.

3. **Strategy performance matrix & breakdown – `#strategyPerformance`, `#strategyBreakdown` (lines ~1369–1447)**
   - **Endpoint:** `GET /strategy/performance?period=7d|30d` for heatmap data and `/strategy/breakdown` returning `{ name, pnl, win_rate }`.
   - **UI:** Populate heatmap cells and strategy cards dynamically; highlight selected period button.
   - **Verification:** Toggle 7D/30D buttons and ensure network calls update DOM; card count matches array length.
   <!-- Agent Notes (2025-08-09): Implemented demo endpoints `/strategy/performance` and `/strategy/breakdown` with deterministic
   stats. Added Strategy Performance panel with 7D/30D toggles and live cards driven by these routes. Verified DOM updates and
   button styling reflect the selected period. -->

4. **Risk analytics panel – `#riskAnalytics` (lines ~1448–1469)**
   - **Endpoint:** `GET /strategy/risk` yielding `{ sharpe, max_drawdown, volatility, calmar }`.
   - **UI:** Replace static metrics; color negative drawdown in orange and hide panel on non-200.
   - **Verification:** Alter backend values and confirm updates propagate without reload.
   <!-- Agent Notes (2025-08-09): Added `/strategy/risk` endpoint returning fixed Sharpe, drawdown, volatility, and Calmar
   ratios. Dashboard renders these values in a dedicated Risk Analytics panel, defaulting to “DATA UNAVAILABLE” on request
   failure. -->

### 7. System Health & Settings

1. **Resource usage – `#cpuUsage`, `#memUsage`, `#netLatency` (lines ~1600–1665)**
   - **Endpoint:** `GET /metrics` exposing `{ cpu, memory, net_latency }`.
   - **UI:** Progress bars and labels use returned percentages.
   - **Verification:** Introduce artificial load on backend and watch bars rise; ensure poll stops on hidden tab.

2. **Module status – `#moduleDataFeed`, `#moduleInference`, `#moduleRisk`, `#moduleExecution` (lines ~1666–1755)**
   - **Endpoint:** `/status` fields `data_feed`, `inference_engine`, `risk_manager`, `trade_execution`.
   - **UI:** Green “OK”/amber “WARN”/red “DOWN”; tooltip with `status.detail`.
   - **Verification:** Toggle backend components and ensure cards update within 5 s.

3. **Configuration panel – inputs `#maxDrawdown`, `#maxPosition`, `#maxTrades`, `#sniperToggle`, `#arbToggle`, `#mmToggle`, `#failoverToggle`, `#rpcSelect` (lines ~1850–2140)**
   - **Endpoint:** `GET /state` on open; `POST /state` on save.
   - **UI:** Disable controls during `saveSettings` async call and show “Saving…” text.
   - **Verification:** After POST, re‑fetch `/state` and assert returned config matches form values.

4. **API base & key – inputs `#apiBaseInput`, `#apiKeyInput`**
   - **Storage:** `localStorage.sol_seeker_api_base` & `localStorage.sol_seeker_api_key`.
   - **Verification:** Clearing storage should force modal prompt; confirm requests include `Authorization: Bearer` header.

### 8. Debug Console

1. **Log feed – `#debugConsole` (lines ~1920 & script ~2370)**
   - **Endpoint:** `/logs/ws` streaming `{ level, timestamp, message }`.
   - **UI:** Append formatted lines; allow level filter via dropdown; “CLEAR” button purges DOM.
   - **Verification:** Trigger log events via backend; ensure console scrolls and truncates after 500 lines.

> After all modules are wired, run through the dashboard with network throttling and backend restarts to confirm graceful error
handling (spinners, toasts, reconnect loops) for every widget.

## 1. Core Data Ingestion and Feature Pipeline
1. Replace the placeholder slot-only stream with real on-chain event subscriptions.
   - Update `src/solbot/solana/data.py` to subscribe via WebSocket to program logs or account changes for DEX swaps, liquidity adds/removes, and token mint events.
   - Ensure reconnect and backoff logic handles high event rates without dropping messages.
   - **Notes:** Implemented `LogStreamer` in `src/solbot/solana/data.py` with WebSocket log subscriptions, internal buffering, and exponential backoff to avoid dropped messages. Deprecated `SlotStreamer` in favor of event-centric streaming.
   - [DONE] 2025-08-04 685f2799 — added Prometheus `log_queue_depth` gauge and `dropped_logs` counter with jittered backoff and fail-fast when queue >75% for 1s; `tests/test_data.py` asserts drop counter increments and stream halts.
   - **Notes:** Introduced `program_id` labels and public `reset_metrics` helper; `LogStreamer` now drains its queue on shutdown to avoid stale depth readings.
2. Implement real event parsing in Rust for low-latency processing.
   - Extend the Rust crate under `rustcore/` to decode swap instructions and liquidity events.
   - Expose parsers to Python via pyo3 and integrate them into `EventStream` so that each incoming log produces a populated `Event` object.
   - **Notes:** Added `ParsedEvent` struct and `parse_log` function in `rustcore/src/lib.rs` using `serde_json`; exposed via pyo3 and wired into `EventStream` for zero-copy conversion of logs to typed events.
3. Map parsed events to feature updates.
   - Use the existing `PyFeatureEngine` interface and ensure only touched indices are updated per event.
   - Implement update functors for at least: liquidity delta, cumulative liquidity, signed and absolute swap volume, swap inter-arrival time, and minted token amount.
   - **Notes:** `EventStream` now yields `solbot.schema.Event` objects derived from parsed logs, enabling `PyFeatureEngine` to update liquidity, volume, inter-arrival, and mint metrics with index-level precision.
4. Define the initial feature subset.
   - Use the taxonomy in `features.yaml` as the source of truth.
   - Document the index and normalization rule for every active feature.
   - **Notes:** Replaced `features.yaml` with six-feature schema mapping indices, categories, event sources, and z-score normalisation; documented the subset in README under an "Active Features" table.
5. Verify per-event processing cost stays O(k) where k is number of affected features.
   - Use profiling to confirm latency below 1 ms per event in Python and sub‑100 µs in Rust.
   - **Notes:** Added `tests/test_perf.py` benchmarking `parse_log` (<100 µs) and expanded `tests/test_features.py` latency benchmark for `PyFeatureEngine` (<80 µs) confirming O(k) updates.
6. Add persistent logging and basic storage.
   - Log every raw event and resulting feature vector at DEBUG level.
   - Implement a ring buffer or SQLite table to retain the latest N feature vectors for debugging and future backtesting.
   - **Notes:** `EventStream` now logs raw WebSocket logs and parsed events; `PyFeatureEngine` logs normalized features and maintains a deque history of the last N `(event, features)` tuples with `history()` accessor.
7. Ensure the pipeline handles thousands of events per second.
   - Use asyncio tasks or threads to parallelize network IO and parsing.
   - Stress test against devnet or mainnet traffic and document throughput.
   - **Notes:** `EventStream` decouples log reception and parsing via an `asyncio.Queue` and thread pool executor; `tests/test_data.py` streams 5k mocked logs in <2s verifying throughput.

## 2. Feature Vector Management
1. Finalise the `FeatureVector` class.
   - Confirm normalization uses an exponentially decaying Welford update with λ=0.995 and epsilon 1e-8.
   - Ensure lag stacking returns a contiguous 768‑float buffer: current slot, lag1, lag2.
2. Implement snapshot and reset utilities for stateful testing and backtesting.
3. Provide hooks for external modules to subscribe to feature updates.
   - Expose a thread-safe publish/subscribe interface that delivers feature vectors without blocking the ingestion loop.

## 3. Posterior Engine Integration
1. Replace dummy probabilities in `src/solbot/engine/posterior.py`.
   - Implement a logistic regression for rug probability and a three-class softmax for trend/revert/chop using the live feature vector.
   - Add an online gradient update method consuming feature vector and observed outcomes.
2. Prepare interfaces for future Bayesian models.
   - Keep `predict` and `update` signatures stable and document internal state for particle filters.
3. Connect posterior outputs to the feature pipeline.
   - Ensure predictions occur every slot with <1 ms overhead and can run concurrently with feature updates.

## 4. Action Selection and Trade Execution
1. Implement the utility-based action selector.
   - Inputs: posterior probabilities, current positions from `RiskManager`, estimated fees/slippage.
   - Output: {Skip, Enter(q), Exit(q)} with q sized via a preliminary Kelly fraction capped at 50%.
   - Enforce an epsilon threshold to avoid churn when utility improvements are negligible.
2. Tie the selector into the existing `TradeEngine`.
   - For now use paper trading mode; wire through to the risk manager and persistence layer.
3. Integrate a Solana execution path.
   - Begin with `simulateTransaction` for all actions.
   - After validation, enable real transaction submission respecting demo/full license state as returned by `LicenseManager.verify_or_exit`.
4. Log every decision.
   - Record inputs, chosen action, computed utilities, and resulting order IDs.

## 5. Safety and Demo Mode Enforcement
1. Guarantee that demo mode never submits on‑chain transactions.
2. Extend `RiskManager` with:
   - Per-position P&L tracking.
   - Global drawdown ceiling that halts new trades when breached.
3. Implement global stop conditions.
   - Network instability, excessive slippage, or schema mismatch should trigger an automatic safe mode (Skip only).
4. Add unit tests covering license enforcement, risk limits, and demo restrictions.

## 6. End-to-End Validation
1. Run full integration tests on devnet.
   - Confirm that parsed liquidity and swap events match on-chain state.
   - Verify feature vector updates and posterior predictions respond to real trades.
2. Capture and store a dataset of event→feature→prediction→action tuples for offline analysis.
3. Document benchmark results: ingestion latency, feature update time, posterior inference time, and action selection latency.

Completion of these steps establishes the continuous data backbone and decision loop required for live trading. Subsequent milestones (advanced inference, multi-market support, reinforcement learning, cross-chain expansion) depend on this foundation.

## 7. Advanced Inference and Online Learning
1. Replace the logistic/softmax stub with a hierarchical Bayesian model.
   - Maintain a particle set (>=128) for rug and regime parameters with Laplace priors.
   - Run stochastic variational Bayes every 4th slot on recent data batches.
2. Implement calibration and drift monitoring.
   - Track Brier scores and recalibrate probabilities via rolling beta scaling when miscalibration exceeds 5%.
   - Trigger model reset if cumulative prediction error doubles baseline.
3. Decouple inference from main loop.
   - Run updates in a dedicated thread or process and publish latest parameters atomically to trading loop.
   - Ensure prediction latency stays <1 ms despite background learning.

## 8. Feature Expansion and Multi-Market Coverage
1. Grow feature vector toward the full 256-d taxonomy.
   - Add Ownership (holder concentration, entropy, top-wallet balances) and Microstructure metrics (spread, realized vol, order-book imbalance).
   - Document each added feature’s index, units, and normalisation.
2. Monitor multiple token pairs concurrently.
   - Refactor ingestion and feature pipeline to handle a configurable list of pools with independent state vectors.
   - Share heavy resources (RPC websockets, Rust parsers) across markets while keeping per-market isolation.
3. Provide hot-plug support for new markets.
   - Allow dynamic registration of a token pair that spins up ingestion, feature tracking, posterior instance, and action selector on demand.

## 9. Position Sizing and Risk Controls
1. Implement Kelly criterion sizing with safety scalars.
   - Compute k* = μ/σ² per asset from posterior mean/variance and cap at γ=0.5.
   - Apply entropy dampening: scale position size by (1 - H(p)/log C) where H is regime entropy.
2. Upgrade `RiskManager` to portfolio-level metrics.
   - Track per-position P&L, exposure, and realized volatility.
   - Compute rolling 99% cVaR assuming multivariate normal copula and block new orders if limit exceeded.
3. Add drawdown watchdog.
   - Record equity peaks and automatically flatten positions when drawdown >10% or when any single trade would breach the limit.

## 10. Performance and Latency Optimisation
1. Profile ingestion, feature updates, inference, and action selection under load.
   - Target <500 µs ingestion, <250 µs feature update, <1 ms inference, <500 µs action selection.
2. Offload critical paths to Rust.
   - Move heavy feature transforms and utility calculations into `rustcore` modules exposed via pyo3.
3. Introduce caching and concurrency improvements.
   - Cache RPC responses for slot data and account info with TTL to cut network latency.
   - Use lock-free queues or asyncio to avoid cross-thread contention.
4. Implement resilience checks.
   - Detect and recover from feed stalls, parser panics, or RPC timeouts without full restart.

## 11. Testing, Backtesting, and Observability
1. Achieve >90% coverage for new modules with deterministic unit tests.
2. Build a replay harness.
   - Feed recorded event streams into the pipeline to validate feature updates and trading decisions offline.
3. Integrate property-based tests for parser correctness and risk invariants.
4. Instrument metrics and tracing.
   - Expose Prometheus counters for latency, trade outcomes, and risk breaches.
   - Add structured logs with correlation IDs for end-to-end tracing.
5. Automate CI.
   - Ensure linting, tests, and type checks run on every push; block merges on failure.

## 12. Long-Term Enhancements
1. Reinforcement learning policy updates.
   - Batch rewards and run policy-gradient updates with entropy bonus to adapt thresholds and sizing.
2. Multi-agent and distributed deployment.
   - Allow independent agents per market communicating via message bus while sharing risk state.
3. Cross-chain and CEX integration.
   - Abstract data/execution interfaces so additional chains or exchanges plug in with minimal changes.
4. On-chain automation.
   - Design Solana programs for pre-signed orders or stop-loss enforcement to reduce off-chain latency.
5. Continuous fraud detection expansion.
   - Add classifiers for new scam patterns and schedule periodic retraining on latest incidents.
