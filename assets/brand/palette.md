# Brand palette

Inferno Ghostwriter uses the **inferno** color map (from matplotlib's perceptually uniform maps), dark to light:

| Swatch | Hex | Used for |
| --- | --- | --- |
| ![](https://img.shields.io/badge/-%20%20%20-000004) | `#000004` | Darkest ink |
| ![](https://img.shields.io/badge/-%20%20%20-1b0c41) | `#1b0c41` | Light-mode text, night surfaces, code blocks |
| ![](https://img.shields.io/badge/-%20%20%20-4a0c6b) | `#4a0c6b` | Logo badge, primary hover (day) |
| ![](https://img.shields.io/badge/-%20%20%20-781c6d) | `#781c6d` | Primary (day), chart default |
| ![](https://img.shields.io/badge/-%20%20%20-a52c60) | `#a52c60` | Accents |
| ![](https://img.shields.io/badge/-%20%20%20-cf4446) | `#cf4446` | Flame gradient start |
| ![](https://img.shields.io/badge/-%20%20%20-ed6925) | `#ed6925` | Accent, focus ring (day) |
| ![](https://img.shields.io/badge/-%20%20%20-fb9b06) | `#fb9b06` | Primary (night), ghost eyes |
| ![](https://img.shields.io/badge/-%20%20%20-f7d13d) | `#f7d13d` | Ghost glow, mark highlights |
| ![](https://img.shields.io/badge/-%20%20%20-fcffa4) | `#fcffa4` | Highlights, light text on dark |

Theme tokens (surfaces, text, borders) are defined once in `frontend/src/index.css` for day and night; components use the tokens, never raw hex values. Text/background pairs meet WCAG AA contrast.

## Identity

- **Name:** Inferno Ghostwriter. **Tagline:** The AI Ghostwriter for Technical Minds.
- **Mascot:** a friendly spectral ghost at a laptop, with a quill. Never an evil ghost, never a generic robot.
- **Look:** the inferno colormap (deep indigo/purple, violet, magenta, red, orange, yellow) with warm glowing accents, without turning the whole brand into flames. Subtle technical motifs (charts, documents, code, data). Clean, modern type.
- **Audience:** developers, data scientists, analysts, engineers, technical marketers, researchers and subject-matter experts.
- **Pipeline strip:** RESEARCH, OUTLINE, WRITE, OPTIMIZE, PUBLISH.

## Brand files

- `source-banner-and-icon.png`: the supplied artwork (banner on top, app icon below). Everything else is cut from it.
- `banner.png`: the README banner.
- `logo-mark-512.png`: the app icon (rounded square, transparent corners).
- `social-preview.png`: 1280x640 repository social preview.
- `Inferno Ghostwriter Summary.txt`: the original positioning notes.

The app's favicon, touch icon and header mark in `frontend/public/` are cut from the same file. Re-render them after replacing the source:

```bash
uv run --project backend python backend/scripts/render_brand.py
```
