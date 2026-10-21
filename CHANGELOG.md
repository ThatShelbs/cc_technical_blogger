# Changelog

All notable changes to Proseferno are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

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
