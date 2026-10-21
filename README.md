<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/brand/logo-dark.svg">
    <img alt="Proseferno" src="assets/brand/logo.svg" width="560">
  </picture>
</p>

<p align="center">
  <strong>Write engaging technical blog posts in your own voice.</strong><br>
  Proseferno learns how <em>you</em> write from your past posts, then drafts new ones (with diagrams, charts, a thumbnail and a closing meme) that your readers would swear you wrote yourself.
</p>

<p align="center">
  <a href="../../actions/workflows/ci.yml"><img alt="CI" src="../../actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Python 3.13" src="https://img.shields.io/badge/python-3.13-4a0c6b">
  <img alt="React 19" src="https://img.shields.io/badge/react-19-781c6d">
  <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-ed6925">
</p>

---

![Proseferno editor in day mode](docs/screenshots/editor-day.png)

## Why Proseferno

Most AI writing tools produce the same polished, generic voice. Proseferno is built around one idea: **the post must sound like you.** It studies your writing, measures it, writes a field guide to your voice (your *voice soul*), and then has an editor check every draft against that guide before you see it.

It is specialized for technical writing about data science, Python, data visualization, machine learning, causal inference and experimentation, analytics leadership, analytics at large companies, AI/LLMs/agents, ML platforms (AWS, Snowflake), and building with agentic coding tools.

## Features

- **Learns your voice.** Upload your posts (Word, PDF, Markdown, HTML, or a URL; Medium exports are cleaned up automatically). Add writers you admire as *influences*: Proseferno borrows their techniques, never their identity.
- **Voice soul.** A versioned `voice_soul.md` per persona: your soul, tone, signature moves, structure, title formulas, humor, teaching style, credibility habits, caption format, lexicon, and verbatim voice anchors, grounded in measured statistics from your writing. Regenerate or edit it any time.
- **Optional web research** on current best practices for titles, storytelling, skimmable structure, humor, insight, credibility and teaching.
- **Personas.** Create several (different names, different voices); exactly one is on at a time.
- **One prompt per post.** Type a sentence or a bullet outline. Everything else has smart defaults: length, image count, humor, education level, topic, platform. Open *Customize* for full control.
- **Voice-fidelity loop.** Plan → streamed draft → an editor critiques the draft against your voice soul and example posts → revision. You see a measured style score and the editor's scores.
- **Images that earn their place.** A hero image that doubles as the thumbnail, clarifying diagrams, illustrative charts, screenshot placeholders, and a closing meme, all placed inline and credited ("Author: You; Made with FLUX.2 [klein]"). **Redraw** any image for a new take, **Replace** it with your own, or roll back through its versions.
- **Export** for Medium, Substack, Gumroad (PDF), or Markdown/Word, as a zip or copy-and-paste HTML with images embedded.
- **Day and night themes** in an inferno palette, a one-click Windows launcher, and a demo mode to try everything without API keys.

## Quick start

