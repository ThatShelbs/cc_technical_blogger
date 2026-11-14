# Changelog

All notable changes to Proseferno are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- **Posts no longer point at examples that are not there.** "Here is the top of the file:" followed by nothing is gone. The default image count now follows how often you use images (measured from your writing), screenshots are drawn by Claude as a mock of the screen the post describes (use **Replace** for the real one), code the author would show as a screenshot is written as a code block, the editor is shown every lead-in with nothing after it, and anything still missing after editing becomes a drawn image right where the text promised it. Older posts can be fixed in place with `POST /api/projects/{id}/examples`.

### Added

- **Formulas: choose or build the shape of a post.** A formula is an article type (deep narrative, top N countdown, how-to, tutorial, X vs. Y comparison, explainer, case study or build walkthrough, hands-on, lessons learned, opinion, tool review or update), an opener (five joke styles, personal anecdote, cold open, result first, controversial idea, myth, surprising number, bold promise, straight to the point, the problem, a question, what just changed), a body structure (18, from narrative arc and countdown to step by step, criterion by criterion and experiment report) and a closer (12, from full circle and one-line kicker to verdict, next step and prediction). Each menu lists the styles that suit the article type first; *Use the classic formula* fills all three; every part also takes your own instructions. Save formulas under a name, reuse them on any post, and set a default formula per persona. Parts left automatic are written as your voice profile describes, the editor checks the draft against the formula, and the closing meme always follows the closer. See `docs/formulas.md`.
- **Formulas: a smart default and a shuffle.** Left on automatic, the article type is read from your brief ("How to ...", "X vs. Y", "Top 7 ...", "What I learned ..."); the form shows the guess as you type, and a brief that does not say keeps your usual shape. *Shuffle the formula* draws a new opener, body and closer from the styles that suit the article type, a dice by each part redraws just that part, and *Try another formula* on a written post opens the settings to shuffle and regenerate.
- **References in every post.** After the voice edit, Claude plans where references would strengthen the post, researches each one on the web and weaves it in with small edits in your voice: sources for claims, famous quotes, widely shared posts from AI/ML voices, tutorials, packages and videos, and related articles (at least five by default, more for long posts; tutorials and related reads can go in a short *Go deeper* list before the meme). Every link must come from the search and every quote must match it word for word, and links that are gone are dropped. Each reference has **Redraw**, **Switch to…** another kind, **Versions** and **Remove**, from a chip next to its link or the new **References** card; *Find references* adds them to older posts. New `reference_count` / `reference_kinds` dials and a persona default.
- *Add source* and *Add quote* now check their link and quote against the search and appear in the References card.

