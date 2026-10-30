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
- Once the configuration is ready, the user can generate a voice_profile.md that the solution will use for all projects
- The voice_profile.md only has to be created once per user but can always be regenerated
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
- **Claude:** Anthropic Python SDK, default model `claude-opus-5-5`, adaptive thinking, per-task `effort`, every call streams (structured outputs via `messages.stream(output_format=...)`; the SDK refuses non-streaming requests above ~21k `max_tokens`), server-side refusal fallback (`fallbacks: "default"`, beta `server-side-fallback-2026-07-01`).
- **"Login to Claude via SSO"** = *Sign in with Claude*: the app runs `ant auth login` (Anthropic CLI browser OAuth with Claude Console; supports org SSO; API billing, not a Claude.ai subscription). An API key in the OS keychain is the fallback. Credential order: saved key → `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` → CLI profile.
- **Claude subscription (Pro/Max):** the `claude_connection` setting (`api` | `subscription`) picks the backend per call (`llm/router.py`). `subscription` runs the user's own unmodified Claude Code headless (`llm/claude_code.py`, `claude -p` with `--system-prompt-file`, `--json-schema`, `stream-json`, no tools, `--setting-sources ""`, empty temp cwd). Anthropic forbids third-party apps from offering Claude.ai login or touching subscription tokens, so never read `~/.claude` credentials or call the API with them. Sign-in is only Claude Code's own `claude auth login`, and there is no logout button because it would sign the user out of Claude Code everywhere. Always strip `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` from the child env, or Claude Code bills the API. On Windows, resolve npm's `claude.cmd` shim to the package's `bin/claude.exe`, because cmd.exe mangles JSON args. Tests use `tests/fixtures/fake_claude.py`, and `ClaudeAuth(discover_ant=False)` also disables Claude Code discovery.
- **Images: Claude only.** No other image models (no Cloudflare, OpenAI or Gemini). Hero, illustration, icon and diagram images are Claude-authored SVG (sanitized, rendered by resvg); charts are Claude-authored Vega-Lite (vl-convert). Model-generated code is never executed. Credits name the Claude model. Captions/credits live only on the image (`strip_image_captions` removes any the writer puts in the body). A failed image sets its own `error` status and never fails the post; `pending` images are failed at startup (jobs are in-memory).
- **Memes:** `images/memes/` has a catalog of 18 formats (famous formats recast with our robot cast, never real people or others' characters; chart jokes; comics; fake artifacts; classic caption). Two calls: `MemeIdeas` (5 scored pitches from the whole post, `plan.joke`, plan callbacks, humor dial; effort `effort_meme_ideas`) then `MemeBuild` (slot text, per-region SVG art, `cast_defs` symbols, chart data). Code owns layout and type: `compose.py` draws frames/bubbles/charts and fits every string to its box with Pillow (`groups` share a size). The meme's `spec` is a JSON state (`version` 2: concepts, chosen, tried, format, build): Redraw keeps the joke, New idea takes the next untried pitch with no ideation call, `meme_format` re-pitches in one format, edits rebuild from the stored build. A build that cannot be drawn is retried once, then falls back to `classic_caption`. Older memes (plain SVG + captions) still edit via `SvgMemeSpec`. Add formats per `docs/images.md`.
- **Titles:** the author can edit the title, pin options (`Project.pinned_titles`), and regenerate the rest (`POST /api/projects/{id}/titles`); pins survive post regeneration.
- **AI-generation detection:** `authenticity/` scores posts 0-100 (100 = reads as human): a scan calibrated to the persona's own samples + a Claude judge (60/40). The scan's findings feed the critique prompt. Eval: `backend/evals/ai_detection.py`.
- **Revising a post:** three paths. *Tweak with feedback* (`writer/tweak.py`, `POST /api/projects/{id}/tweak`, job `tweak_post`) asks Claude for a `PostEdits` find/replace list, never a full rewrite, and redraws only images the feedback names. *Edit brief & settings* regenerates with a new brief, dials or persona (`POST /generate` with a `GenerateIn` body; nothing is saved without regenerating). *Regenerate post* as is. Only one text job (`TEXT_JOBS`) runs per project; only `generate_post` shows the generation view.
- **Text history:** `Project.revisions` keeps the last 10 texts (before tweak, rewrite, manual save, restore), newest first; a full regeneration clears it because old text refers to old image slots. Images keep their own history.
- **X:** an X Article platform (writing guide, 1500×600 header, ≤280-char teaser post in `export/x.py`). Threads are not supported.
- **LinkedIn:** a platform for writing and export (article HTML, 1920×1080 cover, feed post ≤3,000 chars, carousel PDF + PPTX via python-pptx).
- **Voice profile** (formerly "voice soul"; the older name survives only in CHANGELOG history and the profile's own `## Soul` section): the generated, versioned document describing how a persona writes (`VoiceProfile` model, `/voice-profile` routes, `voice_profile.md`). `db/engine.rename_legacy_schema` and `move_legacy_voice_files` migrate databases and files from the old names; keep them until a major version.
- **Personas:** voice profile versions can be pinned (`Persona.pinned_voice_profile_version`; use `current_voice_profile`, not `latest_voice_profile`, for writing) and labeled; personas can be duplicated into a new name. 0-10 style dials are relative to the author (5 = as they write).
- **Learning from edits:** `voice/lessons.py` diffs manual saves (short removals/replacements only, ≤8 words) and keeps tweak feedback in `Persona.edit_lessons`; `format_lessons` feeds them to `writer_system` (pass `lessons` to every writer call) and to voice synthesis. Lives in `voice/`, not `writer/`, to avoid a circular import.
- **Voice profile settings:** `Persona.voice_profile_words`, `voice_sample_max_words` (0 = whole sample; analyses record `_word_limit` and are redone when it changes), `voice_sample_min_words`, `voice_influence_weight` (0 = influences ignored).
- **Callbacks:** `ArticlePlan.callbacks` (key concepts; running jokes only at humor ≥3) go to the draft and critique (`Critique.callbacks`). Older stored plans and critiques lack them, so read them as optional.
- **Images:** `Project.brand_kit` (style, palette, font, motif) overrides the persona's visual style per post; `ImageService.create(..., brand_kit=, instruction=)` edits the current spec when given an instruction (`prompts/image_edit.md`).
- **Finished text:** posts never contain TODOs (`strip_todos` in `ensure_placeholders`) and never name tools only because the samples do. Keep third-party product names out of hard-coded prompts, topic keywords and fixtures; they may appear only when they come from the persona's own writing.
- **Windows build:** `packaging/` (PyInstaller spec, Inno Setup script, `build_windows.bat`; `uv` group `package`). `config.FROZEN` switches the frontend to the bundle and data to `%LOCALAPPDATA%\Proseferno`.
- **Schema changes:** `db/engine.add_missing_columns` adds new columns to existing databases; give new columns a default.
- **Privacy:** user writing (`my_writing_examples/`) and all runtime data (`data/`) are git-ignored. Secrets live in the OS keychain.
- **First run with no files:** the app must work for someone with no writing and no keys. `sample_content/` bundles three sample posts (`POST /api/personas/{id}/samples/import-sample-writing`) and the hand-written example voice profile. `example.py` builds the "Sample Author" example persona (`Persona.is_example`) by running the real voice and writing pipelines against `demo.FakeLLM` through the job manager (`POST`/`DELETE /api/example`). Demo mode seeds it on an empty database (`PROSEFERNO_DEMO_SEED`), `main()` offers demo mode on a bare first launch from a terminal, and the first real persona takes over from the example as the active one. Empty-state behavior is covered by `tests/api/test_empty_state.py` and `frontend/e2e/tour.spec.ts`.
- **Repo tidiness:** a few root files only (launchers, README, CONTRIBUTING, CHANGELOG, CLAUDE.md, LICENSE, configs); scripts in `scripts/` or `backend/scripts/`, community files in `.github/`, guides in `docs/`. No per-folder READMEs: `docs/onboarding.md` is the way in. Windows scripts share `scripts/_env.bat` (finds uv, shortens `UV_PROJECT_ENVIRONMENT` for deep paths, which also fixes the 260-character issue below).
- **Port:** 8732 (8765 collided with another local app).

## Commands

Windows one-click: `launch.bat` (add `--demo` for canned responses, no keys; demo opens seeded with the example persona and post). macOS/Linux: `./launch.sh`. Developer scripts live in `scripts/` as `.bat` + `.sh` pairs: `setup` (one idempotent install), `dev` (API with reload on :8732, Vite on :5173), `check` (every CI check in CI order; `--fix`, `--e2e`). `uv run --project backend proseferno doctor` diagnoses a machine. Standalone app + installer: `packaginguild_windows.bat`. Keep `scripts/check.*` and `.github/workflows/ci.yml` in step. New contributors start at `docs/onboarding.md`.

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
uv run python evals/ai_detection.py --demo --judge --yes   # AI-detection eval wiring check (scan-only runs are free)
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

Deep worktree paths can exceed Windows' 260-character limit inside `backend/.venv` (an Anthropic SDK file name is very long); the Windows scripts handle this automatically, otherwise set `UV_PROJECT_ENVIRONMENT` to a short path. On this Windows machine uv was installed by winget and may not be on PATH in a fresh shell; it lives under `%LOCALAPPDATA%\Microsoft\WinGet\Packages\astral-sh.uv_*`. The Anthropic CLI is at `%LOCALAPPDATA%\Programs\ant\ant.exe`.

## Layout and conventions

- `backend/src/proseferno/`: `api/` (routes only), `sample_content/` (bundled sample posts), `example.py`, `doctor.py`, `ingest/`, `voice/`, `writer/`, `authenticity/`, `images/`, `export/`, `llm/`, `prompts/` (Markdown templates with `$placeholders`), `db/`, `jobs.py`, `services.py` (wiring), `demo.py` (fakes for tests and demo mode).
- All model calls go through the `LLM` protocol (`llm/base.py`); tests use `proseferno.demo.FakeLLM`. When adding a structured-output schema, add a payload for it in `demo.py`.
- Long work runs as a job (`jobs.py`) and streams events over SSE; the frontend follows it with `useJob`.
- Tests must never touch real services: `ClaudeAuth(..., discover_ant=False)` and `MemorySecretStore` in fixtures (a test once launched the real `ant auth login`).
- Frontend: TanStack Query hooks in `src/api/hooks.ts`, theme tokens in `src/index.css` (no raw colors in components), non-component helpers in `src/lib/`, pages in `src/pages/`.
- Text on flame surfaces uses `.flame-button` (AA contrast); `.flame-bar` is decorative only.
- Batch files must keep CRLF line endings (`.gitattributes`).
- Voice quality is the product: measure prompt changes with `backend/evals/voice_fidelity.py` on real writing.

## Docs

`README.md`, `CONTRIBUTING.md`, `docs/` (onboarding, architecture, voice pipeline + eval, AI detection, images, exporting, configuration). Update them when behavior changes; refresh README screenshots with `UPDATE_SCREENSHOTS=1 npm run e2e`.
