# AGENTS AUDIT

This file defines the immediate and near-term directives for the next development agent. The items are ordered by criticality and expected impact. Implement each item completely before moving to the next.

## 1. Core Data Ingestion and Feature Pipeline
1. Replace the placeholder slot-only stream with real on-chain event subscriptions.
   - Update `src/solbot/solana/data.py` to subscribe via WebSocket to program logs or account changes for DEX swaps, liquidity adds/removes, and token mint events.
   - Ensure reconnect and backoff logic handles high event rates without dropping messages.
2. Implement real event parsing in Rust for low-latency processing.
   - Extend the Rust crate under `rustcore/` to decode swap instructions and liquidity events.
   - Expose parsers to Python via pyo3 and integrate them into `EventStream` so that each incoming log produces a populated `Event` object.
3. Map parsed events to feature updates.
   - Use the existing `PyFeatureEngine` interface and ensure only touched indices are updated per event.
   - Implement update functors for at least: liquidity delta, cumulative liquidity, signed and absolute swap volume, swap inter-arrival time, and minted token amount.
4. Define the initial feature subset.
   - Use the taxonomy in `features.yaml` as the source of truth.
   - Document the index and normalization rule for every active feature.
5. Verify per-event processing cost stays O(k) where k is number of affected features.
   - Use profiling to confirm latency below 1 ms per event in Python and sub‑100 µs in Rust.
6. Add persistent logging and basic storage.
   - Log every raw event and resulting feature vector at DEBUG level.
   - Implement a ring buffer or SQLite table to retain the latest N feature vectors for debugging and future backtesting.
7. Ensure the pipeline handles thousands of events per second.
   - Use asyncio tasks or threads to parallelize network IO and parsing.
   - Stress test against devnet or mainnet traffic and document throughput.

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