- **Regenerate any highlighted section.** Select text in the preview (or in *Edit Markdown*) and choose *Rewrite*, *Compact*, *Expand*, *Add source*, *Add quote*, or a *Custom brief* such as "make it more positive". Only that span changes, in your voice; sources and quotes come from a web search so links are real and quotes are attributed, and nothing is added if none is found. The result is re-scored for AI-detection and fidelity, kept in the undo history, and custom briefs are remembered as lessons.
- **Memes people remember**: the closing meme now comes from a writers' room. Claude reads the whole post (including its planned running jokes), pitches five jokes across 18 formats (Drake-style *Nope / Yep*, pointing twins, distracted robot, expanding brain, *This is fine*, two buttons, the midwit bell curve, a four-step plan, a terrible 3D pie, a spurious correlation chart, Venn diagrams, three- and four-panel comics, a team chat, a terminal, a Nutrition Facts label and an alignment chart), scores them and draws the best. Layout and typography are done by code, so text always fits and panels line up. *New idea* tries the next pitch, a format menu remakes the meme in the format you choose, and `scripts/meme_gallery.py` renders every format for review.
- **A meme you can steer.** *Ideas* on the meme card shows all five jokes Claude pitched; pick any one, and *Words* lets you retype the meme's text with the art kept and no call to Claude. Memes with no art (chat, terminal, Nutrition Facts, alignment chart, pie, correlation chart, Venn) are now made in one Claude call instead of two, and switching to one is instant. Claude avoids the formats your last three memes used, and knows the post's formula: the meme adds a beat after the closer instead of repeating it, and a post that opens on a joke can have that joke brought back.
- **Images that look the same everywhere and fail less.** Fonts are bundled (Anton, Inter, Comic Neue, JetBrains Mono; SIL Open Font License), so memes no longer depend on the fonts installed on the machine. Any image that cannot be drawn gets one more try with the error quoted back, small XML slips are repaired without a retry, and a meme format that cannot be drawn is replaced by the next-best joke (the card says so) instead of a garbled caption meme. Long posts keep their ending when the meme is pitched, each image knows what the others show, heroes keep their subject clear of thumbnail crops, and charts take the brand palette and say *Illustrative data* in the image when the numbers are made up.
- **Learns from your edits**: Proseferno remembers what you cut, replace and ask for in generated posts (manual edits are diffed; tweak feedback is kept) and writes every later post, and the next voice profile, with those lessons. Review or forget them per persona.
- **Voice profile settings**: target length of the voice profile, words read from each sample, a minimum sample length, and how much influence samples shape technique (0-10).
- **Callbacks**: each post plans one to three key concepts and running jokes (only at humor 3+) that it sets up, revisits with something new, and pays off. The editor scores them.
- **Edit an image by instruction**: describe the change ("make the arrows orange") and Claude edits the current SVG or chart instead of drawing a new one.
- **Per-post image brand kit**: style, palette, font and recurring motif for one post's images, with *Redraw all images*.
- **Windows installer**: `packaging\build_windows.bat` builds a standalone app (PyInstaller) and a per-user installer (Inno Setup) that needs no Python or Node; data lives in `%LOCALAPPDATA%\Proseferno`.
- **A first run that works with no files and no keys.** *Use 3 sample posts* in the setup guide adds three bundled posts by a fictional "Sample Author", so a voice profile and a post can be generated with nothing uploaded. The Posts page offers *See an example post* (an offline-built persona, voice profile and finished post with credited images; remove it in one click), New post has *Use an example prompt*, and demo mode now opens seeded with the example (`PROSEFERNO_DEMO_SEED=false` turns that off).
- `proseferno doctor`: checks Python, the data folder, the web build, Node.js, the port, the keychain, the Claude connection, Claude Code and Windows path length, and prints a fix for each problem. A bare first launch from a terminal (no data, no Claude connection) offers to start in demo mode.
- Developer scripts in `scripts/`: `setup` (one idempotent install of uv, Node.js 22+, packages and the optional browser), `dev` (now with a macOS/Linux version), and `check` (every CI check in CI order, with `--fix` and `--e2e`). On Windows they move the Python environment to a short path when the folder is deeply nested.
- `docs/onboarding.md`: a cheat sheet, a first-day path, a "change X, edit Y" map, a glossary and troubleshooting. `docs/architecture.md` gains the repository layout and a "Life of a post" trace. CONTRIBUTING gains good first tasks. Every backend package has a docstring.
- `launch.sh` opens an already-running instance, and points to `proseferno doctor` when setup fails (as `launch.bat` does).
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

- Word exports keep link URLs ("text (url)") and style blockquotes as quotes.
- Web research on the API connection keeps text and citations from every round when a search turn pauses, not just the last one.

- The first real persona becomes active even when the example persona exists (a persona is made active when none other than the example is).
- Repository tidy-up: `dev.bat` moved to `scripts/`, `SECURITY.md` and `CODE_OF_CONDUCT.md` to `.github/`, `render_brand.py` to `backend/scripts/`, the e2e sample post to `frontend/e2e/fixtures/`, and the two near-empty sub-READMEs folded into `docs/onboarding.md`. `my_writing_examples/` is no longer tracked by git (it was already ignored; existing files stay on your disk). CI now lints and format-checks `backend/evals` too, and the e2e job covers a seeded demo tour as well as the first run.
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
