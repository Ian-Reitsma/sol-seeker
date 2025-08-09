# Web Client

React + TypeScript frontend powered by [Vite](https://vitejs.dev/).

## Setup

```bash
cd web
npm install
cp .env.example .env # edit VITE_API_URL as needed
```

## Scripts

- `npm run dev` – start the development server
- `npm run build` – bundle the app for production
- `npm run lint` – run ESLint checks

## Environment

The client reads its API base URL from the `VITE_API_URL` environment variable.
Set this in `.env` before running the app:

```bash
VITE_API_URL=http://localhost:8000
```

## Recent Updates

- Dashboard settings auto-save with a disabled state, "Saving…" indicator, and toast on failure.
- WebSocket client tracks reconnect attempts per endpoint and pauses polling when the tab is hidden.
- Added backtest form posting to `/backtest` and rendering PnL, drawdown, and Sharpe metrics.
- Positions list now diffs DOM nodes instead of rebuilding the entire list.

## Next Steps

1. Fix the Jest setup so `npm test` executes the web unit tests.
2. Persist API base/key and recent backtest settings in local storage with validation.
3. Display progress/errors for long backtests and allow cancelation.
4. Add automated accessibility and visual regression tests for the dashboard.
