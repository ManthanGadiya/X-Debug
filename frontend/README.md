# XDebug Frontend

React + TypeScript dashboard for the XDebug explainable debugging platform.

## Stack

- Vite 8 + React 19 + TypeScript 6
- Mantine UI (core, hooks, notifications)
- React Router 7
- Vitest + Testing Library

## Development

```sh
npm install
npm run dev
```

The Vite dev server runs on `http://localhost:5173` and proxies `/api` to the
backend at `http://localhost:8000`.

## Scripts

| Command             | Description                  |
| ------------------- | ---------------------------- |
| `npm run dev`       | Start the dev server         |
| `npm run build`     | Type-check and build         |
| `npm run preview`   | Preview the production build |
| `npm run lint`      | ESLint                       |
| `npm run format`    | Prettier check               |
| `npm run typecheck` | TypeScript compile           |
| `npm test`          | Run the Vitest suite         |

## Environment

Copy `.env.example` to `.env.local` to override `VITE_API_BASE_URL`. When left
unset, the dev server proxies `/api` to `http://localhost:8000`.

## Structure

```
src/
  api/          # Typed backend API client
  components/   # Shared layout and UI components
  pages/        # Route-level pages
  test/         # Test setup
  theme.ts      # Mantine theme configuration
  main.tsx      # Application entry point
```
