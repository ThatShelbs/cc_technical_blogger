"""Cut the brand assets out of the supplied artwork.

The source is ``assets/brand/source-banner-and-icon.png``: the banner on top and the app icon below on white.
Run from the repository root:  uv run --project backend python backend/scripts/render_brand.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parents[2]
HERE = REPO_ROOT / "assets" / "brand"
PUBLIC = REPO_ROOT / "frontend" / "public"
SOURCE = HERE / "source-banner-and-icon.png"


def split_source(im: Image.Image) -> tuple[Image.Image, Image.Image]:
    """The banner is the rows above the first all-white row; the icon is the non-white block below it."""
    white = np.array(im.convert("RGB")).min(axis=2) > 245
    first_white = next(y for y in range(im.height) if white[y].all())
    banner = im.crop((0, 0, im.width, first_white))
    lower = np.array(im.convert("RGB")).min(axis=2)[first_white:] < 200
    cols = np.where(lower.any(axis=0))[0]
    rows = np.where(lower.any(axis=1))[0]
    box = (int(cols.min()), int(rows.min()) + first_white, int(cols.max()) + 1, int(rows.max()) + 1 + first_white)
    return banner, rounded(im.crop(box))


def rounded(icon: Image.Image) -> Image.Image:
    """Square the icon crop and clear the white corners with a rounded-rectangle mask."""
    size = max(icon.size)
    icon = icon.convert("RGB").resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size * 4 - 1, size * 4 - 1), radius=int(size * 4 * 0.2), fill=255)
    out = icon.convert("RGBA")
    out.putalpha(mask.resize((size, size), Image.LANCZOS))
    return out


def main() -> None:
    banner, icon = split_source(Image.open(SOURCE))
    banner.convert("RGB").save(HERE / "banner.png", optimize=True)
    icon.resize((512, 512), Image.LANCZOS).save(HERE / "logo-mark-512.png", optimize=True)

    # Social preview (GitHub recommends 1280x640): the banner, centered on its own dark edge colour.
    bg = banner.convert("RGB").getpixel((4, 4))
    social = Image.new("RGB", (1280, 640), bg)
    scaled = banner.convert("RGB").resize((1280, round(banner.height * 1280 / banner.width)), Image.LANCZOS)
    social.paste(scaled, (0, (640 - scaled.height) // 2))
    social.save(HERE / "social-preview.png", optimize=True)

    PUBLIC.mkdir(parents=True, exist_ok=True)
    icon.resize((256, 256), Image.LANCZOS).save(PUBLIC / "logo-mark.png", optimize=True)
    icon.resize((180, 180), Image.LANCZOS).save(PUBLIC / "apple-touch-icon.png", optimize=True)
    icon.resize((512, 512), Image.LANCZOS).save(PUBLIC / "icon-512.png", optimize=True)
    sizes = (16, 32, 48, 64, 128, 256)
    icon.save(PUBLIC / "favicon.ico", sizes=[(s, s) for s in sizes])
    print("Brand assets rendered.")


if __name__ == "__main__":
    main()
