# Changelog

All notable changes to Proseferno are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- AI-generation detection: a 0-100 "reads as human" score on every post (a scan calibrated to the author's own samples plus a Claude judge), a full report with flagged passages and one-click *Humanize*, *Re-check* after edits, AI tells fed into the editor pass, and `evals/ai_detection.py`.
- LinkedIn: platform-aware writing, copy-ready article HTML, a 1920×1080 cover, a feed post (template or written by Claude in the persona's voice, under 3,000 characters), and a swipeable document carousel as PDF and editable PPTX.
- Persona switcher in the sidebar: switch personas and pin any earlier voice soul version.
- Voice soul versions can be named; personas can be renamed inline; *Save as new persona* branches a separately named persona from any version, and *Regenerate* can create a new persona instead of a new version.
- Persona defaults for every dial: length, image count, humor, education, code, platform, and new 0-10 style dials (storytelling, opinion strength, formality, technical depth, skimmability) where 5 means "as I write". The same dials are available per post.
- `icon` image kind; richer SVG art direction for hero and illustration images.
- Additive database migration so existing databases gain new columns automatically.

### Changed

- "Voice soul" is now **voice profile** everywhere (UI, API routes `/voice-profile`, `voice_profile.md`, code, docs). Existing databases and saved files are migrated automatically on startup; earlier entries below keep the old name.
- Every image is now drawn by Claude (SVG illustrations, icons, diagrams and memes; Vega-Lite charts). Credits name the Claude model, e.g. "Made with Claude Opus 5.5 (SVG)".

### Removed

- Cloudflare Workers AI / FLUX.2 [klein] image generation and its settings.

### Fixed

- Writing-sample cards collapsed into a narrow column with one word per line (form controls could not override their full width).

## [0.1.0] - 2026-10-20

### Added

- Personas with own-writing and influence samples; exactly one persona is on at a time.
- Sample ingestion for .docx, .pdf, .md, .txt, .html and URLs, with Medium-export clean-up (UI chrome removal, heading recovery, caption detection) and stylometrics.
- Voice soul synthesis with per-sample analysis, measured style baseline, optional web research on best practices, versions, and in-app editing.
- Post generation from a prompt or outline with smart-default dials: plan, streamed draft, voice-fidelity critique and revision, measured style score.
- Images: hero/thumbnail, diagrams (sanitized SVG), charts (Vega-Lite), illustrations, screenshot placeholders and a closing meme; FLUX.2 [klein] on Cloudflare Workers AI with a Claude SVG fallback; credits, alt text, redraw, replace and version history.
- Exports for Medium, Substack, Gumroad (PDF) and Markdown/Word, as zip bundles or copy-ready HTML.
- Sign in with Claude (Anthropic CLI OAuth) or an API key stored in the OS keychain.
- Day and night themes in an inferno palette, robot-blogger logo, first-run setup guide.
- One-click `launch.bat` / `launch.sh`, developer `dev.bat`, demo mode, CI, Playwright smoke test, and a voice-fidelity eval.
