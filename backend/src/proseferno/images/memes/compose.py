"""Compose a meme from a format and Claude's build: code draws the layout, frames, bubbles and text;
Claude's SVG fills each art region. Model SVG is never executed: the composite is sanitized and
rasterized by resvg, then text is fitted and drawn with Pillow."""

from __future__ import annotations

import io
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from lxml import etree
from PIL import Image, ImageDraw

from proseferno.images.base import ImageProviderError
from proseferno.images.memes import charts
from proseferno.images.memes.formats import ArtRegion, Box, MemeFormat
from proseferno.images.memes.specs import MemeDatum, MemeText
from proseferno.images.memes.text import STYLES, Fitted, draw_fitted, fit_text
from proseferno.images.render import SVG_NS, svg_to_png

XLINK_NS = "http://www.w3.org/1999/xlink"
INK = "#14101f"
BUBBLE_PAD = 24
BUBBLE_TAIL = 46


@dataclass
class Placed:
    """Text the template adds (headers, axis labels, legends), fitted like any slot."""

    box: Box
    text: str
    style: str
    align: str = "center"
    valign: str = "center"
    fill: str | None = None


@dataclass
class Scene:
    under: list[str] = field(default_factory=list)
    over: list[str] = field(default_factory=list)
    texts: list[Placed] = field(default_factory=list)
    boxes: dict[str, Box] = field(default_factory=dict)


# -- SVG fragments from Claude ----------------------------------------------------

_PROLOG_RE = re.compile(r"<\?xml[^>]*\?>|<!DOCTYPE[^>]*>", re.IGNORECASE)
_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False, remove_comments=True)


def _parse(fragment: str, what: str) -> tuple[list[etree._Element], str | None]:
    """Parse model SVG that may or may not have its own <svg> wrapper; returns its elements and viewBox."""
    body = _PROLOG_RE.sub("", fragment or "").strip()
    try:
        root = etree.fromstring(f'<svg xmlns="{SVG_NS}" xmlns:xlink="{XLINK_NS}">{body}</svg>'.encode(), _PARSER)
    except etree.XMLSyntaxError as exc:
        raise ImageProviderError(f"The SVG for {what} is not valid XML: {exc}") from exc
    children = [c for c in root if isinstance(c.tag, str)]
    if len(children) == 1 and etree.QName(children[0]).localname == "svg":
        inner = children[0]
        return [c for c in inner if isinstance(c.tag, str)], inner.get("viewBox")
    return children, None


def _ids(elements: list[etree._Element]) -> set[str]:
    return {el.get("id") for root in elements for el in root.iter() if isinstance(el.tag, str) and el.get("id")}


def _prefix_ids(elements: list[etree._Element], prefix: str) -> None:
    """Make ids unique per region, so two regions' gradients named 'g1' don't collide."""
    ids = _ids(elements)
    if not ids:
        return
    pattern = re.compile(r"#(" + "|".join(re.escape(i) for i in sorted(ids, key=len, reverse=True)) + r")(?![\w-])")
    for root in elements:
        for el in root.iter():
            if not isinstance(el.tag, str):
                continue
            if el.get("id") in ids:
                el.set("id", f"{prefix}-{el.get('id')}")
            for attr, value in el.attrib.items():
                if "#" in value:
                    el.set(attr, pattern.sub(lambda m: f"#{prefix}-{m.group(1)}", value))
            if etree.QName(el).localname == "style" and el.text:
                el.text = pattern.sub(lambda m: f"#{prefix}-{m.group(1)}", el.text)


def _serialize(elements: list[etree._Element]) -> str:
    return "".join(etree.tostring(el, encoding="unicode") for el in elements)


def region_svg(region: ArtRegion, fragment: str) -> str:
    elements, view_box = _parse(fragment, f"the '{region.name}' art")
    _prefix_ids(elements, f"r-{region.name}")
    x, y, w, h = region.box
    fit = "xMidYMid slice" if region.opaque else "xMidYMid meet"
    return (
        f'<svg x="{x}" y="{y}" width="{w}" height="{h}" viewBox="{view_box or f"0 0 {w} {h}"}" '
        f'preserveAspectRatio="{fit}" overflow="hidden">{_serialize(elements)}</svg>'
    )


