# Contributing to Proseferno

Thanks for helping! This guide gets you from clone to a passing pull request. If you are new to the project, read [docs/onboarding.md](docs/onboarding.md) first: it has the cheat sheet, a map of "I want to change X, so edit Y", a glossary and troubleshooting.

## Set up

```bash
scripts\setup.bat      # Windows
scripts/setup.sh       # macOS / Linux
```

This installs [uv](https://docs.astral.sh/uv/) (Python 3.13 and the backend environment) and [Node.js](https://nodejs.org) 22 LTS if you agree, installs all packages, and finishes by running `proseferno doctor`, which tells you how to fix anything still missing. Re-run it any time; it is safe to repeat. The [Anthropic CLI](https://github.com/anthropics/anthropic-cli/releases) is optional, only for testing *Sign in with Claude*.

You do **not** need API keys or any writing of your own to develop: demo mode and the test suite use a fake Claude and a fake image model, and the app ships with sample posts and an example persona.

## Run it

```bash
scripts\dev.bat --demo     # Windows
scripts/dev.sh --demo      # macOS / Linux
```

This starts the API with auto-reload on port 8732 and the Vite dev server with hot reload on <http://localhost:5173>. Drop `--demo` to use real Claude credentials.

## Check your change

```bash
scripts\check.bat          # or scripts/check.sh
```

It runs everything CI runs, in CI order, and prints a summary: ruff (lint and format check), mypy, pytest, the generated-types check, then typecheck, oxlint, prettier, vitest and the production build. `--fix` applies the formatters, and `--e2e` adds the Playwright end-to-end tests (`PW_CHANNEL=msedge` or `chrome` uses an installed browser instead of downloading Chromium). CI runs the same checks on every pull request; if you change the list, change `scripts/check.*` and `.github/workflows/ci.yml` together.

## Changing the API

The frontend's TypeScript types are generated from the FastAPI schema. After changing a model in `backend/src/proseferno/api/schemas.py` (or anything else that changes the OpenAPI schema), regenerate them:

```bash
uv run --project backend python backend/scripts/export_types.py
```

CI fails if `frontend/src/api/types.gen.ts` is out of date.

## Changing prompts

Prompts live in `backend/src/proseferno/prompts/*.md` with `$placeholders`. The most important ones are `voice_synthesize.md` (what a voice profile contains) and `writer_system.md` / `draft.md` / `critique.md` / `revise.md` (how posts are written). Voice quality is the product, so measure prompt changes with the [voice-fidelity eval](docs/voice-pipeline.md#measuring-voice-fidelity) on real writing before and after.

## Good first tasks

Each one touches a small, well-contained part of the code and is covered by the checks.

1. **Tune a prompt and measure it.** Change one instruction in `prompts/critique.md`, then run `uv run --project backend python backend/evals/voice_fidelity.py --demo --yes` to see how the eval is wired (a real run on your own writing costs money and needs `--yes`).
2. **Add a dial.** Follow an existing one, for example "skimmability": `writer/dials.py` (resolution and prompt text), `api/schemas.py`, `db/models.py` (a persona default; give it a column default), `frontend/src/pages/dials.ts` and `components/DialsFields.tsx`. Regenerate the types.
3. **Add an export platform.** Look at `export/x.py` (small) and `PLATFORMS` in `export/bundle.py`; add a writing guide for it and a test in `tests/unit/`.
4. **Improve a screen's empty state.** Find one in `frontend/src/pages/` (try Personas), and check it in day and night mode.

## Conventions

- Python: typed, small modules, `ruff` formatting (140 columns). Business logic stays out of route handlers.
- Long-running work runs as a job (`proseferno.jobs`) and streams progress to the UI over Server-Sent Events.
- Everything model-related goes through the `LLM` protocol (`proseferno.llm.base`) so tests can use `proseferno.demo.FakeLLM`. When you add a structured-output schema, add a payload for it in `demo.py`.
- Tests must never touch real services: fixtures use `ClaudeAuth(..., discover_ant=False)` and `MemorySecretStore`.
- Model-authored visuals are never executed: SVG is sanitized and rasterized, charts are declarative Vega-Lite.
- React: function components, TanStack Query for server state, Tailwind classes with the theme tokens in `src/index.css` (never hard-code colors in components).
- Accessibility: every control has a label; check both day and night mode.
- Secrets go in the OS keychain via `proseferno.secrets`, never in the database, logs, or repo.
- Keep the repository tidy: new files go in the folder that already holds their kind (`scripts/`, `docs/`, `backend/scripts/`); avoid adding loose files at the root.
- Batch files (`*.bat`) keep CRLF line endings; `.gitattributes` handles it.

## Commits and pull requests

Small, focused PRs with a clear description of the user-visible change are easiest to review. Include screenshots for UI changes (day and night). Add or update tests with every behavior change.

By contributing you agree that your contributions are licensed under the [MIT License](LICENSE) and that you follow the [Code of Conduct](.github/CODE_OF_CONDUCT.md). Report security issues privately, as described in the [security policy](.github/SECURITY.md).
