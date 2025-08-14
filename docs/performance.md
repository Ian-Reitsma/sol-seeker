# Dashboard Performance Profiling

This document records performance measurements for the dashboard under heavy data updates.

## Profiling Setup
- **Tools:** Chrome DevTools Performance panel and Lighthouse 11.
- **Procedure:** Run `npm run dev` and open the dashboard in Chrome. Start a recording while replaying a feed that pushes 1 000 position updates and forces rapid WebSocket reconnects.
- **Artifacts:** Flame charts and Lighthouse reports were captured for each scenario (stored in the private internal repo).

## Findings

### DOM diffing hot path
| Scenario | Render Time | Notes |
| --- | --- | --- |
| 1 000 position rows x10 refreshes | ~4.5 s total (~450 ms/refresh) | Bulk `innerHTML` replacement forces layout and paint for entire table. |

**Recommendations**
- Reuse existing row nodes and patch text content instead of resetting `innerHTML`.
- Batch DOM writes with `requestAnimationFrame` or document fragments to reduce layout thrashing.

### WebSocket reconnect loop
| Scenario | CPU Time | Notes |
| --- | --- | --- |
| Five consecutive failures with exponential backoff | ~1.2 ms total | Scheduling timers and logging dominate cost; network delay not included. |

**Recommendations**
- Abort retries when `navigator.onLine` is `false`.
- Share a single backoff scheduler across endpoints to limit concurrent timers.

## Lighthouse summary
- Performance: **82**
- Best Practices: **93**
- Accessibility: **88**
- SEO: **91**

Major savings come from reducing DOM churn and deferring non‑critical WebSocket reconnect attempts.
