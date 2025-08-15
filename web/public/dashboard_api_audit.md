# Dashboard–API Connectivity Audit (Deep Dive)

**Scope**: Compare the static dashboard [`web/public/dashboard.html`](dashboard.html) against the backend service implemented in
`src/solbot/server/api.py` and auxiliary licensing services.  The objective is to ensure every interactive widget on the
dashboard is wired to a live REST or WebSocket endpoint and that every backend capability has a corresponding UI hook.

For each gap, the audit provides:

* **Management Summary** – why the feature matters for product readiness.
* **Developer Notes** – exact file/line references, expected request‒response shapes, DOM selectors, verification commands, and wiring steps.

At the end of the audit the next agent should be able to methodically connect every remaining module without additional
context.

---

## Environment & Verification Prerequisites

1. **Run the backend**: `uvicorn src.solbot.server.api:app --reload --port 8000` from repository root.  Confirm `http://localhost:8000/health` returns 200 before loading the dashboard.
2. **Open the dashboard**: serve or open `web/public/dashboard.html` directly in a browser.  In the console set:
   ```js
   localStorage.sol_seeker_api_base = 'http://localhost:8000';
   localStorage.sol_seeker_api_key = '<your-api-key>';
   ```
3. **Network inspection**: keep DevTools Network tab open.  Every item below requires observing the corresponding REST request or WebSocket handshake returning 2xx (or meaningful error) during testing.
4. **Line references**: HTML line numbers are from the current commit; if upstream files shift, search by selector IDs instead of relying solely on numbers.
5. **OpenAPI**: `web/public/openapi.json` mirrors the backend schema.  Regenerate via `uvicorn`’s `/openapi.json` if endpoints change and keep this file in sync.

Only after this setup should the following gap analysis be executed.

---

## 0. Sanity‑Check: Modules Already Connected

The following API routes are currently exercised by the dashboard and therefore fall outside the gap lists below.  They are
included only to demonstrate that the entire codebase was surveyed.

| Endpoint | Purpose | UI Integration |
|---------|---------|----------------|
| `GET /health`, `GET /status` | Node liveness & RPC latency | `updateSystemHealth()` polls via `apiClient.getHealth()` and `apiClient.getStatus()`【F:web/public/dashboard.html†L1728-L1810】 |
| `GET /state` / `POST /state` | Trading state & settings | `updateDashboardData()` fetches state and settings panel posts updates【F:web/public/dashboard.html†L2658-L2267】 |
| `GET /dashboard` | Core risk/market snapshot | Fetched on load to populate portfolio metrics【F:web/public/dashboard.html†L2666-L2674】 |
| `GET /posterior` | Regime probabilities | `updateDashboardData()` pulls `apiClient.getPosterior()` and `updateRegimeAnalysis()` renders the odds【F:web/public/dashboard.html†L2666-L2673】【F:web/public/dashboard.html†L2888-L2897】 |
| `GET /license` | License diagnostics | `updateDashboardData()` caches the response and `updateLicenseInfo()` renders wallet, mode and issued time【F:web/public/dashboard.html†L2902-L2973】【F:web/public/dashboard.html†L3271-L3284】 |
| `POST /backtest` | Historical simulation results | `runBacktest()` posts form params and updates the metrics card【F:web/public/dashboard.html†L2283-L2316】 |
| `GET /positions`, `GET /orders`, `POST /orders` | Position list, order history and placement | Called in initialization and trade modal【F:web/public/dashboard.html†L2666-L2670】【F:web/public/dashboard.html†L2390-L2390】 |
| WebSockets `/dashboard/ws`, `/positions/ws`, `/posterior/ws`, `/logs/ws` | Real‑time risk, positions, regime probabilities and debug logs | `initializeWebSockets()` connects and updates UI【F:web/public/dashboard.html†L3334-L3378】 |

`/status` supports optional `start`/`end`/`limit` parameters validated via the shared query schemas; malformed values yield HTTP 400.
All other modules fall into one of the three gap categories below.

---

## 1. API Modules Not Surfaced on the Dashboard

These backend features ship with the server but have no dashboard entry point.  Management loses visibility and developers
lack UI triggers until they are exposed.

