# Brand palette

Proseferno uses the **inferno** color map (from matplotlib's perceptually uniform maps), dark to light:

| Swatch | Hex | Used for |
| --- | --- | --- |
| ![](https://img.shields.io/badge/-%20%20%20-000004) | `#000004` | Darkest ink |
| ![](https://img.shields.io/badge/-%20%20%20-1b0c41) | `#1b0c41` | Light-mode text, night surfaces, code blocks |
| ![](https://img.shields.io/badge/-%20%20%20-4a0c6b) | `#4a0c6b` | Logo badge, primary hover (day) |
| ![](https://img.shields.io/badge/-%20%20%20-781c6d) | `#781c6d` | Primary (day), chart default |
| ![](https://img.shields.io/badge/-%20%20%20-a52c60) | `#a52c60` | Accents |
| ![](https://img.shields.io/badge/-%20%20%20-cf4446) | `#cf4446` | Flame gradient start |
| ![](https://img.shields.io/badge/-%20%20%20-ed6925) | `#ed6925` | Accent, focus ring (day) |
| ![](https://img.shields.io/badge/-%20%20%20-fb9b06) | `#fb9b06` | Primary (night), robot eyes |
| ![](https://img.shields.io/badge/-%20%20%20-f7d13d) | `#f7d13d` | Robot head |
| ![](https://img.shields.io/badge/-%20%20%20-fcffa4) | `#fcffa4` | Highlights, light text on dark |

Theme tokens (surfaces, text, borders) are defined once in `frontend/src/index.css` for day and night; components use the tokens, never raw hex values. Text/background pairs meet WCAG AA contrast.

## Logo files

- `logo-mark.svg`: the robot blogger badge (app icon, favicon source)
- `logo.svg` / `logo-dark.svg`: horizontal lockup for light and dark backgrounds
- `social-preview.png`: 1280×640 repository social preview

Regenerate the PNG/ICO renders after editing the SVGs:

```bash
uv run --project backend python backend/scripts/render_brand.py
```
