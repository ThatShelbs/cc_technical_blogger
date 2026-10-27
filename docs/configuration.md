# Configuration

Proseferno works with zero configuration. Most settings live in the app (**Settings**); a few can be set with environment variables or a `.env` file at the repository root (copy `.env.example`).

## In the app

| Setting | Where | Default |
| --- | --- | --- |
| Claude sign-in or API key | Settings → Claude | none |
| Model | Settings → Advanced | `claude-opus-5-5` |
| Voice editing passes | Settings → Advanced | 1 |
| Refusal fallback | Settings → Advanced | on |
| AI-detection judge | Settings → Advanced | on (the free scan always runs) |
| Theme | Settings → Appearance, or the sidebar toggle | match system |
| Persona name, byline, credit format, visual style, web research | Personas → (persona) → Settings & defaults | from the voice soul |
| Default dials for new posts: length, images, humor, storytelling, opinion strength, formality, technical depth, skimmability, education level, code, platform | Personas → (persona) → Settings & defaults | 1,500 words, automatic images, humor 5, style dials 5 ("as I write"), intermediate, code where it helps, Medium |
| Voice soul version in use | Sidebar persona switcher, or the Voice soul tab | always the latest |

## Environment variables

| Variable | Purpose | Default |
| --- | --- | --- |
| `PROSEFERNO_DATA_DIR` | Where the database, samples, voice souls, images and exports live | `./data` |
| `PROSEFERNO_PORT` | Port for the local app | `8732` |
| `PROSEFERNO_SEED_SAMPLES_DIR` | Folder offered for one-click import of your writing | `./my_writing_examples` |
| `PROSEFERNO_MODEL` | Claude model | `claude-opus-5-5` |
| `PROSEFERNO_USE_FALLBACKS` | Server-side refusal fallback | `true` |
| `PROSEFERNO_REVISION_PASSES` | Editing passes per post | `1` |
| `PROSEFERNO_EFFORT_*` | Effort per task: `ANALYZE`, `RESEARCH`, `SYNTHESIZE`, `PLAN`, `DRAFT`, `CRITIQUE`, `IMAGES`, `DETECT` | see `config.py` |
| `PROSEFERNO_DEMO` | Demo mode (canned responses) | `false` |
| `PROSEFERNO_NO_BROWSER` | Do not open a browser on start | unset |
| `ANTHROPIC_API_KEY` | Claude API key (overrides *Sign in with Claude*) | unset |
| `PROSEFERNO_AI_DETECTION` | Claude judge in the AI-detection report | `true` |

Values saved in the app (model, passes, fallback, AI-detection judge) take precedence over environment defaults.

## Claude credentials, in order

1. An API key saved in Proseferno (OS keychain).
2. `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN` in the environment.
3. The active Anthropic CLI profile from *Sign in with Claude* (`ant auth login`).

An environment API key silently overrides a signed-in profile; the Settings page warns you when that happens.

## Command line

```bash
uv run --project backend proseferno --help
```

```text
--host HOST   --port PORT   --open (browser)   --reload (development)   --demo
```