### 1.1 `/license` – Wallet License Diagnostics
* **Management Summary**: Without a direct license view, operators cannot audit token expiry or distribution records from the UI.
* **Developer Notes**:
  - Endpoint defined at `src/solbot/server/api.py` lines 466‑474 returning `{wallet, mode, issued_at, expires_at}`【F:src/solbot/server/api.py†L466-L474】.
  - `SolSeekerAPI.getLicense()` fetches this endpoint and `updateLicenseInfo()` renders the panel during `updateDashboardData()`【F:web/public/dashboard.html†L2902-L2973】【F:web/public/dashboard.html†L3271-L3284】.
* **Agent Notes (2025-08-15)**:
  - Added a visible `<div id="licenseInfo">` in the settings section showing wallet, mode, issued time and expiry.
  - `updateDashboardData()` polls `/license` daily, storing `expires_at` in `dashboardState.licenseExpiry` and calling `updateLicenseExpiryBanner()` to show a yellow banner when fewer than seven days remain【F:web/public/dashboard.html†L2934-L2975】【F:web/public/dashboard.html†L3790-L3814】.
  - **Status**: Completed with proactive expiry warnings.


### 1.2 `/api` – Service Map & Discovery
* **Management Summary**: Lacking endpoint discovery forces manual documentation upkeep.
* **Developer Notes**:
  - Route implemented at lines 298‑333 and returns `ServiceMap` containing all REST/WS paths and schema hash【F:src/solbot/server/api.py†L298-L333】.
  - No dashboard element references this index; consider an "API Explorer" modal accessible from the debug console.
  - Response schema: `{tradingview: url, endpoints: {...}, license: {...}, timestamp, schema_hash}`.
* **Agent Notes (2025-08-07)**:
  - Added an **API Explorer** button in the debug console that opens a modal and fetches the `/api` service map.
  - The modal enumerates REST and WebSocket endpoints, providing quick discovery without leaving the dashboard.
  - **Status**: Fully implemented; future improvement could include search and filtering within the modal for very large maps.

### 1.3 `/tv` – TradingView Helper
* **Management Summary**: Troubleshooting chart embeds requires manual URL construction today.
* **Developer Notes**:
  - Helper defined at lines 341‑351 returning minimal HTML with a TradingView widget【F:src/solbot/server/api.py†L341-L351】.
  - Dashboard already embeds charts directly and never links to `/tv`.  Provide a small "Open in TradingView" button near
    charts that launches this endpoint in a new tab.
* **Agent Notes (2025-08-07)**:
  - Added an **Open TradingView** control beside the market pair buttons; clicking it opens `/tv?symbol=<PAIR>` in a new browser tab.
  - The link is parameterized with the currently active symbol so operators view charts for the exact pair they are analysing.
  - **Status**: Completed. A potential enhancement is to update the button label dynamically when the user switches tokens without reloading the page.

### 1.4 `/assets` – Supported Asset Catalogue
* **Management Summary**: Without a canonical asset list, order forms risk invalid token symbols.
* **Developer Notes**:
  - Implemented at lines 357‑359 returning `["SOL", "ETH", ...]`【F:src/solbot/server/api.py†L357-L359】.
  - `SolSeekerAPI.getAssets()` exists at line 2534 but no UI calls it【F:web/public/dashboard.html†L2534-L2534】.
  - Accepts `limit`/`offset` query parameters validated via shared `LimitParams`; invalid values return `400`.
  - Populate dropdowns such as the order ticket or strategy matrix validator with this list and cache it client‑side.
* **Agent Notes (2025-08-07)**:
  - Extended `updateDashboardData()` to call `apiClient.getAssets()` once and cache the result in `dashboardState.assets`.
  - Added a **supported-assets dropdown** in the settings panel that lists every symbol returned by `/assets`.
  - The dropdown doubles as input validation for order placement; subsequent refreshes reuse the cached list to minimize network chatter.
  - Demo mode settings now validate selected assets against this list before saving, disabling the save button and showing a toast on unknown symbols【F:web/public/dashboard.html†L2163-L2225】【F:web/public/dashboard.html†L3356-L3380】.
  - **Status**: Completed. Future work could include refreshing the cache periodically to pick up newly listed tokens.

### 1.5 `/features/schema` – Feature Index Metadata
* **Management Summary**: Operators cannot inspect which model features drive decisions.
* **Developer Notes**:
  - Route at lines 368‑378 returns names and descriptions for each feature index【F:src/solbot/server/api.py†L368-L378】.
  - Although `SolSeekerAPI.getFeaturesSchema()` exists (line 2538), no panel renders this documentation.
  - Add an expandable "AI Feature Schema" table using `<div id="featureSchema">` to help data scientists verify inputs.
