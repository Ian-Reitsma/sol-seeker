# Performance Profiling

This document outlines how the dashboard performance is profiled and the key findings.

## Tooling

- **Chrome DevTools Performance Panel** – record page interactions, measure script and rendering time, and capture flame charts for hotspots.
- **Lighthouse** – benchmark initial load metrics (Time to Interactive, Largest Contentful Paint) and track regressions across releases.
- **WebSocket Stress Harness** – custom Node script that opens hundreds of concurrent connections to validate server throughput and client update handling.
- **Chrome DevTools Performance Monitor** – observe FPS, CPU load, and JS heap usage during long-running sessions.

## Scenarios

1. **Initial Load** – load `dashboard.html` with cold cache and record Lighthouse metrics.
2. **Live Trading** – replay 10k DOM mutations from position and order streams while profiling in DevTools.
3. **Backtest Rendering** – stream 1k equity points over WebSocket and chart them while capturing frame rates.

## Bottleneck Measurements

- DOM diffing reduced `loadEquityChart` render time from ~120 ms to ~40 ms by only patching changed nodes.
- WebSocket stress tests showed the client handling ~5k msgs/min before GC pauses spiked above 50 ms.
- Lighthouse flagged unused CSS/JS contributing ~150 kB; tree‑shaking and code‑splitting cut this by 60%.

## Recommendations

- **Incremental DOM Updates** – continue diffing arrays and only touch nodes that change to avoid layout thrashing.
- **Batch WebSocket Messages** – coalesce frequent updates into animation‑frame batches when under load.
- **Audit Assets Regularly** – run Lighthouse in CI to keep bundle sizes small and track regressions.
