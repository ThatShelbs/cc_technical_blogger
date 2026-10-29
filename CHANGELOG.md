# Changelog

All notable changes to Proseferno are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **Memes people remember**: the closing meme now comes from a writers' room. Claude reads the whole post (including its planned running jokes), pitches five jokes across 18 formats (Drake-style *Nope / Yep*, pointing twins, distracted robot, expanding brain, *This is fine*, two buttons, the midwit bell curve, a four-step plan, a terrible 3D pie, a spurious correlation chart, Venn diagrams, three- and four-panel comics, a team chat, a terminal, a Nutrition Facts label and an alignment chart), scores them and draws the best. Layout and typography are done by code, so text always fits and panels line up. *New idea* tries the next pitch, a format menu remakes the meme in the format you choose, and `scripts/meme_gallery.py` renders every format for review.
- **Learns from your edits**: Proseferno remembers what you cut, replace and ask for in generated posts (manual edits are diffed; tweak feedback is kept) and writes every later post, and the next voice profile, with those lessons. Review or forget them per persona.
- **Voice profile settings**: target length of the voice profile, words read from each sample, a minimum sample length, and how much influence samples shape technique (0-10).
- **Callbacks**: each post plans one to three key concepts and running jokes (only at humor 3+) that it sets up, revisits with something new, and pays off. The editor scores them.
- **Edit an image by instruction**: describe the change ("make the arrows orange") and Claude edits the current SVG or chart instead of drawing a new one.
- **Per-post image brand kit**: style, palette, font and recurring motif for one post's images, with *Redraw all images*.
- **Windows installer**: `packaging\build_windows.bat` builds a standalone app (PyInstaller) and a per-user installer (Inno Setup) that needs no Python or Node; data lives in `%LOCALAPPDATA%\Proseferno`.
- **Three ways to revise a post**: *Tweak with feedback* (Claude makes surgical edits and keeps the rest of the text and images, redrawing only an image the feedback names), *Edit brief & settings* (see and refine the original brief or the outline Claude planned, change any dial, the platform or the persona, then regenerate), and *Regenerate post*.
- Text version history: *Undo last change* and *Restore* for the last ten versions (before each tweak, passage rewrite, manual save or restore).
- **X** as a platform: X Article writing conventions and an export with a 1500×600 header and a teaser post under 280 characters.
- **Audience** dial: say who the post is for; empty means the author's usual readers.
- **Claude subscription connection**: run Proseferno on your Claude Pro or Max plan instead of API credits. Proseferno runs your own Claude Code CLI headless (`claude -p`), the route Anthropic's policy allows for subscriptions, and never handles Claude credentials. Choose it in Settings → Claude, which shows your plan, Claude Code version and sign-in.
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

- Posts no longer contain `[TODO: ...]` notes to the author; the writer hedges or leaves uncertain facts out, and any TODO that slips through is removed.
- Posts and image captions no longer mention a tool (for example a BI product credited in your samples) unless the brief calls for it, and captions never name a tool other than Claude as an image's maker.
- Reloading a post while one of its images was redrawing showed the full-page generation view.
- Post generation no longer fails on a transient mid-stream Claude error during critique ("Claude API error 200"). Such errors are retried, and if the editing pass still fails, the draft is kept.
- A low Anthropic API credit balance now says so plainly instead of showing a raw 400 error.
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
