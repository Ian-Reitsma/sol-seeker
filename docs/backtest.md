# Backtest Persistence

Completed backtests are stored as JSON files under `persistence/backtests/` with the job identifier as the filename.
Each record contains the backtest id, timestamp, and summary metrics (PnL, drawdown, Sharpe).

## Retrieval

- `GET /backtest/{id}` returns the metrics for a specific run.
- `GET /backtest/history` returns a list of all stored backtests sorted by timestamp.

## Cleanup

Backtest files are not automatically pruned. Administrators should periodically
remove old entries from `persistence/backtests/` as needed to reclaim disk space.