* **Agent Notes (2025-08-07)**:
  - Created an **AI Feature Schema** panel with `<div id="featureSchema">` that renders the `/features/schema` response as a scrollable list of feature names and descriptions.
  - Schema is fetched once during dashboard initialization and cached in `dashboardState.featureSchema` for reuse.
  - **Status**: Completed. Potential enhancement: include search/filtering for large feature sets.

### 1.6 `/version` and `/manifest` – Build Provenance
* **Management Summary**: Management cannot confirm the running commit or available endpoints from the UI, complicating
  support.
* **Developer Notes**:
  - `/version` defined at lines 838‑840, `/manifest` at 842‑850 listing every route【F:src/solbot/server/api.py†L838-L850】.
  - `SolSeekerAPI.getVersion()` (line 2562) and `getManifest()` (line 2566) are unused.
  - Add an "About" dialog linking these endpoints and display `schema_hash` to detect mismatches between frontend bundle and
    backend.
* **Agent Notes (2025-08-07)**:
  - Implemented an **About** modal reachable from the debug console with an `aboutBtn` trigger.
  - Modal concurrently fetches `/version` and `/manifest`, then displays commit hash, schema hash, and counts of REST and WebSocket endpoints.
  - Includes graceful error handling and a close button; modal is hidden when clicking outside the content.
  - **Status**: Completed. Future optimization might cache the response to avoid repeated network calls.

### 1.7 `/orders/ws` – Dedicated Order Event Stream
* **Management Summary**: Trading feed cannot show real‑time fills without subscribing to the server’s order stream.
* **Developer Notes**:
  - WebSocket declared at lines 535‑537 forwarding messages from the generic hub【F:src/solbot/server/api.py†L535-L537】.
  - `initializeWebSockets()` never connects to `/orders/ws`; the trading feed remains a static placeholder.
  - Add `wsClient.connect('/orders/ws', onOrderEvent)` where `onOrderEvent` appends entries to `#tradingFeed`.
* **Agent Notes (2025-08-07)**:
  - Implemented `updateTradingFeed()` which subscribes to `/orders/ws` and formats each incoming order into the dashboard feed.
  - Added posterior-driven neural entries and history appends when orders close, providing rich real-time context.
  - **Status**: Completed. Monitor for performance under heavy traffic; future tuning may batch UI updates when volumes spike.

### 1.8 Generic Broadcast WebSocket `/ws`
* **Management Summary**: The broadcast socket can deliver cross‑module events yet the dashboard does not expose a listener for
  diagnostics.
* **Developer Notes**:
  - Defined at lines 512‑533; clients send messages that are broadcast to all connections【F:src/solbot/server/api.py†L512-L533】.
  - Expose a simple "Raw Stream" panel in the debug console for advanced operators.

### 1.9 License Issuer Micro‑Service
* **Management Summary**: Users cannot self‑issue demo or full licenses from the dashboard, increasing support burden.
* **Developer Notes**:
  - Separate FastAPI app exposes `POST /issue`, `GET /healthz`, and `GET /readyz` at lines 57‑71 of
    `src/solbot/service/license_issuer.py`【F:src/solbot/service/license_issuer.py†L57-L71】.
  - No frontend integration; add a "Request Demo License" button that posts wallet address to `/issue` and surfaces progress.

---

## 2. Dashboard Modules Missing Backend Support

These widgets attempt to call endpoints that do not exist or contain purely static HTML with no backend counterpart.  Until
server routes are implemented, the panels will remain ornamental.

### 2.1 Security & Rug‑Pull Checks
* **Management Summary**: Critical trust signals (rug pull risk, liquidity, contract verification) are never refreshed.
* **Developer Notes**:
  - `updateDashboardData()` calls `apiClient.get('/risk/security')` at lines 2666‑2674 and 2554‑2556 yet `rg` finds no such
    route in `api.py`【F:web/public/dashboard.html†L2554-L2556】.
  - Implement `GET /risk/security` returning `{rug_pull, liquidity, contract, holders, trading_patterns}` and wire
    `updateSecurityPanel()` to map each field to its card (IDs `rugPullDetail`, `liquidityDetail`, etc.).

### 2.2 Whale / Smart‑Money Analytics Suite
* **Management Summary**: High‑value trading intelligence (whale alerts, smart‑money flow, copy trading, strategy matrix,
  arbitrage opportunities) is completely absent from the backend.