def cast_svg(cast_defs: str) -> str:
    if not cast_defs.strip():
        return ""
    elements, _ = _parse(cast_defs, "the cast")
    # Unwrap a <defs> the model may have added itself.
    flat: list[etree._Element] = []
    for el in elements:
        if etree.QName(el).localname == "defs":
            flat.extend(c for c in el if isinstance(c.tag, str))
        else:
            flat.append(el)
    return f"<defs>{_serialize(flat)}</defs>"


# -- Bubbles -------------------------------------------------------------------------


def bubble_svg(x: float, y: float, w: float, h: float, speaker: str) -> str:
    side = speaker.strip().lower()
    if side == "left":
        b1, b2, tip = x + w * 0.22, x + w * 0.38, (x + w * 0.14, y + h + BUBBLE_TAIL)
    elif side == "right":
        b1, b2, tip = x + w * 0.62, x + w * 0.78, (x + w * 0.86, y + h + BUBBLE_TAIL)
    else:
        b1, b2, tip = x + w * 0.42, x + w * 0.58, (x + w * 0.5, y + h + BUBBLE_TAIL)
    base = y + h
    tail = f"{b1:.1f},{base - 2:.1f} {tip[0]:.1f},{tip[1]:.1f} {b2:.1f},{base - 2:.1f}"
    seam = f"{b1 + 5:.1f},{base - 9:.1f} {tip[0]:.1f},{tip[1] - 9:.1f} {b2 - 5:.1f},{base - 9:.1f}"
    return (
        f'<rect x="{x + 6:.1f}" y="{y + 8:.1f}" width="{w:.1f}" height="{h:.1f}" rx="30" fill="#000" opacity="0.22"/>'
        f'<g stroke="{INK}" stroke-width="5" stroke-linejoin="round" fill="#ffffff">'
        f'<polygon points="{tail}"/><rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="30"/></g>'
        f'<polygon points="{seam}" fill="#ffffff"/>'
    )


# -- Scenes: what the template draws for each format ---------------------------------


def _frame(boxes: list[Box], color: str = INK, width: int = 6) -> str:
    return "".join(
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" stroke="{color}" stroke-width="{width}"/>' for x, y, w, h in boxes
    )


def _nope_yep(fmt: MemeFormat, texts: dict[str, str], data: list[MemeDatum], colors: list[str]) -> Scene:
    return Scene(
        under=['<rect x="540" y="0" width="540" height="1080" fill="#ffffff"/>'],
        over=[
            f'<line x1="540" y1="0" x2="540" y2="1080" stroke="{INK}" stroke-width="5"/>'
            f'<line x1="0" y1="540" x2="1080" y2="540" stroke="{INK}" stroke-width="5"/>'
        ],
    )


def _expanding_brain(fmt: MemeFormat, texts: dict[str, str], data: list[MemeDatum], colors: list[str]) -> Scene:
    lines = "".join(f'<line x1="0" y1="{i * 330}" x2="1080" y2="{i * 330}" stroke="{INK}" stroke-width="5"/>' for i in (1, 2, 3))
    return Scene(over=[lines + f'<line x1="540" y1="0" x2="540" y2="1320" stroke="{INK}" stroke-width="5"/>'])


def _button(cx: float, cy: float) -> str:
    return (
        f'<ellipse cx="{cx}" cy="{cy + 52}" rx="206" ry="126" fill="#2f2a3a" opacity="0.55"/>'
        f'<rect x="{cx - 190}" y="{cy}" width="380" height="44" fill="#8c1616"/>'
        f'<ellipse cx="{cx}" cy="{cy + 44}" rx="190" ry="115" fill="#8c1616"/>'
        f'<ellipse cx="{cx}" cy="{cy}" rx="190" ry="115" fill="url(#btn-top)" stroke="#6b0f0f" stroke-width="3"/>'
        f'<ellipse cx="{cx - 40}" cy="{cy - 52}" rx="110" ry="34" fill="#ffffff" opacity="0.2"/>'
    )


