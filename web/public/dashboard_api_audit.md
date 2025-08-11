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
| `POST /backtest` | Historical simulation results | `runBacktest()` posts form params and updates the metrics card【F:web/public/dashboard.html†L2283-L2316】 |
| `GET /positions`, `GET /orders`, `POST /orders` | Position list, order history and placement | Called in initialization and trade modal【F:web/public/dashboard.html†L2666-L2670】【F:web/public/dashboard.html†L2390-L2390】 |
| WebSockets `/dashboard/ws`, `/positions/ws`, `/posterior/ws`, `/logs/ws` | Real‑time risk, positions, regime probabilities and debug logs | `initializeWebSockets()` connects and updates UI【F:web/public/dashboard.html†L3334-L3378】 |

All other modules fall into one of the three gap categories below.

---

## 1. API Modules Not Surfaced on the Dashboard

These backend features ship with the server but have no dashboard entry point.  Management loses visibility and developers
lack UI triggers until they are exposed.

### 1.1 `/license` – Wallet License Diagnostics
* **Management Summary**: Without a direct license view, operators cannot audit token expiry or distribution records from the
  UI.
* **Developer Notes**:
  - Endpoint defined at `src/solbot/server/api.py` lines 261‑267 returning `{owner, mode, issued_at}`【F:src/solbot/server/api.py†L261-L267】.
  - `SolSeekerAPI.getLicense()` is stubbed at dashboard line 2570 yet never invoked【F:web/public/dashboard.html†L2570-L2571】.
  - Add a "License" panel in settings that calls `apiClient.getLicense()` during `updateDashboardData()` and surfaces fields
    like `mode` and `expires`.

### 1.2 `/api` – Service Map & Discovery
* **Management Summary**: Lacking endpoint discovery forces manual documentation upkeep.
* **Developer Notes**:
  - Route implemented at lines 298‑333 and returns `ServiceMap` containing all REST/WS paths and schema hash【F:src/solbot/server/api.py†L298-L333】.
  - No dashboard element references this index; consider an "API Explorer" modal accessible from the debug console.
  - Response schema: `{tradingview: url, endpoints: {...}, license: {...}, timestamp, schema_hash}`.

### 1.3 `/tv` – TradingView Helper
* **Management Summary**: Troubleshooting chart embeds requires manual URL construction today.
* **Developer Notes**:
  - Helper defined at lines 341‑351 returning minimal HTML with a TradingView widget【F:src/solbot/server/api.py†L341-L351】.
  - Dashboard already embeds charts directly and never links to `/tv`.  Provide a small "Open in TradingView" button near
    charts that launches this endpoint in a new tab.

### 1.4 `/assets` – Supported Asset Catalogue
* **Management Summary**: Without a canonical asset list, order forms risk invalid token symbols.
* **Developer Notes**:
  - Implemented at lines 357‑359 returning `["SOL", "ETH", ...]`【F:src/solbot/server/api.py†L357-L359】.
  - `SolSeekerAPI.getAssets()` exists at line 2534 but no UI calls it【F:web/public/dashboard.html†L2534-L2534】.
  - Populate dropdowns such as the order ticket or strategy matrix validator with this list and cache it client‑side.

### 1.5 `/features/schema` – Feature Index Metadata
* **Management Summary**: Operators cannot inspect which model features drive decisions.
* **Developer Notes**:
  - Route at lines 368‑378 returns names and descriptions for each feature index【F:src/solbot/server/api.py†L368-L378】.
  - Although `SolSeekerAPI.getFeaturesSchema()` exists (line 2538), no panel renders this documentation.
  - Add an expandable "AI Feature Schema" table using `<div id="featureSchema">` to help data scientists verify inputs.

### 1.6 `/version` and `/manifest` – Build Provenance
* **Management Summary**: Management cannot confirm the running commit or available endpoints from the UI, complicating
  support.
* **Developer Notes**:
  - `/version` defined at lines 838‑840, `/manifest` at 842‑850 listing every route【F:src/solbot/server/api.py†L838-L850】.
  - `SolSeekerAPI.getVersion()` (line 2562) and `getManifest()` (line 2566) are unused.
  - Add an "About" dialog linking these endpoints and display `schema_hash` to detect mismatches between frontend bundle and
    backend.

### 1.7 `/orders/ws` – Dedicated Order Event Stream
* **Management Summary**: Trading feed cannot show real‑time fills without subscribing to the server’s order stream.
* **Developer Notes**:
  - WebSocket declared at lines 535‑537 forwarding messages from the generic hub【F:src/solbot/server/api.py†L535-L537】.
  - `initializeWebSockets()` never connects to `/orders/ws`; the trading feed remains a static placeholder.
  - Add `wsClient.connect('/orders/ws', onOrderEvent)` where `onOrderEvent` appends entries to `#tradingFeed`.

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
* **Management Summary**: Time‑sensitive catalysts remain hard‑coded, risking stale information.
* **Developer Notes**:
  - Static markup at lines 948‑971 lists `$NOVA Token Burn`, `Jupiter V2 Launch`, and `Solana Breakpoint`【F:web/public/dashboard.html†L948-L971】.
  - No API call exists; design a new `GET /catalysts` returning `{event, timestamp, severity}` and refresh panel via
    `updateCatalystList()`.

