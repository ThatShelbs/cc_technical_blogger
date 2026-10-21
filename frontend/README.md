# Proseferno frontend

React 19 + TypeScript + Vite + Tailwind CSS 4. In production the backend serves the build from `dist/`; you normally start everything with `launch.bat` or `dev.bat` at the repository root.

```bash
npm run dev          # Vite dev server on :5173, proxies /api to the backend on :8732
npm test             # Vitest + Testing Library
npm run typecheck    # tsc
npm run lint         # oxlint
npm run format       # prettier
npm run build        # production build into dist/
npm run e2e          # Playwright smoke test against the real backend in demo mode
```

- `src/api/types.gen.ts` is generated from the backend's OpenAPI schema (`backend/scripts/export_types.py`); don't edit it by hand.
- Theme tokens (day and night) live in `src/index.css`; use the token classes (`bg-surface`, `text-muted`, `border-line`, `bg-primary`, ...) instead of raw colors.
