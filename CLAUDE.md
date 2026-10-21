# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project purpose

**Proseferno** is a React front end, Python back end application that lets people write engaging technical blogs in their own voice.

This solution is specialized in writing technical blogs generally covering the following topics:
 - Data Science
 - Python Programming
 - Data Visualization
 - Machine Learning
 - Causality, Experimentation, & Causal Inference
 - Leading Analytics and Data Science Professionals
 - Advanced Analytics and Data Science at Large Companies
 - AI, LLM, and Agents
 - AI/ML Platforms (AWS, Snowflake)
 - Building with Agentic Coding Tools (Claude Code, Cursor, Anti-Gravity)

## Core functionality of solution

### User level functionality
- The user can upload samples of their blogs and writing as my_writing_examples, which is used to help establish personalized voice, tone, soul, and structure of writing
- The user can also upload samples of other people's blogs and writings to further synthesize voice, tone, soul, and structure of writing
- The user can also optionally turn on web research, which runs an LLM/agent to gather best practices in writing technical AI/ML blogs, including
    - title creation
    - writing compelling and satisfying stories
    - ensuring the structure serves the skim reader
    - incorporating humor
    - incorporating insightful work
    - building credibility and trust
    - educating by writing
- Once the configuration is ready, the user can generate a voice_soul.md that the solution will use for all projects
- The voice_soul.md only has to be created once per user but can always be regenerated
- The user can build multiple personas and give them names, but has to have one selected as "on" with all the others "off"

### Project level functionality
- The user will make one project per article/post/story
- There are additional dials to control target story length, how many images are generated within it, humor level, and education level
- Regarding the story images
    - Every post has an initial image that is also the thumbnail for the post
    - Every post closes with a funny, relevant joke or meme image
    - Other images serve key concepts, workflows, diagrams, and other points of the subsections
    - Images should take great care to be relevant to the text and provide additional value to the reader, for example
        - a clarifying diagram
        - an illustrative data visualization
        - a moment of humor
        - images should credit their creator (user name with model credit as well)
    - The user can redraw any given image to get another random image
    - When relevant, posts have key code snippets, LLM prompts, or platform screenshots
- The user is able to download the completed story optimized for one of medium.com, substack.com, gumroad.com, etc.
- Once the user is satisfied with the configuration, they provide a prompt or bullet point outline of the story and the application generates it
    - ensure this is in the 'on' persona's synthesized voice, tone, soul, and structure; this is the key point of the solution. If we don't pull this step off with high quality, the application is a failure
    - ensure the images are placed inline in the story

## Other details

 - use Python for the back end and React for the front end
 - with Python, always use uv for environment control
 - always use smart defaults: the user should have to fill out a very minimal set of inputs to do the work but have the option for lots of customization and flexibility
 - take care that this application is easy to launch with a .bat file
 - use best practices for folder structure and file organization in this repo so humans can easily and intuitively develop this open source application
 - after working on the app, always prove the functionality worked and the tool is still in good health and passing tests
 - after working on the app, always revisit CLAUDE.md as needed
 - ensure the repository is well documented and looks professional
 - the logo is a cute, savvy, professional agent robot that is also a tech blogger (`assets/brand/`)
 - prioritize the inferno color palette for the logo design and application theme
 - make sure the application can run in day mode and night mode as themes
 - the application can connect and log in to Claude via SSO

## Decisions made

- **Name:** Proseferno (Python package `proseferno`).
- **Claude:** Anthropic Python SDK, default model `claude-opus-5-5`, adaptive thinking, per-task `effort`, streaming for long outputs, structured outputs via `messages.parse()`, server-side refusal fallback (`fallbacks: "default"`, beta `server-side-fallback-2026-07-01`).
- **"Login to Claude via SSO"** = *Sign in with Claude*: the app runs `ant auth login` (Anthropic CLI browser OAuth with Claude Console; supports org SSO; API billing, not a Claude.ai subscription). An API key in the OS keychain is the fallback. Credential order: saved key → `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` → CLI profile.
- **Raster images:** Cloudflare Workers AI `@cf/black-forest-labs/flux-2-klein-4b` (multipart form; steps fixed at 4). Diagrams are Claude-authored SVG (sanitized, rendered by resvg); charts are Vega-Lite (vl-convert). Without Cloudflare, hero/illustration/meme fall back to Claude SVG. Model-generated code is never executed.
- **Privacy:** user writing (`my_writing_examples/`) and all runtime data (`data/`) are git-ignored. Secrets live in the OS keychain.
- **Port:** 8732 (8765 collided with another local app).

## Commands

Windows one-click: `launch.bat` (add `--demo` for canned responses, no keys). Developer mode: `dev.bat` (API with reload on :8732, Vite on :5173). macOS/Linux: `./launch.sh`.

Backend (run in `backend/`):

```bash
uv sync
uv run pytest                     # fake Claude + fake image model; no network
uv run ruff check src tests scripts evals
uv run ruff format src tests scripts evals
uv run mypy
uv run python scripts/export_types.py      # regenerate frontend/src/api/types.gen.ts after API changes
uv run proseferno --demo --open            # run the app
uv run python evals/voice_fidelity.py --demo --yes    # eval wiring check (real run costs money; needs --yes)
```

Frontend (run in `frontend/`):

```bash
npm run typecheck
npm run lint                      # oxlint
npm run format                    # prettier (types.gen.ts is ignored)
npm test                          # vitest
npm run build
npm run e2e                       # Playwright smoke test in demo mode; PW_CHANNEL=msedge to use installed Edge
```

On this Windows machine uv was installed by winget and may not be on PATH in a fresh shell; it lives under `%LOCALAPPDATA%\Microsoft\WinGet\Packages\astral-sh.uv_*`. The Anthropic CLI is at `%LOCALAPPDATA%\Programs\ant\ant.exe`.

## Layout and conventions

- `backend/src/proseferno/`: `api/` (routes only), `ingest/`, `voice/`, `writer/`, `images/`, `export/`, `llm/`, `prompts/` (Markdown templates with `$placeholders`), `db/`, `jobs.py`, `services.py` (wiring), `demo.py` (fakes for tests and demo mode).
- All model calls go through the `LLM` protocol (`llm/base.py`); tests use `proseferno.demo.FakeLLM`. When adding a structured-output schema, add a payload for it in `demo.py`.
- Long work runs as a job (`jobs.py`) and streams events over SSE; the frontend follows it with `useJob`.
- Tests must never touch real services: `ClaudeAuth(..., discover_ant=False)` and `MemorySecretStore` in fixtures (a test once launched the real `ant auth login`).
- Frontend: TanStack Query hooks in `src/api/hooks.ts`, theme tokens in `src/index.css` (no raw colors in components), non-component helpers in `src/lib/`, pages in `src/pages/`.
- Text on flame surfaces uses `.flame-button` (AA contrast); `.flame-bar` is decorative only.
- Batch files must keep CRLF line endings (`.gitattributes`).
- Voice quality is the product: measure prompt changes with `backend/evals/voice_fidelity.py` on real writing.

## Docs

`README.md`, `CONTRIBUTING.md`, `docs/` (architecture, voice pipeline + eval, images, exporting, configuration). Update them when behavior changes; refresh README screenshots with `UPDATE_SCREENSHOTS=1 npm run e2e`.
