Internal design documentation has moved to the private repository.

## Recent Updates

- Backend exposes a configurable `/backtest` endpoint returning PnL, drawdown, and Sharpe ratios.
- Dashboard UI gained auto-saving settings, toast notifications, DOM-diffed positions, and a backtest form.
- WebSocket reconnect logic now tracks attempts per endpoint and pauses when the tab is hidden.

## Next Steps

- Expand public docs to cover the backtesting API and dashboard integration details.
- Provide architectural diagrams for the WebSocket lifecycle and settings autosave flow.
- Document testing procedures once Jest-based web tests are in place.
- Record performance profiling results for the dashboard in `performance.md`.