### 2.6 Backtest Progress WebSocket
* **Management Summary**: Users cannot monitor long‑running backtests, leading to confusion about job status.
* **Developer Notes**:
  - After `apiClient.runBacktest()` (line 2301), the UI expects updates from `/backtest/ws/{id}` at lines 2281‑2316【F:web/public/dashboard.html†L2281-L2316】.
  - Server exposes only synchronous `POST /backtest`; implement `@app.websocket('/backtest/ws/{id}')` streaming `{progress,
    pnl}` and close on completion.

### 2.7 Portfolio Equity Chart Endpoint
* **Management Summary**: Equity curve is a key KPI yet the chart never renders.
* **Developer Notes**:
  - `loadEquityChart()` fetches `/chart/portfolio?tf=...` at lines 3187‑3193【F:web/public/dashboard.html†L3187-L3193】.
  - Backend only supports `/chart/{symbol}`; either add `/chart/portfolio` or adapt the frontend to call `/chart/SOL` (or
    whichever symbol represents equity).

---

## 3. Modules Present in Both Backend and Frontend but Disconnected

In these cases both sides ship partial implementations, but mismatched expectations prevent data from flowing.

### 3.1 Metrics Polling Without Endpoint
* **Management Summary**: Resource meters always show stale defaults, giving a false impression of system health.
* **Developer Notes**:
  - `updateSystemHealth()` calls `apiClient.get('/metrics')` at lines 1799‑1810 and again via `dashboardState` at 2558‑2559【F:web/public/dashboard.html†L1799-L1810】【F:web/public/dashboard.html†L2558-L2559】.
  - `ServiceMap` advertises a metrics route (line 316) but `api.py` defines no `@app.get('/metrics')` handler【F:src/solbot/server/api.py†L316-L316】.
  - Implement a FastAPI route returning `{cpu, memory, network}` or remove polling.

### 3.2 Feature Stream Logged but Not Rendered
* **Management Summary**: Real‑time model features arrive over WebSocket yet remain invisible to users.
* **Developer Notes**:
  - WebSocket `/features/ws` implemented at lines 579‑616 streams arrays of feature values【F:src/solbot/server/api.py†L579-L616】.
  - `initializeWebSockets()` subscribes but only logs the payload at lines 3366‑3370【F:web/public/dashboard.html†L3366-L3370】.
  - Create an "AI Feature Monitor" table (`<div id='featureStream'>`) and populate it on each message.

### 3.3 Backtest Summary vs. Expected Streaming
* **Management Summary**: The backtest form appears unresponsive because the frontend waits for messages that never arrive.
* **Developer Notes**:
  - `POST /backtest` returns final metrics immediately (lines 394‑408)【F:src/solbot/server/api.py†L394-L408】.
  - The frontend nevertheless attempts to open `/backtest/ws/{id}` (lines 2281‑2316) for progress updates.
  - Decide between a purely synchronous job (remove WebSocket logic) or implement streaming as described in §2.6.

### 3.4 Chart API Shape Mismatch
* **Management Summary**: Portfolio chart never displays because UI and API disagree on path structure.
* **Developer Notes**:
  - API exposes `/chart/{symbol}` at lines 832‑837【F:src/solbot/server/api.py†L832-L837】.
  - Dashboard requests `/chart/portfolio?tf=1H|4H|1D` (lines 3187‑3193)【F:web/public/dashboard.html†L3187-L3193】.
  - Align by either implementing `/chart/portfolio` or using `/chart/${symbol}` consistently.

### 3.5 Trading Feed Not Subscribed to Order Stream
* **Management Summary**: Live fills are vital for traders yet the feed stays empty.
* **Developer Notes**:
  - UI contains `#tradingFeed` container (lines 1000‑1010) and helper `appendTradeEntry()` at 2116‑2144.
  - Backend provides `/orders/ws` (lines 535‑537) but `initializeWebSockets()` never connects; only generic `/ws` exists.
  - Add `wsClient.connect('/orders/ws', appendTradeEntry)` to populate the feed and remove `feedPlaceholder`.

### 3.6 License Mode Indicator vs. Rich License Data
* **Management Summary**: Status banner only distinguishes demo vs. live, ignoring detailed license fields already provided by
  the backend.
* **Developer Notes**:
  - `updateLicenseMode()` toggles CSS based solely on `state.mode` from `/state` (lines 2658‑2695).
  - `/license` offers additional fields such as `owner` and `issued_at` (lines 261‑267) yet the function never consumes them.
  - Extend `updateDashboardData()` to merge `getLicense()` output and display token mint and expiry in the settings modal.

### 3.7 Feature Snapshot Fetched but Hidden
* **Management Summary**: The dashboard retrieves a one‑off feature vector but never exposes it, preventing operators from verifying model inputs.
* **Developer Notes**:
  - `/features` provides the latest feature array (lines 361‑366)【F:src/solbot/server/api.py†L361-L366】.
  - `updateDashboardData()` stores the response in `dashboardState.features`, yet no UI component reads it (lines 2666‑2681)【F:web/public/dashboard.html†L2666-L2681】.
  - Surface a "Current Feature Snapshot" panel or remove the fetch to avoid unnecessary bandwidth.

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