def _two_buttons(fmt: MemeFormat, texts: dict[str, str], data: list[MemeDatum], colors: list[str]) -> Scene:
    defs = (
        '<defs><radialGradient id="btn-top" cx="0.4" cy="0.35" r="0.75"><stop offset="0" stop-color="#ff6b5e"/>'
        '<stop offset="1" stop-color="#c81d1d"/></radialGradient></defs>'
    )
    return Scene(
        over=[defs + _button(300, 305) + _button(780, 275) + f'<line x1="0" y1="700" x2="1080" y2="700" stroke="{INK}" stroke-width="6"/>']
    )


def _midwit(fmt: MemeFormat, texts: dict[str, str], data: list[MemeDatum], colors: list[str]) -> Scene:
    scene = Scene(
        under=[
            '<defs><linearGradient id="mw-bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fffdf5"/>'
            '<stop offset="1" stop-color="#fdeccf"/></linearGradient></defs><rect width="1400" height="900" fill="url(#mw-bg)"/>'
            + charts.bell_curve_svg()
        ]
    )
    for k, iq in enumerate((55, 70, 85, 100, 115, 130, 145)):
        scene.texts.append(Placed((700 + (k - 3) * 150 - 45, 792, 90, 36), str(iq), "ui_bold", fill="#1b0c41"))
    for k, pct in enumerate(("14%", "34%", "34%", "14%")):
        scene.texts.append(Placed((700 + (k - 2) * 150 + 25, 742, 100, 30), pct, "ui", fill="#4a0c6b"))
    scene.texts.append(Placed((560, 840, 280, 44), "IQ", "ui_bold", fill="#1b0c41"))
    return scene


