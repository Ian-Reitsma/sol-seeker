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