**Windows:** double-click **`launch.bat`**. The first run installs what it needs (it asks before installing [uv](https://docs.astral.sh/uv/) or Node.js with winget), builds the app, and opens it in your browser.

**macOS / Linux:**

```bash
./launch.sh
```

**Just looking?** Start in demo mode: canned AI responses and placeholder images, no keys, no cost, separate data folder.

```bash
launch.bat --demo
```

Then follow the five-step setup guide in the app:

1. **Connect Claude**: *Sign in with Claude* (browser sign-in through the [Anthropic CLI](https://github.com/anthropics/anthropic-cli/releases), works with your organization's SSO) or paste an Anthropic API key.
2. **Images (optional)**: add a Cloudflare account ID and Workers AI token for FLUX.2 [klein] images. Skip it and Proseferno still draws diagrams, charts and SVG illustrations with Claude.
3. **Persona**: give it a name and a byline for image credits.
4. **Your writing**: drop in three or more of your posts. If you keep them in a `my_writing_examples/` folder in the repo, the app offers to import them in one click (that folder is git-ignored).
5. **Voice soul**: generate it and read it. Edit anything that is off.

Then click **New post**, describe the post, and watch it being written.

## Costs and accounts

| Service | Used for | Billing |
| --- | --- | --- |
| [Claude](https://platform.claude.com) (default model: Claude Opus 5.5) | Voice analysis, voice soul, planning, drafting, editing, image design | Your Claude Console (API) account. *Sign in with Claude* uses Console billing, not a Claude.ai chat subscription. |
| [Cloudflare Workers AI](https://developers.cloudflare.com/workers-ai/) `@cf/black-forest-labs/flux-2-klein-4b` | Hero, illustration and meme images | Your Cloudflare account; includes a daily free allocation. Optional. |

You can switch to Claude Sonnet 5.5 (faster, cheaper) or Claude Fable 5.1 (most capable) in **Settings → Advanced**, and choose 0–2 editing passes.

## How Proseferno keeps your voice

```mermaid
flowchart LR
  A[Your posts<br/>docx, pdf, md, html, URL] --> B[Clean up<br/>Medium chrome, headings, captions]
  B --> C[Measure style<br/>sentence rhythm, I/you rate,<br/>headings and images per word]
  B --> D[Claude analyzes<br/>each post]
  E[Influences] --> D
  F[Optional web research] --> G
  C --> G[Voice soul<br/>voice_soul.md]
  D --> G
  G --> H[Plan]
  I[Your prompt + dials] --> H
  J[Most similar posts<br/>as full examples] --> K
  H --> K[Draft]
  K --> L[Editor critique<br/>vs. voice soul]
  L --> M[Revision]
  M --> N[Images + credits]
  N --> O[Export]
```

Details: [docs/voice-pipeline.md](docs/voice-pipeline.md). To measure voice quality on your own writing, run the [voice-fidelity eval](docs/voice-pipeline.md#measuring-voice-fidelity): it holds out some of your real posts, regenerates them from a brief, and asks a blind judge to spot the real one.

## Privacy

Everything stays on your computer in the `data/` folder: samples, voice souls, posts, images, exports. API keys go into your operating system's keychain (Windows Credential Manager, macOS Keychain, Secret Service), never into files. Content is sent only to the services you configure (Claude, and Cloudflare for images) when you generate something.

## Project layout

```
launch.bat / launch.sh / dev.bat   One-click start and developer mode
backend/                           FastAPI + uv (Python 3.13)
  src/proseferno/
    api/        HTTP routes (auth, settings, personas, samples, voice, projects, images, export, jobs/SSE)
    ingest/     Parsers, Medium clean-up, stylometrics
    voice/      Sample analysis, research, voice soul synthesis, exemplar selection
    writer/     Dials, plan, draft, critique/revise
    images/     Cloudflare FLUX provider, SVG/Vega-Lite renderers, memes, credits
    export/     Medium, Substack, Gumroad (PDF), Markdown/Word bundles
    llm/        Claude client, sign-in resolution
    prompts/    Every prompt, as readable Markdown
  tests/        pytest (fake Claude + fake image model)
  evals/        Voice-fidelity eval (real API, opt-in)
frontend/                          React 19 + Vite + Tailwind CSS 4
  src/pages/    Posts, new post, editor, personas, settings, setup guide
  e2e/          Playwright smoke test (demo mode)
assets/brand/                      Logo and palette
docs/                              Architecture and guides
```

## Documentation

- [Architecture](docs/architecture.md)
- [Voice pipeline and evaluation](docs/voice-pipeline.md)
- [Images](docs/images.md)
- [Exporting](docs/exporting.md)
- [Configuration](docs/configuration.md)
- [Contributing](CONTRIBUTING.md)

## Night mode

![Proseferno editor in night mode](docs/screenshots/editor-night.png)

## License

[MIT](LICENSE) © Shelby Temple
