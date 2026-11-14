"""The drawing surface for code-laid-out opening images.

Shapes are SVG written by code (never by a model) and rasterized by resvg; every string is then fitted to its box and
drawn with Pillow in the bundled fonts, so text is always crisp and never overflows. Parallel texts (tiles, rows,
steps) share one font size through ``group``.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass, field, replace

from PIL import Image, ImageDraw

from proseferno.images.memes.text import Fitted, Style, draw_fitted, fit_text
from proseferno.images.render import SVG_NS, svg_to_png

W, H = 1600, 900
MX = 90
# Platforms crop the thumbnail from the centre, as wide as 5:2 (1600x640): everything that matters stays in this band.
SAFE_TOP, SAFE_BOTTOM = (H - 640) // 2, (H + 640) // 2

Box = tuple[int, int, int, int]


def esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _rgb(color: str) -> tuple[int, int, int]:
    value = color.lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    try:
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
    except (ValueError, IndexError):
        return 0, 0, 0


def _hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c))):02x}" for c in rgb)


def mix(a: str, b: str, t: float) -> str:
    """``a`` moved ``t`` of the way to ``b``."""
    ra, rb = _rgb(a), _rgb(b)
    return _hex(tuple(x + (y - x) * t for x, y in zip(ra, rb, strict=True)))  # type: ignore[arg-type]


def luminance(color: str) -> float:
    def channel(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in _rgb(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def readable_on(background: str) -> str:
    return "#14101f" if contrast(background, "#14101f") >= contrast(background, "#ffffff") else "#ffffff"


@dataclass(frozen=True)
class Theme:
    bg: str
    bg2: str
    ink: str
    muted: str
    panel: str
    line: str
    accents: tuple[str, ...]

    @property
    def dark(self) -> bool:
        return luminance(self.bg) < 0.2

    def accent(self, i: int) -> str:
        return self.accents[i % len(self.accents)]

    def style(self, role: str) -> Style:
        return {
            "headline": Style("heavy", self.ink, 78, line_spacing=1.08),
            "subhead": Style("regular", self.muted, 36, line_spacing=1.2),
            "label": Style("bold", self.ink, 44, line_spacing=1.12),
            "detail": Style("regular", self.muted, 32, line_spacing=1.22),
            "number": Style("heavy", self.accent(0), 300, line_spacing=1.0),
            "value": Style("bold", self.ink, 30),
            "tick": Style("regular", self.muted, 24),
            "small": Style("regular", self.muted, 22, line_spacing=1.15),
            "badge": Style("heavy", readable_on(self.accent(0)), 40),
            "mono": Style("mono", self.ink, 32, line_spacing=1.2),
        }[role]


INFERNO_DARK = Theme(
    bg="#1b0c41",
    bg2="#07041a",
    ink="#ffffff",
    muted="#d9c9f2",
    panel="#2b1260",
    line="#4f2a8a",
    accents=("#fb9b06", "#ed6925", "#cf4446", "#f7d13d", "#a52c60", "#fcffa4"),
)


def theme_for(palette: tuple[str, ...] = ()) -> Theme:
    """The house theme, or one built from a brand palette (3+ colors): its darkest color becomes the background
    when it is dark enough, otherwise the image is light with the palette as accents."""
    colors = [c for c in palette if c.startswith("#") and len(c.lstrip("#")) in (3, 6)]
    if len(colors) < 3:
        return INFERNO_DARK
    ordered = sorted(colors, key=luminance)
    darkest = ordered[0]
    if luminance(darkest) < 0.08:
        accents = tuple(c for c in ordered[1:] if contrast(c, darkest) >= 2.2) or ("#fb9b06", "#f7d13d")
        return Theme(
            bg=darkest,
            bg2=mix(darkest, "#000000", 0.6),
            ink="#ffffff",
            muted=mix("#ffffff", darkest, 0.22),
            panel=mix(darkest, "#ffffff", 0.08),
            line=mix(darkest, "#ffffff", 0.22),
            accents=accents,
        )
    accents = tuple(c for c in ordered if contrast(c, "#ffffff") >= 2.2) or ("#781c6d", "#cf4446")
    return Theme(
        bg="#ffffff",
        bg2=mix("#ffffff", ordered[-1], 0.25),
        ink="#14101f",
        muted="#4b4560",
        panel=mix("#ffffff", accents[0], 0.07),
        line=mix("#ffffff", "#14101f", 0.18),
        accents=accents,
    )


@dataclass
class Text:
    box: Box
    text: str
    style: Style
    align: str = "center"
    valign: str = "center"
    group: str = ""


@dataclass
class Canvas:
    theme: Theme
    shapes: list[str] = field(default_factory=list)
    texts: list[Text] = field(default_factory=list)

    def add(self, svg: str) -> None:
        self.shapes.append(svg)

    def rect(self, box: Box, fill: str, *, rx: int = 0, opacity: float = 1.0, stroke: str = "", stroke_width: int = 0) -> None:
        x, y, w, h = box
        extra = f' stroke="{stroke}" stroke-width="{stroke_width}"' if stroke else ""
        op = f' opacity="{opacity:.3g}"' if opacity < 1 else ""
        self.add(f'<rect x="{x}" y="{y}" width="{max(0, w)}" height="{max(0, h)}" rx="{rx}" fill="{fill}"{op}{extra}/>')

    def line(self, x1: float, y1: float, x2: float, y2: float, color: str, width: float = 3, *, dash: str = "") -> None:
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" '
            f'stroke-width="{width}" stroke-linecap="round"{d}/>'
        )

    def circle(self, cx: float, cy: float, r: float, fill: str, *, stroke: str = "", stroke_width: float = 0) -> None:
        extra = f' stroke="{stroke}" stroke-width="{stroke_width}"' if stroke else ""
        self.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}"{extra}/>')

    def arrow(self, x1: float, y1: float, x2: float, y2: float, color: str, width: float = 5) -> None:
        """A straight arrow with a drawn head (no marker defs, so nothing depends on ids)."""
        angle = math.atan2(y2 - y1, x2 - x1)
        head = width * 3.6
        bx, by = x2 - head * math.cos(angle), y2 - head * math.sin(angle)
        self.line(x1, y1, bx, by, color, width)
        left = (bx + head * 0.6 * math.sin(angle), by - head * 0.6 * math.cos(angle))
        right = (bx - head * 0.6 * math.sin(angle), by + head * 0.6 * math.cos(angle))
        self.add(f'<polygon points="{x2:.1f},{y2:.1f} {left[0]:.1f},{left[1]:.1f} {right[0]:.1f},{right[1]:.1f}" fill="{color}"/>')

    def text(
        self, box: Box, text: str, role: str, *, align: str = "center", valign: str = "center", group: str = "", fill: str = ""
    ) -> None:
        if not text.strip():
            return
        style = self.theme.style(role)
        if fill:
            style = replace(style, fill=fill)
        self.texts.append(Text(box, text.strip(), style, align, valign, group))


def frame(canvas: Canvas, headline: str, subhead: str = "", sources: str = "") -> Box:
    """The shared frame: an accent rule, the headline, the subhead and the source line. Returns the body box."""
    theme = canvas.theme
    canvas.rect((MX, SAFE_TOP + 4, 96, 8), theme.accent(0), rx=4)
    canvas.text((MX, SAFE_TOP + 22, W - 2 * MX, 104), headline, "headline", align="left")
    top = SAFE_TOP + 136
    if subhead.strip():
        canvas.text((MX, top, W - 2 * MX, 46), subhead, "subhead", align="left")
        top += 64
    else:
        top += 14
    bottom = SAFE_BOTTOM - 6
    if sources.strip():
        canvas.text((MX, SAFE_BOTTOM - 32, W - 2 * MX, 28), sources, "small", align="left")
        bottom = SAFE_BOTTOM - 46
    return (MX, top, W - 2 * MX, bottom - top)


def render(canvas: Canvas) -> tuple[bytes, int, int]:
    theme = canvas.theme
    background = (
        f'<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{theme.bg}"/>'
        f'<stop offset="1" stop-color="{theme.bg2}"/></linearGradient></defs><rect width="{W}" height="{H}" fill="url(#bg)"/>'
    )
    svg = f'<svg xmlns="{SVG_NS}" width="{W}" height="{H}" viewBox="0 0 {W} {H}">{background}{"".join(canvas.shapes)}</svg>'
    png, _, _ = svg_to_png(svg, width=W, background=theme.bg)
    with Image.open(io.BytesIO(png)) as source:
        img = source.convert("RGB")
    draw = ImageDraw.Draw(img)
    caps: dict[str, int] = {}
    for item in canvas.texts:
        if item.group:
            size = fit_text(draw, item.text, item.box[2], item.box[3], item.style).size
            caps[item.group] = min(size, caps.get(item.group, size))
    for item in canvas.texts:
        fitted: Fitted = fit_text(draw, item.text, item.box[2], item.box[3], item.style, min_size=12, max_size=caps.get(item.group))
        draw_fitted(draw, fitted, item.box, item.style, align=item.align, valign=item.valign)
    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue(), img.width, img.height
