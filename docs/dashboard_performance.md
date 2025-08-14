# Dashboard Performance Profiling

This document summarises profiling of the dashboard's main update paths under heavy load. Tests were executed with JSDOM via Jest (`web/tests/perf_profile.test.ts`).

## DOM Diffing (`updatePositionsDisplay`)
- **Scenario:** Rendered 1,000 synthetic positions across 10 successive refreshes.
- **Result:** ~4.5 s total (~450 ms per refresh).
- **Bottleneck:** Each update rebuilds row markup with `innerHTML`, forcing the browser to parse HTML strings and recreate DOM nodes.
- **Optimization Ideas:**
  - Reuse existing row elements and update text nodes instead of resetting `innerHTML`.
  - Batch DOM writes with `requestAnimationFrame` or a document fragment to reduce layout thrashing.
  - Consider virtual scrolling if position counts regularly exceed a few hundred.

## WebSocket Reconnection Loop
- **Scenario:** Simulated five consecutive failures with exponential backoff.
- **Result:** ~1.2 ms CPU time (timers dominated overall latency).
- **Bottleneck:** Minimal CPU impact; repeated `setTimeout` scheduling and logging are the primary costs.
- **Optimization Ideas:**
  - Abort retries when `navigator.onLine` is false to avoid needless timer setup.
  - Share a single backoff scheduler across endpoints to reduce concurrent timers.

Profiling code and measurements are reproducible via `npm test web/tests/perf_profile.test.ts`.
