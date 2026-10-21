"""Render brand PNG/ICO assets from the SVG sources.

Run from the repository root:  uv run --project backend python assets/brand/render_brand.py
"""

from __future__ import annotations

import io
from pathlib import Path

import resvg_py
from PIL import Image

HERE = Path(__file__).resolve().parent
PUBLIC = HERE.parents[1] / "frontend" / "public"


def png(svg_path: Path, width: int, background: str | None = None) -> bytes:
    return bytes(resvg_py.svg_to_bytes(svg_string=svg_path.read_text(encoding="utf-8"), width=width, background=background))


def main() -> None:
    mark = HERE / "logo-mark.svg"
    (HERE / "logo-mark-512.png").write_bytes(png(mark, 512))
    (HERE / "logo-1480.png").write_bytes(png(HERE / "logo.svg", 1480))
    (HERE / "logo-dark-1480.png").write_bytes(png(HERE / "logo-dark.svg", 1480))
    # Social preview (GitHub recommends 1280x640).
    social = Image.new("RGB", (1280, 640), "#1b0c41")
    lockup = Image.open(io.BytesIO(png(HERE / "logo-dark.svg", 1100))).convert("RGBA")
    social.paste(lockup, ((1280 - lockup.width) // 2, (640 - lockup.height) // 2), lockup)
    social.save(HERE / "social-preview.png")

    PUBLIC.mkdir(parents=True, exist_ok=True)
    (PUBLIC / "logo-mark.svg").write_text(mark.read_text(encoding="utf-8"), encoding="utf-8")
    (PUBLIC / "apple-touch-icon.png").write_bytes(png(mark, 180))
    (PUBLIC / "icon-512.png").write_bytes(png(mark, 512))
    icons = [Image.open(io.BytesIO(png(mark, size))).convert("RGBA") for size in (16, 32, 48, 64)]
    icons[-1].save(PUBLIC / "favicon.ico", sizes=[(s, s) for s in (16, 32, 48, 64)], append_images=icons[:-1])
    print("Brand assets rendered.")


if __name__ == "__main__":
    main()
