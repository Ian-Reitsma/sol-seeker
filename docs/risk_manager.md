# Risk Manager

The `RiskManager` tracks portfolio state, exposures, and PnL. It now monitors
per-token drawdowns in addition to global equity.

## Per-token drawdown

- `token_equity`: running realized + unrealized value for each token.
- `token_peak`: highest recorded `token_equity`.
- `set_token_drawdown_limit(token, limit)`: configure a maximum fractional
  drawdown (e.g. `0.1` for 10%).
- `token_drawdown(token)`: current drawdown relative to `token_peak`.
- `record_trade()` refuses trades once a token's drawdown meets or exceeds its
  configured limit.

Calling `reset()` clears all token-specific tracking and limits.