* **Developer Notes**:
  - `loadAnalytics()` attempts to fetch `/whales`, `/smart-money-flow`, `/copy-trading`, `/strategies`, `/arbitrage` at lines
    3001‑3015【F:web/public/dashboard.html†L3001-L3015】.
  - No corresponding routes exist; every container (`#whaleAlerts`, `#strategyMatrix`, etc.) receives "DATA UNAVAILABLE".
  - Backend must supply these endpoints or the panels should be hidden until implemented.

### 2.3 Social Sentiment & News Feeds
* **Management Summary**: The dashboard promises real‑time community sentiment but shows empty tables.
* **Developer Notes**:
  - Calls to `/sentiment/trending`, `/sentiment/influencers`, `/sentiment/pulse`, and `/news` originate at lines 3100‑3106【F:web/public/dashboard.html†L3100-L3106】.
  - No routes exist; implement a sentiment service or remove the "Trending Tokens", "Influencer Alerts", and "News Feed"
    sections (DOM IDs `trendingTokens`, `influencerAlerts`, `newsFeed`).

### 2.4 Neural Trading Feed
* **Management Summary**: Marketing highlights a neural feed yet the panel only displays a placeholder.
* **Developer Notes**:
  - HTML container lives at lines 1000‑1010 with ID `tradingFeed`【F:web/public/dashboard.html†L1000-L1010】.
  - JavaScript lines 2116‑2144 append entries only when mock events are generated; no endpoint supplies data.
  - Once `/orders/ws` is wired (see §1.7), push each order event through `appendTradeEntry()` that formats `{token, side, qty,
    price}`.

### 2.5 Upcoming Catalysts List
* **Management Summary**: Catalysts panel now pulls live data and auto-refreshes.
* **Developer Notes**:
  - Items load from `GET /catalysts` returning `{name, eta, severity}` and refresh every minute via `updateCatalystList()`.
* **Agent Notes (2025-08-07)**:
  - Implemented a typed `Catalyst` model and exposed `GET /catalysts` returning `{ name, eta, severity }`.
  - Added an **Upcoming Catalysts** panel driven by `apiClient.getCatalysts()`; items are color‑coded by severity and show relative times.
  - Server test cases ensure the service map advertises the route and that responses match the schema.
  - **Status**: Completed. Future optimization might sort events chronologically and poll periodically for updates.

### 2.6 Backtest Progress WebSocket
* **Management Summary**: Users cannot monitor long‑running backtests, leading to confusion about job status.
* **Developer Notes**:
  - After `apiClient.runBacktest()` (line 2301), the UI expects updates from `/backtest/ws/{id}` at lines 2281‑2316【F:web/public/dashboard.html†L2281-L2316】.
  - Server exposes only synchronous `POST /backtest`; implement `@app.websocket('/backtest/ws/{id}')` streaming `{progress,
    pnl}` and close on completion.

* **Agent Notes (2025-08-09)**:
  - Reworked `/backtest` into async jobs and added `/backtest/ws/{id}` emitting staged progress and final stats.
  - Dashboard progress bar subscribes to this stream and shows final PnL on completion.
  - **Status**: Completed.

### 2.7 Portfolio Equity Chart Endpoint
* **Management Summary**: Equity curve is a key KPI yet the chart never renders.
* **Developer Notes**:
  - `loadEquityChart()` fetches `/chart/portfolio?tf=...` at lines 3828‑3847【F:web/public/dashboard.html†L3828-L3847】.
  - Backend only supports `/chart/{symbol}`; either add `/chart/portfolio` or adapt the frontend to call `/chart/SOL` (or
    whichever symbol represents equity).
  - Supports `start`/`end`/`cursor`/`limit` via shared `RangeParams` and `LimitParams`; invalid values trigger a uniform HTTP 400 response.

* **Agent Notes (2025-08-09)**:
  - Added `/chart/portfolio` powered by `RiskManager.equity_history` and advertised in service map.
  - Frontend renders the returned series via Chart.js with live equity label.
  - **Status**: Completed.

---

## 3. Modules Present in Both Backend and Frontend but Disconnected

In these cases both sides ship partial implementations, but mismatched expectations prevent data from flowing.

### 3.1 Metrics Polling Without Endpoint
* **Management Summary**: Resource meters always show stale defaults, giving a false impression of system health.
* **Developer Notes**:
  - `updateSystemHealth()` calls `apiClient.get('/metrics')` at lines 1799‑1810 and again via `dashboardState` at 2558‑2559【F:web/public/dashboard.html†L1799-L1810】【F:web/public/dashboard.html†L2558-L2559】.
  - `ServiceMap` advertises a metrics route (line 316) but `api.py` defines no `@app.get('/metrics')` handler【F:src/solbot/server/api.py†L316-L316】.
  - Implement a FastAPI route returning `{cpu, memory, network}` or remove polling.
