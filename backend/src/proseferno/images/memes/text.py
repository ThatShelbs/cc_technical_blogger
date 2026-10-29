"""Fonts and text fitting for memes: every string is sized and wrapped to its box, so text never overflows."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path

from PIL import ImageDraw, ImageFont

Font = ImageFont.FreeTypeFont | ImageFont.ImageFont

# Bundled fonts (if present) win, then common system fonts, so output looks alike on every OS.
_BUNDLED = Path(__file__).parent / "fonts"
_DIRS = [
    _BUNDLED,
    Path("C:/Windows/Fonts"),
    Path("/System/Library/Fonts/Supplemental"),
    Path("/Library/Fonts"),
    Path("/usr/share/fonts/truetype/msttcorefonts"),
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/share/fonts/dejavu"),
]
_FILES = {
    "impact": ["Anton-Regular.ttf", "impact.ttf", "Impact.ttf", "ariblk.ttf", "DejaVuSans-Bold.ttf"],
    "heavy": ["Inter-Black.ttf", "ariblk.ttf", "Arial Black.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"],
    "bold": ["Inter-Bold.ttf", "segoeuib.ttf", "arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf"],
    "regular": ["Inter-Regular.ttf", "segoeui.ttf", "arial.ttf", "Arial.ttf", "DejaVuSans.ttf"],
    "comic": ["ComicNeue-Bold.ttf", "comicbd.ttf", "Comic Sans MS Bold.ttf", "segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"],
    "mono": ["JetBrainsMono-Regular.ttf", "consola.ttf", "Menlo.ttc", "Courier New.ttf", "DejaVuSansMono.ttf"],
}


@dataclass(frozen=True)
class Style:
    font: str
    fill: str
    max_size: int
    stroke: str | None = None
    stroke_ratio: float = 0.0
    upper: bool = False
    line_spacing: float = 1.15


STYLES = {
    "impact": Style("impact", "#ffffff", 120, stroke="#000000", stroke_ratio=1 / 18, upper=True, line_spacing=1.08),
    "outline": Style("heavy", "#ffffff", 64, stroke="#000000", stroke_ratio=1 / 8),
    "dark": Style("bold", "#1b0c41", 72),
    "light": Style("heavy", "#ffffff", 60),
    "title": Style("heavy", "#1b0c41", 60),
    "bubble": Style("comic", "#14101f", 46),
    "mono": Style("mono", "#fcffa4", 34, line_spacing=1.25),
    "ui": Style("regular", "#1d1c1d", 34, line_spacing=1.3),
    "ui_bold": Style("bold", "#1d1c1d", 34),
}


@cache
def font_path(role: str) -> str | None:
    for name in _FILES[role]:
        for directory in _DIRS:
            candidate = directory / name
            if candidate.exists():
                return str(candidate)
    return None


@cache
def load_font(role: str, size: int) -> Font:
    path = font_path(role)
    return ImageFont.truetype(path, size) if path else ImageFont.load_default(size=size)


@dataclass
class Fitted:
    font: Font
    size: int
    lines: list[str]
    stroke: int
    line_height: int
    width: int
    height: int
    broke: bool = False


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: Font, width: float) -> tuple[list[str], bool]:
    """Greedy word wrap by measured width; also says whether a word had to be broken."""
    lines: list[str] = []
    broke = False
    for paragraph in text.split("\n"):
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}".strip()
            if draw.textlength(candidate, font=font) <= width:
                current = candidate
                continue
            if current:
                lines.append(current)
            # A single word wider than the box is broken by characters.
            while draw.textlength(word, font=font) > width and len(word) > 1:
                broke = True
                cut = len(word) - 1
                while cut > 1 and draw.textlength(word[:cut], font=font) > width:
                    cut -= 1
                lines.append(word[:cut])
                word = word[cut:]
            current = word
        lines.append(current)
    while lines and not lines[-1]:
        lines.pop()
    return lines or [""], broke


def _measure(draw: ImageDraw.ImageDraw, text: str, style: Style, size: int, width: int) -> Fitted:
    font = load_font(style.font, size)
    stroke = round(size * style.stroke_ratio) if style.stroke else 0
    lines, broke = _wrap(draw, text, font, width - 2 * stroke)
    line_height = round(size * style.line_spacing)
    widest = max(int(draw.textlength(line, font=font)) for line in lines) + 2 * stroke
    return Fitted(font, size, lines, stroke, line_height, widest, line_height * len(lines) + 2 * stroke, broke)


def fit_text(
    draw: ImageDraw.ImageDraw, text: str, width: int, height: int, style: Style, min_size: int = 12, max_size: int | None = None
) -> Fitted:
    """The largest font size at which ``text`` fits ``width`` x ``height``, preferring sizes that keep words whole;
    at the minimum size, extra lines are cut."""
    if style.upper:
        text = text.upper()
    for allow_breaks in (False, True):
        low, high = min_size, max(min_size, min(max_size or style.max_size, height))
        best = None
        while low <= high:
            size = (low + high) // 2
            fitted = _measure(draw, text, style, size, width)
            if fitted.height <= height and fitted.width <= width and (allow_breaks or not fitted.broke):
                best, low = fitted, size + 1
            else:
                high = size - 1
        if best is not None:
            return best
    fitted = _measure(draw, text, style, min_size, width)
    keep = max(1, (height - 2 * fitted.stroke) // fitted.line_height)
    if len(fitted.lines) > keep:
        fitted.lines = [*fitted.lines[: keep - 1], fitted.lines[keep - 1].rstrip(".,;: ") + "…"]
        fitted.height = fitted.line_height * keep + 2 * fitted.stroke
    return fitted


def draw_fitted(
    draw: ImageDraw.ImageDraw,
    fitted: Fitted,
    box: tuple[int, int, int, int],
    style: Style,
    *,
    align: str = "center",
    valign: str = "center",
    fill: str | None = None,
) -> None:
    x, y, w, h = box
    top = y + (h - fitted.height) // 2 if valign == "center" else y
    top += fitted.stroke
    for line in fitted.lines:
        line_width = draw.textlength(line, font=fitted.font)
        left: float
        if align == "left":
            left = x + fitted.stroke
        elif align == "right":
            left = x + w - line_width - fitted.stroke
        else:
            left = x + (w - line_width) / 2
        # Pillow anchors text at the ascender; nudge so the line's visual center sits in its slot.
        draw.text(
            (left, top + (fitted.line_height - fitted.size) * 0.35),
            line,
            font=fitted.font,
            fill=fill or style.fill,
            stroke_width=fitted.stroke,
            stroke_fill=style.stroke,
        )
        top += fitted.line_height
