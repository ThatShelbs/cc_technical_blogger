"""The opening image as a reader first meets it: a feed card (the 1200x630 thumbnail crop with the title under it).

The final pick judges candidates as feed cards, because the thumbnail and the title are sold together: a picture that
fights the title, or whose point is cropped away, loses here.
"""

from __future__ import annotations

import io

from PIL import Image, ImageDraw

from inferno_ghostwriter.images.memes.text import Style, draw_fitted, fit_text

CARD_W, CARD_H = 1200, 630
TITLE_H = 150
TITLE_STYLE = Style("heavy", "#14101f", 54, line_spacing=1.1)


def feed_card(png: bytes, title: str, *, fit: str = "cover") -> bytes:
    """A 1200x780 card: the image cropped (or padded) to 1200x630 and the title in a white band below."""
    with Image.open(io.BytesIO(png)) as source:
        img = source.convert("RGB")
    if fit == "contain":
        scale = min(CARD_W / img.width, CARD_H / img.height)
        fitted = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.Resampling.LANCZOS)
        thumb = Image.new("RGB", (CARD_W, CARD_H), img.getpixel((0, 0)))  # type: ignore[arg-type]
        thumb.paste(fitted, ((CARD_W - fitted.width) // 2, (CARD_H - fitted.height) // 2))
    else:
        scale = max(CARD_W / img.width, CARD_H / img.height)
        resized = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.Resampling.LANCZOS)
        left, top = (resized.width - CARD_W) // 2, (resized.height - CARD_H) // 2
        thumb = resized.crop((left, top, left + CARD_W, top + CARD_H))
    card = Image.new("RGB", (CARD_W, CARD_H + TITLE_H), "#ffffff")
    card.paste(thumb, (0, 0))
    draw = ImageDraw.Draw(card)
    box = (36, CARD_H + 18, CARD_W - 72, TITLE_H - 36)
    fitted_title = fit_text(draw, title.strip() or " ", box[2], box[3], TITLE_STYLE, min_size=20)
    draw_fitted(draw, fitted_title, box, TITLE_STYLE, align="left", valign="center")
    out = io.BytesIO()
    card.save(out, format="PNG", optimize=True)
    return out.getvalue()
