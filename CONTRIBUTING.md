# Contributing to Proseferno

Thanks for helping! This guide gets you from clone to a passing pull request.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (manages Python 3.13 and the backend environment)
- [Node.js](https://nodejs.org) 22 LTS (frontend)
- Optional: the [Anthropic CLI](https://github.com/anthropics/anthropic-cli/releases) to test *Sign in with Claude*

You do **not** need API keys to develop: demo mode and the test suite use a fake Claude and a fake image model.

## Run it

```bash
dev.bat --demo
```

`dev.bat` starts the API with auto-reload on port 8732 and the Vite dev server with hot reload on <http://localhost:5173>. Drop `--demo` to use real Claude credentials. On macOS/Linux run the two halves yourself:

```bash
uv run --project backend proseferno --reload --demo
```

```bash
cd frontend && npm run dev
```

## Checks (run before opening a PR)

Backend, from `backend/`:

```bash
uv run ruff check src tests scripts evals
uv run ruff format src tests scripts evals
uv run mypy
uv run pytest
```

Frontend, from `frontend/`:

```bash
npm run typecheck
npm run lint
npm run format
npm test
npm run build
```

End to end (builds on the steps above; uses demo mode). `PW_CHANNEL=msedge` or `chrome` uses an installed browser instead of downloading Chromium:

```bash
npm run e2e
```

CI runs all of these on every pull request.

## Changing the API

The frontend's TypeScript types are generated from the FastAPI schema. After changing a model in `backend/src/proseferno/api/schemas.py` (or anything else that changes the OpenAPI schema), regenerate them:

```bash
uv run --project backend python backend/scripts/export_types.py
```

CI fails if `frontend/src/api/types.gen.ts` is out of date.

## Changing prompts

Prompts live in `backend/src/proseferno/prompts/*.md` with `$placeholders`. The most important ones are `voice_synthesize.md` (what a voice soul contains) and `writer_system.md` / `draft.md` / `critique.md` / `revise.md` (how posts are written). Voice quality is the product, so measure prompt changes with the [voice-fidelity eval](docs/voice-pipeline.md#measuring-voice-fidelity) on real writing before and after.

## Conventions

- Python: typed, small modules, `ruff` formatting (140 columns). Business logic stays out of route handlers.
- Long-running work runs as a job (`proseferno.jobs`) and streams progress to the UI over Server-Sent Events.
- Everything model-related goes through the `LLM` protocol (`proseferno.llm.base`) so tests can use `proseferno.demo.FakeLLM`.
- Model-authored visuals are never executed: SVG is sanitized and rasterized, charts are declarative Vega-Lite.
- React: function components, TanStack Query for server state, Tailwind classes with the theme tokens in `src/index.css` (never hard-code colors in components).
- Accessibility: every control has a label; check both day and night mode.
- Secrets go in the OS keychain via `proseferno.secrets`, never in the database, logs, or repo.

## Commits and pull requests

Small, focused PRs with a clear description of the user-visible change are easiest to review. Include screenshots for UI changes (day and night). Add or update tests with every behavior change.

By contributing you agree that your contributions are licensed under the [MIT License](LICENSE) and that you follow the [Code of Conduct](CODE_OF_CONDUCT.md).