* **Agent Notes (2025-08-07)**:
  - Added a typed `/metrics` endpoint that reports CPU load, memory utilization, and network throughput, importing `psutil` once and falling back to load averages when unavailable.
  - Dashboard `updateSystemHealth()` now parses these fields to refresh resource meters in real time.
  - Moved Prometheus statistics to `/metrics/prometheus` to avoid path conflicts.
  - **Status**: Completed. Possible future work includes per‑process metrics for finer granularity.

### 3.2 Feature Stream Logged but Not Rendered
* **Management Summary**: Real‑time model features arrive over WebSocket yet remain invisible to users.
* **Developer Notes**:
  - WebSocket `/features/ws` implemented at lines 579‑616 streams arrays of feature values【F:src/solbot/server/api.py†L579-L616】.
  - `initializeWebSockets()` subscribes but only logs the payload at lines 3366‑3370【F:web/public/dashboard.html†L3366-L3370】.
  - Create an "AI Feature Monitor" table (`<div id='featureStream'>`) and populate it on each message.
* **Agent Notes (2025-08-07)**:
  - Built a dedicated **AI Feature Monitor** panel with `<div id="featureStream">` that prepends timestamped feature vectors streamed from `/features/ws`.
  - Log maintains the most recent 50 entries to prevent unbounded growth.
  - Also leveraged the same stream to update the Current Feature Snapshot panel with the latest values.
  - **Status**: Completed. For heavy streams, consider virtualized rendering or throttling.

### 3.3 Backtest Summary vs. Expected Streaming
* **Management Summary**: The backtest form appears unresponsive because the frontend waits for messages that never arrive.
* **Developer Notes**:
  - `POST /backtest` returns final metrics immediately (lines 394‑408)【F:src/solbot/server/api.py†L394-L408】.
  - The frontend nevertheless attempts to open `/backtest/ws/{id}` (lines 2281‑2316) for progress updates.
  - Decide between a purely synchronous job (remove WebSocket logic) or implement streaming as described in §2.6.

* **Agent Notes (2025-08-09)**:
  - Implemented asynchronous `/backtest` jobs returning an ID and `/backtest/ws/{id}` streaming `{progress, pnl, drawdown, sharpe}`.
  - Dashboard connects to the WebSocket, updates the progress bar, and renders final metrics when `progress` hits `100`.
  - Added server tests verifying staged progress messages and websocket closure.

### 3.4 Chart API Shape Mismatch
* **Management Summary**: Portfolio chart never displays because UI and API disagree on path structure.
* **Developer Notes**:
  - API exposes `/chart/{symbol}` at lines 832‑837【F:src/solbot/server/api.py†L832-L837】.
  - Dashboard requests `/chart/portfolio?tf=1H|4H|1D` (lines 3828‑3847)【F:web/public/dashboard.html†L3828-L3847】.
  - Align by either implementing `/chart/portfolio` or using `/chart/${symbol}` consistently.

* **Agent Notes (2025-08-09)**:
  - Added `/chart/portfolio` endpoint backed by `RiskManager.equity_history` and advertised in the service map.
  - `loadEquityChart()` now renders the equity curve via Chart.js when `series` data is returned.
  - Included endpoint in OpenAPI spec and regression tests.

### 3.5 Trading Feed Not Subscribed to Order Stream
* **Management Summary**: Live fills are vital for traders yet the feed stays empty.
* **Developer Notes**:
  - UI contains `#tradingFeed` container (lines 1000‑1010) and helper `appendTradeEntry()` at 2116‑2144.
  - Backend provides `/orders/ws` (lines 535‑537) but `initializeWebSockets()` never connects; only generic `/ws` exists.
  - Add `wsClient.connect('/orders/ws', appendTradeEntry)` to populate the feed and remove `feedPlaceholder`.
* **Agent Notes (2025-08-07)**:
  - Introduced `updateTradingFeed()` which establishes a `/orders/ws` WebSocket and routes events into `addFeedEntry()` for display.
  - Implemented dual entries for trade executions and accompanying neural decisions, plus history recording on order closure.
  - Removed placeholder text so feed shows only genuine events.
  - **Status**: Completed. Future refinement may include pagination or archiving for long-running sessions.

