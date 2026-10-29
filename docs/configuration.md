# Configuration

Proseferno works with zero configuration. Most settings live in the app (**Settings**); a few can be set with environment variables or a `.env` file at the repository root (copy `.env.example`).

## In the app

| Setting | Where | Default |
| --- | --- | --- |
| Claude connection: Anthropic API or your Claude subscription | Settings → Claude | Anthropic API |
| Claude sign-in or API key | Settings → Claude | none |
| Model | Settings → Advanced | `claude-opus-5-5` |
| Voice editing passes | Settings → Advanced | 1 |
| Refusal fallback | Settings → Advanced | on |
| AI-detection judge | Settings → Advanced | on (the free scan always runs) |
| Theme | Settings → Appearance, or the sidebar toggle | match system |
| Persona name, byline, credit format, visual style, web research | Personas → (persona) → Settings & defaults | from the voice profile |
| Voice profile settings: profile length, words read per sample, minimum sample length, influence weight | Personas → (persona) → Settings & defaults | about 2,000 words, whole samples, every sample, influence 5/10 |
| Edits learned from your changes and feedback (review or forget) | Personas → (persona) → Settings & defaults | learned automatically |
| Image brand kit for one post: style, palette, font, motif | New post → Customize, or the post's **Image brand kit** card | the persona's visual style |
| Default dials for new posts: length, images, humor, storytelling, opinion strength, formality, technical depth, skimmability, education level, code, platform | Personas → (persona) → Settings & defaults | 1,500 words, automatic images, humor 5, style dials 5 ("as I write"), intermediate, code where it helps, Medium |
| Per-post brief, persona, platform, audience and every dial | New post → Customize; on a written post, **Edit brief & settings** (regenerates the post) | the persona's defaults; audience = your usual readers |
| Voice profile version in use | Sidebar persona switcher, or the Voice profile tab | always the latest |

## Environment variables

| Variable | Purpose | Default |
| --- | --- | --- |
| `PROSEFERNO_DATA_DIR` | Where the database, samples, voice profiles, images and exports live | `./data` |
| `PROSEFERNO_PORT` | Port for the local app | `8732` |
| `PROSEFERNO_SEED_SAMPLES_DIR` | Folder offered for one-click import of your writing | `./my_writing_examples` |
| `PROSEFERNO_CLAUDE_CONNECTION` | `api` (Console credits) or `subscription` (your Pro/Max plan through Claude Code) | `api` |
| `PROSEFERNO_MODEL` | Claude model | `claude-opus-5-5` |
| `PROSEFERNO_USE_FALLBACKS` | Server-side refusal fallback | `true` |
| `PROSEFERNO_REVISION_PASSES` | Editing passes per post | `1` |
| `PROSEFERNO_EFFORT_*` | Effort per task: `ANALYZE`, `RESEARCH`, `SYNTHESIZE`, `PLAN`, `DRAFT`, `CRITIQUE`, `IMAGES`, `DETECT` | see `config.py` |
| `PROSEFERNO_DEMO` | Demo mode (canned responses) | `false` |
| `PROSEFERNO_NO_BROWSER` | Do not open a browser on start | unset |
| `ANTHROPIC_API_KEY` | Claude API key (overrides *Sign in with Claude*) | unset |
| `PROSEFERNO_AI_DETECTION` | Claude judge in the AI-detection report | `true` |

Values saved in the app (connection, model, passes, fallback, AI-detection judge) take precedence over environment defaults.

## Claude credentials, in order

1. An API key saved in Proseferno (OS keychain).
2. `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN` in the environment.
3. The active Anthropic CLI profile from *Sign in with Claude* (`ant auth login`).

An environment API key silently overrides a signed-in profile; the Settings page warns you when that happens.

These apply to the **Anthropic API** connection only.

## Using your Claude subscription (Pro or Max)

Choose **Settings → Claude → Claude subscription** to have Proseferno use your Claude plan instead of API credits.

How it works: Anthropic does not let third-party apps sign in with a Claude.ai account or use subscription credentials themselves ([Anthropic's policy](https://code.claude.com/docs/en/legal-and-compliance)). It does allow you to use your own subscription in the unmodified Claude Code CLI. So Proseferno runs *your* Claude Code in headless mode (`claude -p`) for every model call. Proseferno never sees your Claude credentials.

Setup:

1. [Install Claude Code](https://code.claude.com/docs/en/setup) and keep it current (`claude update`). New models need recent versions; for example, Claude Opus 5.5 needs Claude Code 2.1.280 or newer.
2. In Settings, choose **Claude subscription**, then **Sign in with Claude** if you are not signed in. This runs Claude Code's own `claude auth login` in your browser. Pick your Claude account, not Console.
3. Click **Test connection**. It shows your plan (for example "Claude Pro plan") without using any of your limits.

What to expect:

- Usage counts toward your plan's 5-hour and weekly limits. A full post with images is many calls. When you hit a limit, the error says when it resets, and you can switch to the API meanwhile.
- Each call is isolated. Proseferno's prompt replaces Claude Code's own system prompt, and the call runs with no tools (web search only for research), no MCP servers, no settings, hooks or CLAUDE.md, no saved session, and an empty working folder. Claude Code still adds a little context of its own, such as today's date.
- `ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN` are removed from Claude Code's environment, because Claude Code would otherwise bill the API instead of your plan.
- The refusal fallback and Proseferno's prompt-cache hints do not apply. Claude Code handles caching, retries and thinking itself.
- Proseferno runs at most three Claude Code processes at once.

## Command line

```bash
uv run --project backend proseferno --help
```

```text
--host HOST   --port PORT   --open (browser)   --reload (development)   --demo
```