def _gru(fmt: MemeFormat, texts: dict[str, str], data: list[MemeDatum], colors: list[str]) -> Scene:
    parts = []
    for r in fmt.regions:
        x, y, _w, h = r.box
        pw = 1200 // 2 - 18
        parts.append(
            f'<rect x="{x}" y="{y}" width="{pw}" height="{h}" fill="#f4e6d2"/>'
            f'<rect x="{x}" y="{y + h * 0.78:.0f}" width="{pw}" height="{h * 0.22:.0f}" fill="#c58f5e"/>'
            f'<line x1="{x + 330}" y1="{y + 360}" x2="{x + 300}" y2="{y + h - 10}" stroke="#6b4a2b" stroke-width="8"/>'
            f'<line x1="{x + 540}" y1="{y + 360}" x2="{x + 570}" y2="{y + h - 10}" stroke="#6b4a2b" stroke-width="8"/>'
            f'<line x1="{x + 435}" y1="{y + 360}" x2="{x + 435}" y2="{y + h - 20}" stroke="#6b4a2b" stroke-width="8"/>'
            f'<rect x="{x + 304}" y="{y + 46}" width="262" height="318" rx="6" fill="#ffffff" stroke="#3a3346" stroke-width="5"/>'
            f'<rect x="{x + 294}" y="{y + 360}" width="282" height="14" rx="4" fill="#8a6a48"/>'
        )
    frames = [(r.box[0], r.box[1], 1200 // 2 - 18, r.box[3]) for r in fmt.regions]
    return Scene(under=parts, over=[_frame(frames)])


def _joke_pie(fmt: MemeFormat, texts: dict[str, str], data: list[MemeDatum], colors: list[str]) -> Scene:
    slices = charts.pie_slices(data)
    scene = Scene(
        under=[
            '<rect x="20" y="150" width="1160" height="660" rx="12" fill="#ffffff" stroke="#d9cfe6" stroke-width="3"/>'
            + charts.pie_svg(slices, colors)
        ]
    )
    for (_, pct), (px, py) in zip(slices, charts.pie_label_points(slices), strict=True):
        if pct >= 5:
            scene.texts.append(Placed((round(px) - 70, round(py) - 28, 140, 56), f"{pct:.0f}%", "outline"))
    top = 480 - len(slices) * 80 // 2
    for i, (label, _) in enumerate(slices):
        y = top + i * 80
        color = colors[i % len(colors)]
        scene.under.append(f'<rect x="830" y="{y + 14}" width="40" height="40" rx="8" fill="{color}" stroke="{INK}" stroke-width="2"/>')
        scene.texts.append(Placed((886, y, 280, 68), label, "ui_bold", align="left"))
    return scene


def _venn(fmt: MemeFormat, texts: dict[str, str], data: list[MemeDatum], colors: list[str]) -> Scene:
    three = bool(texts.get("c", "").strip())
    if three:
        circles = [(470, 450, colors[0]), (730, 450, colors[1]), (600, 660, colors[2])]
        radius, boxes = 270, {}
    else:
        circles = [(450, 560, colors[0]), (750, 560, colors[1])]
        radius = 310
        boxes = {"a": (170, 470, 280, 160), "b": (750, 470, 280, 160), "center": (520, 490, 160, 140)}
    svg = "".join(
        f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="{color}" fill-opacity="0.55" stroke="{INK}" stroke-width="4"/>'
        for cx, cy, color in circles
    )
    return Scene(under=[svg], boxes=boxes)


def _comic(fmt: MemeFormat, texts: dict[str, str], data: list[MemeDatum], colors: list[str]) -> Scene:
    return Scene(over=[_frame([r.box for r in fmt.regions])])


def _chat(fmt: MemeFormat, texts: dict[str, str], data: list[MemeDatum], colors: list[str]) -> Scene:
    avatar = ["#ed6925", "#781c6d", "#cf4446", "#4a0c6b"]
    scene = Scene(under=['<rect width="1080" height="1080" fill="#ffffff"/><rect width="1080" height="120" fill="#1b0c41"/>'])
    scene.texts.append(Placed((40, 30, 48, 60), "#", "light", fill="#fb9b06"))
    for i in range(4):
        y = 150 + i * 225
        if i == 3:
            scene.under.append(f'<rect x="0" y="{y - 20}" width="1080" height="225" fill="#fff4d6"/>')
        if i:
            scene.under.append(f'<line x1="40" y1="{y - 20}" x2="1040" y2="{y - 20}" stroke="#ece6f2" stroke-width="2"/>')
        scene.under.append(f'<rect x="40" y="{y}" width="84" height="84" rx="18" fill="{avatar[i]}"/>')
        name = texts.get(f"m{i + 1}_name", "").strip()
        initials = "".join(part[0] for part in name.split()[:2]).upper() or "?"
        scene.texts.append(Placed((52, y + 18, 60, 48), initials, "light"))
        scene.texts.append(Placed((700, y + 4, 200, 40), f"9:{41 + i * 3:02d} AM", "ui", align="left", fill="#8a8494"))
    return scene


def _terminal(fmt: MemeFormat, texts: dict[str, str], data: list[MemeDatum], colors: list[str]) -> Scene:
    scene = Scene(
        under=[
            '<rect x="20" y="10" width="1160" height="780" rx="18" fill="#1a1030" stroke="#3a2a5a" stroke-width="3"/>'
            '<path d="M20,28 a18,18 0 0 1 18,-18 h1124 a18,18 0 0 1 18,18 v38 h-1160 z" fill="#2a1b47"/>'
            '<circle cx="60" cy="38" r="11" fill="#ff5f57"/><circle cx="94" cy="38" r="11" fill="#febc2e"/>'
            '<circle cx="128" cy="38" r="11" fill="#28c840"/>'
        ]
    )
    for slot in ("cmd1", "cmd2", "cmd3"):
        spec = fmt.slot(slot)
        if spec and texts.get(slot, "").strip():
            _x, y, _w, h = spec.box
            scene.texts.append(Placed((60, y, 36, h), "$", "mono", fill="#ed6925"))
    return scene


def _nutrition(fmt: MemeFormat, texts: dict[str, str], data: list[MemeDatum], colors: list[str]) -> Scene:
    rules = [
        '<rect x="40" y="40" width="820" height="1120" fill="#ffffff" stroke="#000" stroke-width="5"/>',
        '<rect x="66" y="158" width="768" height="3" fill="#000"/>',
        '<rect x="66" y="292" width="768" height="20" fill="#000"/>',
        '<rect x="66" y="424" width="768" height="9" fill="#000"/>',
        '<rect x="66" y="476" width="768" height="2" fill="#000"/>',
        '<rect x="66" y="950" width="768" height="12" fill="#000"/>',
    ]
    rules += [f'<rect x="66" y="{480 + (i + 1) * 78 - 7}" width="768" height="2" fill="#000"/>' for i in range(5)]
    return Scene(
        under=["".join(rules)],
        texts=[
            Placed((66, 52, 768, 104), "Nutrition Facts", "title", align="left", fill="#000000"),
            Placed((66, 316, 480, 100), "Calories", "title", align="left", fill="#000000"),
            Placed((430, 438, 404, 32), "% Daily Value*", "ui_bold", align="right", fill="#000000"),
        ],
    )


_ALIGN = (
    ("Lawful Good", "Neutral Good", "Chaotic Good"),
    ("Lawful Neutral", "True Neutral", "Chaotic Neutral"),
    ("Lawful Evil", "Neutral Evil", "Chaotic Evil"),
)


def _alignment(fmt: MemeFormat, texts: dict[str, str], data: list[MemeDatum], colors: list[str]) -> Scene:
    scene = Scene()
    tints, bands = ("#fff3c4", "#ffe2c9", "#f8d0dc"), ("#ed6925", "#a52c60", "#4a0c6b")
    for r, row in enumerate(_ALIGN):
        for c, label in enumerate(row):
            x, y = 24 + c * 388, 130 + r * 352
            scene.under.append(
                f'<rect x="{x}" y="{y}" width="372" height="336" rx="16" fill="{tints[r]}"/>'
                f'<path d="M{x},{y + 16} a16,16 0 0 1 16,-16 h340 a16,16 0 0 1 16,16 v54 h-372 z" fill="{bands[r]}"/>'
            )
            scene.texts.append(Placed((x + 12, y + 8, 348, 56), label.upper(), "light"))
    return scene


SCENES: dict[str, Callable[[MemeFormat, dict[str, str], list[MemeDatum], list[str]], Scene]] = {
    "nope_yep": _nope_yep,
    "expanding_brain": _expanding_brain,
    "two_buttons": _two_buttons,
    "midwit_bell_curve": _midwit,
    "gru_plan": _gru,
    "joke_pie_3d": _joke_pie,
    "venn": _venn,
    "comic_strip_3": _comic,
    "comic_grid_4": _comic,
    "chat_thread": _chat,
    "terminal": _terminal,
    "nutrition_label": _nutrition,
    "alignment_chart": _alignment,
}


# -- Composition ---------------------------------------------------------------------


def compose(
    fmt: MemeFormat,
    texts: dict[str, MemeText],
    art: dict[str, str],
    cast_defs: str = "",
    data: list[MemeDatum] | None = None,
    *,
    palette: tuple[str, ...] = (),
) -> tuple[bytes, int, int]:
    """Render one meme to PNG; raises ImageProviderError when the build cannot be drawn.

    A brand ``palette`` (3+ hex colors) recolors the template's chart marks; otherwise they use inferno."""
    data = data or []
    colors = list(palette) if len(palette) >= 3 else charts.PIE_COLORS
    words = {name: t.text.strip() for name, t in texts.items()}
    if fmt.id == "spurious_correlation":
        return charts.spurious_png(words, data)

    width, height = fmt.size
    scene = SCENES.get(fmt.id, lambda *_: Scene())(fmt, words, data, colors)
    measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    drawn: list[tuple[Fitted, Box, str, str, str, str | None]] = []
    bubbles: list[str] = []

    def text_area(box: Box, bubble: bool) -> tuple[int, int]:
        return (box[2] - 2 * BUBBLE_PAD, box[3] - 2 * BUBBLE_PAD - BUBBLE_TAIL) if bubble else (box[2], box[3])

    # Parallel slots (rows, cells, panels) share the largest size that fits all of them.
    cap: dict[str, int] = {}
    for group in fmt.groups:
        sizes = []
        for name in group:
            spec = fmt.slot(name)
            if spec and words.get(name):
                w, h = text_area(scene.boxes.get(name, spec.box), spec.bubble)
                sizes.append(fit_text(measure, words[name], w, h, STYLES[spec.style]).size)
        if sizes:
            cap.update(dict.fromkeys(group, min(sizes)))

    for slot in fmt.slots:
        text = words.get(slot.name, "")
        if not text:
            continue
        box = scene.boxes.get(slot.name, slot.box)
        style = STYLES[slot.style]
        w, h = text_area(box, slot.bubble)
        if slot.bubble:
            fitted = fit_text(measure, text, w, h, style, max_size=cap.get(slot.name))
            bw = max(fitted.width + 2 * BUBBLE_PAD, 170)
            bh = fitted.height + 2 * BUBBLE_PAD
            bx = box[0] + (box[2] - bw) // 2
            bubbles.append(bubble_svg(bx, box[1], bw, bh, texts[slot.name].speaker))
            drawn.append(
                (
                    fitted,
                    (bx + BUBBLE_PAD, box[1] + BUBBLE_PAD, bw - 2 * BUBBLE_PAD, bh - 2 * BUBBLE_PAD),
                    slot.style,
                    "center",
                    "center",
                    slot.fill,
                )
            )
        else:
            fitted = fit_text(measure, text, w, h, style, max_size=cap.get(slot.name))
            drawn.append((fitted, box, slot.style, slot.align, slot.valign, slot.fill))
    for placed in scene.texts:
        fitted = fit_text(measure, placed.text, placed.box[2], placed.box[3], STYLES[placed.style], min_size=10)
        drawn.append((fitted, placed.box, placed.style, placed.align, placed.valign, placed.fill))

    regions = "".join(region_svg(region, art[region.name]) for region in fmt.regions if art.get(region.name, "").strip())
    svg = (
        f'<svg xmlns="{SVG_NS}" xmlns:xlink="{XLINK_NS}" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'<rect width="{width}" height="{height}" fill="{fmt.background}"/>{cast_svg(cast_defs)}'
        f"{''.join(scene.under)}{regions}{''.join(scene.over)}{''.join(bubbles)}</svg>"
    )
    png, _, _ = svg_to_png(svg, width=width, background=fmt.background)

    with Image.open(io.BytesIO(png)) as source:
        img = source.convert("RGB")
    draw = ImageDraw.Draw(img)
    for fitted, box, style_name, align, valign, fill in drawn:
        draw_fitted(draw, fitted, box, STYLES[style_name], align=align, valign=valign, fill=fill)
    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue(), img.width, img.height


MASCOT_SCENE = """
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#4a0c6b"/><stop offset="1" stop-color="#cf4446"/></linearGradient>
  <radialGradient id="glow" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="#fcffa4"/><stop offset="1" stop-color="#fb9b06" stop-opacity="0"/></radialGradient>
  <linearGradient id="body" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#781c6d"/><stop offset="1" stop-color="#4a0c6b"/></linearGradient>
</defs>
<rect width="1080" height="1080" fill="url(#bg)"/>
<circle cx="540" cy="560" r="330" fill="#ed6925" opacity="0.18"/>
<ellipse cx="540" cy="820" rx="250" ry="36" fill="#000004" opacity="0.3"/>
<rect x="400" y="560" width="280" height="250" rx="60" fill="url(#body)"/>
<rect x="455" y="610" width="170" height="90" rx="22" fill="#ed6925"/>
<path d="M400,640 C330,600 300,540 320,500" stroke="#4a0c6b" stroke-width="44" fill="none" stroke-linecap="round"/>
<path d="M680,640 C750,600 780,540 760,500" stroke="#4a0c6b" stroke-width="44" fill="none" stroke-linecap="round"/>
<circle cx="320" cy="490" r="34" fill="#f7d13d"/><circle cx="760" cy="490" r="34" fill="#f7d13d"/>
<rect x="370" y="300" width="340" height="270" rx="70" fill="url(#body)"/>
<rect x="405" y="335" width="270" height="190" rx="48" fill="#1b0c41"/>
<ellipse cx="490" cy="420" rx="30" ry="40" fill="#fcffa4"/><ellipse cx="590" cy="420" rx="30" ry="40" fill="#fcffa4"/>
<path d="M500,480 Q540,465 580,480" stroke="#fcffa4" stroke-width="10" fill="none" stroke-linecap="round"/>
<line x1="540" y1="300" x2="540" y2="240" stroke="#4a0c6b" stroke-width="12"/>
<circle cx="540" cy="226" r="40" fill="url(#glow)"/><circle cx="540" cy="226" r="18" fill="#fb9b06"/>
"""