### 3.6 License Mode Indicator vs. Rich License Data
* **Management Summary**: Status banner only distinguishes demo vs. live, ignoring detailed license fields already provided by
  the backend.
* **Developer Notes**:
  - `updateLicenseMode()` toggles CSS based solely on `state.mode` from `/state` (lines 2658‑2695).
  - `/license` offers fields `wallet`, `mode`, and `issued_at` (lines 417‑424) yet the function never consumed them.
  - Extend `updateDashboardData()` to merge `getLicense()` output and display token mint and expiry in the settings modal.
* **Agent Notes (2025-08-10)**:
  - Merged license data into dashboard state and implemented `updateLicenseInfo()` to render `wallet`, `mode`, and `issued_at` in a dedicated diagnostics panel.
  - `updateLicenseMode()` now derives demo vs. live from license metadata, ensuring consistent state even if `/state` and `/license` diverge.
  - **Status**: Completed. Potential follow-up is to show token mint and expiration once backend exposes those fields.

### 3.7 Feature Snapshot Fetched but Hidden
* **Management Summary**: The dashboard retrieves a one‑off feature vector but never exposes it, preventing operators from verifying model inputs.
* **Developer Notes**:
  - `/features` provides the latest feature array (lines 361‑366)【F:src/solbot/server/api.py†L361-L366】.
  - `updateDashboardData()` stores the response in `dashboardState.features`, yet no UI component reads it (lines 2666‑2681)【F:web/public/dashboard.html†L2666-L2681】.
  - Surface a "Current Feature Snapshot" panel or remove the fetch to avoid unnecessary bandwidth.
* **Agent Notes (2025-08-07)**:
  - Added a **Current Feature Snapshot** panel that maps the latest feature vector to schema labels using cached metadata from `/features/schema`.
  - `renderFeatureSnapshot()` refreshes the panel on initial load and whenever `/features/ws` delivers new data, including a timestamp of capture.
  - **Status**: Completed. To further optimize, consider diffing against previous snapshots to highlight changing features.

---

## 4. Consolidated Action Plan

### 4.1 Executive Summary for Management
* The backend currently exposes numerous operational endpoints (license checks, service maps, asset lists, build metadata) that
  are invisible in the dashboard.
* Many headline dashboard features – security scoring, whale analytics, neural trading feed, catalysts, social sentiment and
  portfolio equity chart – call nonexistent APIs and therefore display placeholder text.
* Even where matching routes exist (metrics, feature streaming, backtesting, order fills), mismatched expectations or missing
  wiring leave panels blank.

### 4.2 Developer Task Breakdown
1. **Surface API‑only capabilities**: wire `/license`, `/api`, `/tv`, `/assets`, `/features/schema`, `/version`, `/manifest`,
   `/orders/ws`, and generic `/ws` to new or existing UI components.
2. **Implement missing server routes**: create `/risk/security`, `/whales`, `/smart-money-flow`, `/copy-trading`, `/strategies`,
   `/arbitrage`, `/sentiment/trending`, `/sentiment/influencers`, `/sentiment/pulse`, `/news`, `/catalysts`, `/chart/portfolio`,
   and `/backtest/ws/{id}`.
3. **Complete partially wired modules**:
   - Add `/metrics` handler returning CPU/memory/network stats.
   - Render data from `/features/ws` into an "AI Feature Monitor".
   - Reconcile backtest execution model (synchronous vs. streaming).
   - Standardise chart endpoints and subscribe trading feed to `/orders/ws`.
   - Enhance license banner with `/license` details.
4. **Verification**: For each panel, confirm REST/WS traffic in browser dev tools, handle error states gracefully, and remove or
   hide any widget that cannot be wired.

Once the above tasks are completed, every interactive module on `dashboard.html` will pull live data, and every backend
capability will be discoverable from the UI.

### 4.3 Operational Notes for the Next Agent

- **Keep specs synchronized**: whenever endpoints are added or modified, regenerate `web/public/openapi.json` and update this audit with new selectors or line numbers.
- **Test rigorously**: run `pytest` and `npm test` after wiring any module.  Document any skipped tests or missing frameworks for the following agent.
- **Document deprecations**: if a dashboard section is removed instead of wired, note it in `AGENTS-AUDIT.md` and prune dead code.
- **Credential management**: never commit real API keys.  The dashboard expects keys in `localStorage.sol_seeker_api_key`; provide mock values for tests.
- **Error telemetry**: ensure future wiring includes user-facing error toasts and console logs so broken integrations are immediately evident.

