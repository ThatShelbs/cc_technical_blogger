# Onboarding

Start here, whichever of these you are. Every path works **without any API keys and without any writing of your own**.

| I want to... | Do this |
| --- | --- |
| **Look around** before committing to anything | Run `launch.bat --demo` (or `./launch.sh --demo`). It opens on a finished example post. See [no files, no keys](#no-files-no-keys-start-here). |
| **Use it** to write in my own voice | Run `launch.bat`, then follow the five-step setup guide in the app. |
| **Work on the code** | Run `scripts\setup.bat` (or `scripts/setup.sh`), then follow [your first day](#your-first-day-as-a-developer). |

## Cheat sheet

| | Windows | macOS / Linux |
| --- | --- | --- |
| Use the app | `launch.bat` | `./launch.sh` |
| Try it with canned responses | `launch.bat --demo` | `./launch.sh --demo` |
| One-time developer setup | `scripts\setup.bat` | `scripts/setup.sh` |
| Developer mode (hot reload) | `scripts\dev.bat [--demo]` | `scripts/dev.sh [--demo]` |
| Run every check CI runs | `scripts\check.bat` | `scripts/check.sh` |
| Fix formatting, then check | `scripts\check.bat --fix` | `scripts/check.sh --fix` |
| Add the browser tests | `scripts\check.bat --e2e` | `scripts/check.sh --e2e` |
| Is my machine set up right? | `uv run --project backend proseferno doctor` | same |

| Thing | Where |
| --- | --- |
| The app | <http://127.0.0.1:8732> (the API docs are at `/docs`) |
| Developer mode | UI on <http://localhost:5173> (Vite proxies `/api` to the API on 8732) |
| Your data | `data/` (git-ignored); demo mode uses `data/demo/` |
| Your private writing | `my_writing_examples/` (git-ignored; the app offers a one-click import) |
| Secrets | your operating system keychain, never a file |
| Settings and environment variables | [configuration.md](configuration.md) |
| Logs | the terminal window running the API |

## No files, no keys? Start here

You do not need to have written anything, or have a Claude account, to see how Proseferno works.

1. **See a finished result.** `launch.bat --demo` opens on an example persona ("Sample Author") with a voice profile and a finished post: a hero image, diagram, chart and closing meme, each credited. Click the post, then **Personas** to read the voice profile. Everything is canned, nothing costs money, and your real data is untouched.
2. **Try the whole flow with no files.** In the setup guide, **Your writing** offers **Use 3 sample posts**: short posts by the fictional Sample Author. Generate a voice profile from them, then on **New post** click **Use an example prompt**. Replace the samples with your own writing whenever you like.
3. **See the example without demo mode.** If you run the real app with nothing set up, the empty Posts page has **See an example post**. It adds the example persona without calling Claude, and **Remove example** (Personas page) deletes it again.
4. **Ready for real output?** Open **Settings** to sign in with Claude or paste an API key, or choose your Claude subscription. Then upload three or more of your own posts (Word, PDF, Markdown, HTML or a URL).

If you start `launch.bat` on a fresh machine with no Claude connection, it offers to start in demo mode for you.

## Your first day as a developer

About 30 minutes.

1. **Set up** (5 min): `scripts\setup.bat`. It installs [uv](https://docs.astral.sh/uv/) and Node.js 22+ if you agree, installs the Python and web packages, and finishes with `proseferno doctor`.
2. **Run it** (2 min): `scripts\dev.bat --demo`. Open <http://localhost:5173>.
3. **Write a post** (5 min): click through the example, then try **Tweak with feedback** and **Edit brief & settings** on the post.
4. **Read** (10 min): [architecture.md](architecture.md), especially *Life of a post*, then skim one pipeline: `backend/src/proseferno/writer/pipeline.py`.
5. **Prove your setup** (3 min): `scripts\check.bat`. All ten checks should pass before you change anything.
6. **Make a first change** (5 min): pick one from *Good first tasks* in [CONTRIBUTING.md](../CONTRIBUTING.md#good-first-tasks), then run `scripts\check.bat` again.

### What is in the repository

| Folder | What lives there |
| --- | --- |
| `launch.bat`, `launch.sh` | One-click start for people using the app. |
| `scripts/` | Developer scripts: `setup`, `dev`, `check` (plus the shared `_env.bat`). |
| `backend/` | FastAPI + [uv](https://docs.astral.sh/uv/) (Python 3.13). `src/proseferno/` is the app, `tests/` uses a fake Claude, `evals/` are opt-in real-API quality evals, `scripts/` holds the type exporter and brand renderer. |
| `frontend/` | React 19 + Vite + Tailwind CSS 4. `src/pages/` are screens, `src/api/` the typed client, `e2e/` the Playwright tests. |
| `docs/` | Guides. This file is the way in. |
| `assets/brand/` | Logo and palette. |
| `.github/` | CI, issue and PR templates, the security policy and the code of conduct. |

The backend modules are described in [architecture.md](architecture.md#backend-modules). Each package's `__init__.py` has a one-line docstring saying what it is for.

### Commands you will use in the sub-projects

Backend, from `backend/` (`scripts\check` runs all of these for you):

```bash
uv sync
uv run pytest
uv run ruff check src tests scripts evals
uv run ruff format src tests scripts evals
uv run mypy
uv run python scripts/export_types.py        # after changing the API; CI checks it is current
uv run proseferno --demo --open
```

Frontend, from `frontend/`:

```bash
npm run dev          # Vite on :5173, proxies /api to :8732
npm test             # Vitest + Testing Library
npm run typecheck    # tsc
npm run lint         # oxlint
npm run format       # prettier
npm run build        # production build into dist/
npm run e2e          # Playwright, against the real backend in demo mode
```

`frontend/src/api/types.gen.ts` is generated from the backend's OpenAPI schema; do not edit it by hand. Theme tokens (day and night) live in `frontend/src/index.css`; use the token classes (`bg-surface`, `text-muted`, `border-line`, `bg-primary`, ...) instead of raw colors.

## I want to change... where do I edit?

| Change | Edit | Then |
| --- | --- | --- |
| How the voice profile is written | `backend/src/proseferno/prompts/voice_synthesize.md` | Run the [voice-fidelity eval](voice-pipeline.md#measuring-voice-fidelity) before and after. |
| How posts are written | `prompts/writer_system.md`, `plan.md`, `draft.md`, `critique.md`, `revise.md` | Same eval. |
| A post setting (a "dial") | `writer/dials.py`, `api/schemas.py`, `frontend/src/pages/dials.ts`, `components/DialsFields.tsx` | Regenerate types. |
| An export platform | `backend/src/proseferno/export/` and `PLATFORMS` in `export/bundle.py` | Add a writing guide, see [exporting.md](exporting.md). |
| What images look like | `prompts/image_system.md`, `image_spec.md`, `images/service.py` | See [images.md](images.md). |
| A screen | `frontend/src/pages/` | Check day and night mode. |
| Colors | `frontend/src/index.css` tokens only | Never raw colors in components. |
| An API endpoint | `backend/src/proseferno/api/` plus a model in `api/schemas.py` | `uv run python scripts/export_types.py`, then add a payload to `demo.py` for any new structured output. |
| A database column | `db/models.py` | Give it a default; `add_missing_columns` migrates old databases. |
| The example persona or sample posts | `backend/src/proseferno/sample_content/`, `example.py` | `uv run pytest tests/unit/test_example.py`. |
| Settings or environment variables | `config.py` | Update [configuration.md](configuration.md) and `.env.example`. |

## Glossary

- **Persona**: one writing voice with its own samples and voice profile. Exactly one is **on** at a time.
- **Sample**: a post you give Proseferno to learn from. *Own* samples define your voice; *influence* samples are writers you admire, whose techniques (not identity) are borrowed.
- **Voice profile**: the generated, versioned `voice_profile.md` describing how a persona writes. Regenerate it, edit it, name versions, or pin an old one.
- **Dials**: per-post settings (length, images, humor, education level, formality, technical depth...). The 0-10 style dials are relative to the author: 5 means "as they write".
- **Exemplars**: the most similar of your own posts, included in full as examples when drafting.
- **Project**: one post. Its **brief** is the sentence or outline you gave it.
- **Tweak, rewrite, regenerate**: the three ways to revise a post. A tweak is a list of small edits, never a full rewrite.
- **Revisions**: the last ten text versions, for Undo. Images keep their own history.
- **Reads-as-human score**: 0-100 AI-detection report (100 reads as human): a scan calibrated to your own samples plus a Claude judge.
- **Job**: long work that runs in the background and streams progress to the browser over server-sent events (SSE).
- **Connection**: how Claude is reached. *API* uses a Console key or sign-in; *subscription* runs your own Claude Code with your Pro or Max plan.
- **Demo mode**: canned responses from `demo.FakeLLM`; no keys, a separate `data/demo/` folder, seeded with the example.
- **Example**: the offline-built "Sample Author" persona and post. It is labelled everywhere it appears and can be removed in one click.

## Troubleshooting

Run `uv run --project backend proseferno doctor` first. It checks the items below and prints a fix for each.

| Symptom | Fix |
| --- | --- |
| `uv` is not recognised right after installing it | Open a new terminal. `launch.bat` and `scripts\*.bat` also look in the usual install folders. |
| Imports fail or `uv sync` fails with "path too long" (Windows) | Deep folders exceed Windows' 260-character limit. The scripts move the environment to `%USERPROFILE%\.venvs\proseferno` automatically; for manual commands set `UV_PROJECT_ENVIRONMENT` to a short path. Doctor reports "Windows path length". |
| "Something is already running on port 8732" | Close the other Proseferno window, or set `PROSEFERNO_PORT`. |
| The page says "the web app has not been built" or looks stale | Run `launch.bat` (it rebuilds when sources changed) or `npm run build` in `frontend/`. |
| `npm ci` errors or the build fails | Check `node --version` is 22 or newer. |
| "Not signed in" | Settings → Claude. Or explore with `--demo`. |
| An API key does not save (Linux) | No keychain service is running. Use *Sign in with Claude*, or install a Secret Service provider (for example gnome-keyring). |
| Claude subscription says Claude Code is missing or too old | Install or update it: <https://code.claude.com/docs/en/setup>, then `claude update`. |
| Playwright cannot find a browser | `npx playwright install chromium`, or set `PW_CHANNEL=msedge` to use Edge. |
| Tests try to reach the network | They must not. Fixtures use `ClaudeAuth(..., discover_ant=False)` and `MemorySecretStore`; see `backend/tests/conftest.py`. |
