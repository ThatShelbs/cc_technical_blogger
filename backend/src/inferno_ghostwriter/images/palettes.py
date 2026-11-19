"""The colors of the opening image and the closing meme: inferno, magma or viridis on white, gray or near-black.

This is the only place those colors are defined. A ``Scheme`` is one ramp on one surface; the meme looks, the
opener templates, the character kit and the prompts all read their colors from it, and ``snap_svg`` moves every
color in model-drawn SVG to the nearest scheme color, so the palette is guaranteed, not just asked for.

A brand kit palette (the author's explicit choice) still wins: ``scheme_for`` builds a ramp from it.
"""

from __future__ import annotations

import random
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import cached_property

from lxml import etree

# Ten stops each, dark to light (matplotlib's perceptually uniform maps).
RAMPS: dict[str, tuple[str, ...]] = {
    "inferno": ("#000004", "#1b0c41", "#4a0c6b", "#781c6d", "#a52c60", "#cf4446", "#ed6925", "#fb9b06", "#f7d13d", "#fcffa4"),
    "magma": ("#000004", "#180f3e", "#451077", "#721f81", "#9f2f7f", "#cd4071", "#f1605d", "#fd9567", "#fec98d", "#fcfdbf"),
    "viridis": ("#440154", "#482878", "#3e4989", "#31688e", "#26828e", "#1f9e89", "#35b779", "#6ece58", "#b5de2b", "#fde725"),
}
RAMP_LABELS = {"inferno": "Inferno", "magma": "Magma", "viridis": "Viridis"}

# Backgrounds: white and grays, or dark blacks.
SURFACES: dict[str, str] = {
    "white": "#ffffff",
    "paper": "#f6f6f7",
    "light_gray": "#e7e7ea",
    "slate": "#2a2a31",
    "charcoal": "#1e1e22",
    "near_black": "#0b0b0f",
    "ink_black": "#000004",
}
LIGHT_SURFACES = ("white", "paper", "light_gray")
DARK_SURFACES = ("slate", "charcoal", "near_black", "ink_black")

INK_DARK = "#14101f"
INK_LIGHT = "#ffffff"
# Natural colors the character kit may use in any scheme (skin tones, a red button, a white eye), never snapped.
NATURALS = ("#ffffff", "#000000", INK_DARK)

DEFAULT = ("inferno", "near_black")


# -- color maths ------------------------------------------------------------------------------------------------------


def rgb(color: str) -> tuple[int, int, int]:
    value = color.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    try:
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
    except (ValueError, IndexError):
        return 0, 0, 0


def to_hex(color: Sequence[float]) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c))):02x}" for c in color)


def mix(a: str, b: str, t: float) -> str:
    """``a`` moved ``t`` of the way to ``b``."""
    ra, rb = rgb(a), rgb(b)
    return to_hex([x + (y - x) * t for x, y in zip(ra, rb, strict=True)])


def luminance(color: str) -> float:
    def channel(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _lab(color: str) -> tuple[float, float, float]:
    def lin(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(c) for c in rgb(color))
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def distance(a: str, b: str) -> float:
    la, lb = _lab(a), _lab(b)
    return sum((p - q) ** 2 for p, q in zip(la, lb, strict=True)) ** 0.5


# -- schemes ----------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Scheme:
    """One ramp on one surface: everything the opener and the meme are colored with."""

    ramp_id: str
    surface_id: str
    ramp: tuple[str, ...]
    bg: str

    @property
    def id(self) -> str:
        return f"{self.ramp_id}:{self.surface_id}"

    @property
    def label(self) -> str:
        return f"{RAMP_LABELS.get(self.ramp_id, 'Brand')} on {self.surface_id.replace('_', ' ')}"

    @property
    def dark(self) -> bool:
        return luminance(self.bg) < 0.2

    @property
    def bg2(self) -> str:
        """The far end of the background's gentle gradient."""
        return mix(self.bg, "#000000", 0.55) if self.dark else mix(self.bg, self.ramp[1], 0.06)

    @property
    def ink(self) -> str:
        return INK_LIGHT if self.dark else INK_DARK

    @property
    def muted(self) -> str:
        return mix(self.ink, self.bg, 0.3)

    @property
    def panel(self) -> str:
        return mix(self.bg, "#ffffff", 0.07) if self.dark else mix(self.bg, self.ramp[2], 0.06)

    @property
    def line(self) -> str:
        return mix(self.bg, self.ink, 0.22)

    @cached_property
    def accents(self) -> tuple[str, ...]:
        """Ramp colors that read on the background, most vivid first (the warm/bright end on dark, the deep end on light)."""
        usable = [c for c in self.ramp if contrast(c, self.bg) >= 2.0]
        if not usable:
            usable = list(self.ramp)
        if self.dark:
            # Bright end first, skipping the palest stop (it reads as white).
            ordered = sorted(usable, key=luminance, reverse=True)
            ordered = ordered[1:] + ordered[:1] if len(ordered) > 3 else ordered
        else:
            ordered = sorted(usable, key=lambda c: abs(luminance(c) - 0.12))
        # Spread out: alternate picks so neighbors differ.
        spread = ordered[::2] + ordered[1::2]
        return tuple(spread[:6]) if len(spread) >= 6 else tuple((spread * 6)[:6])

    def accent(self, i: int) -> str:
        return self.accents[i % len(self.accents)]

    @property
    def deep(self) -> str:
        """A deep ramp color for dark shapes on light surfaces and frames."""
        return self.ramp[1]

    @property
    def glow(self) -> str:
        """The ramp's bright end, for glows and highlights."""
        return self.ramp[-2]

    def at(self, t: float) -> str:
        """The ramp sampled at ``t`` (0 = dark end, 1 = light end), interpolated."""
        t = max(0.0, min(1.0, t))
        pos = t * (len(self.ramp) - 1)
        i = min(int(pos), len(self.ramp) - 2)
        return mix(self.ramp[i], self.ramp[i + 1], pos - i)

    @cached_property
    def allowed(self) -> tuple[str, ...]:
        """Every color a snapped drawing may use: the ramp, its tints and shades, the surfaces and the inks."""
        tints = [mix(c, "#ffffff", t) for c in self.ramp for t in (0.35, 0.7)]
        shades = [mix(c, "#000000", 0.4) for c in self.ramp]
        grays = [mix("#ffffff", "#000000", t) for t in (0.1, 0.25, 0.45, 0.65, 0.82)]
        return tuple(dict.fromkeys([*self.ramp, *tints, *shades, *SURFACES.values(), *grays, INK_DARK, INK_LIGHT, self.bg]))

    def describe(self) -> str:
        """The scheme as a drawing prompt reads it."""
        tone = "dark" if self.dark else "light"
        return (
            f"Colors: the {RAMP_LABELS.get(self.ramp_id, 'brand')} palette on a {tone} {self.surface_id.replace('_', ' ')} "
            f"background ({self.bg}). Palette, dark to light: {' '.join(self.ramp)}. Use only these colors, their tints "
            f"toward white, white, grays and near-black; any other color is moved to the nearest palette color."
        )


def scheme(ramp_id: str = DEFAULT[0], surface_id: str = DEFAULT[1]) -> Scheme:
    ramp = RAMPS.get(ramp_id) or RAMPS[DEFAULT[0]]
    surface = SURFACES.get(surface_id) or SURFACES[DEFAULT[1]]
    return Scheme(ramp_id if ramp_id in RAMPS else DEFAULT[0], surface_id if surface_id in SURFACES else DEFAULT[1], ramp, surface)


def from_id(scheme_id: str | None) -> Scheme | None:
    """A stored ``ramp:surface`` id back to its scheme (None for anything unknown)."""
    if not scheme_id or ":" not in scheme_id:
        return None
    ramp_id, surface_id = scheme_id.split(":", 1)
    if ramp_id not in RAMPS or surface_id not in SURFACES:
        return None
    return scheme(ramp_id, surface_id)


def brand_scheme(palette: Sequence[str], surface_id: str | None = None) -> Scheme:
    """A scheme from a brand kit palette (3+ hex colors): the palette sorted dark to light is the ramp; the surface is
    its darkest color when that is dark enough, else white."""
    colors = sorted({c.lower() for c in palette if re.fullmatch(r"#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?", c.strip())}, key=luminance)
    if len(colors) < 3:
        return scheme()
    if surface_id in SURFACES:
        bg = SURFACES[str(surface_id)]
    else:
        bg = colors[0] if luminance(colors[0]) < 0.08 else SURFACES["white"]
        surface_id = "brand_dark" if luminance(colors[0]) < 0.08 else "white"
    return Scheme("brand", str(surface_id), tuple(colors), bg)


def choose(
    recent: Iterable[str] = (),
    *,
    ramp: str | None = None,
    surface: str | None = None,
    dark: bool | None = None,
    rng: random.Random | None = None,
    avoid: Iterable[str] = (),
) -> Scheme:
    """A scheme for a new image: a pinned ramp/surface wins; otherwise the one used least recently, so a persona's
    images rotate through inferno, magma and viridis and between light and dark backgrounds."""
    rng = rng or random.Random()
    recent_ids = [r for r in recent if r]
    avoided = set(avoid)
    ramps = [ramp] if ramp in RAMPS else list(RAMPS)
    if surface in SURFACES:
        surfaces = [str(surface)]
    elif dark is True:
        surfaces = list(DARK_SURFACES)
    elif dark is False:
        surfaces = list(LIGHT_SURFACES)
    else:
        surfaces = list(SURFACES)
    recent_ramps = [r.split(":", 1)[0] for r in recent_ids]
    recent_tone = ["dark" if r.split(":", 1)[-1] in DARK_SURFACES else "light" for r in recent_ids]

    def staleness(ramp_id: str, surface_id: str) -> tuple[int, int, float]:
        ramp_age = recent_ramps.index(ramp_id) if ramp_id in recent_ramps else len(recent_ids) + 1
        tone = "dark" if surface_id in DARK_SURFACES else "light"
        tone_age = recent_tone.index(tone) if tone in recent_tone else len(recent_ids) + 1
        return ramp_age, tone_age, rng.random()

    options = [(r, s) for r in ramps for s in surfaces if f"{r}:{s}" not in avoided] or [(r, s) for r in ramps for s in surfaces]
    best = max(options, key=lambda o: staleness(*o))
    return scheme(*best)


def house_ramp(palette: Sequence[str]) -> str | None:
    """The house ramp a palette is (a remix's inferno, magma or viridis tweak), else None (a real brand palette)."""
    colors = tuple(c.lower() for c in palette)
    return next((rid for rid, ramp in RAMPS.items() if colors == ramp), None)


def pick(
    palette: Sequence[str], recent: Iterable[str] = (), *, dark: bool | None = None, ramp: str | None = None, avoid: Iterable[str] = ()
) -> Scheme:
    """A new image's scheme: a brand palette builds its own; a house ramp (a remix pin) keeps the surface rotation;
    otherwise the least recently used ramp and tone."""
    house = house_ramp(palette)
    if len(palette) >= 3 and house is None:
        return brand_scheme(palette)
    return choose(recent, ramp=house or ramp, dark=dark, avoid=avoid)


def scheme_for(palette: Sequence[str] = (), scheme_id: str | None = None) -> Scheme:
    """The scheme an image is drawn in: a brand palette (3+ colors) first, then a stored scheme id, then the default."""
    if len([c for c in palette if c]) >= 3 and house_ramp(palette) is None:
        return brand_scheme(palette)
    return from_id(scheme_id) or scheme()


# -- snapping model-drawn SVG -------------------------------------------------------------------------------------------

_COLOR_ATTRS = ("fill", "stroke", "stop-color", "flood-color", "lighting-color", "color")
_HEX = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
_RGB = re.compile(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(?:,\s*[\d.]+\s*)?\)")
_NAMED = {
    "red": "#ff0000",
    "green": "#008000",
    "blue": "#0000ff",
    "yellow": "#ffff00",
    "orange": "#ffa500",
    "purple": "#800080",
    "pink": "#ffc0cb",
    "cyan": "#00ffff",
    "magenta": "#ff00ff",
    "lime": "#00ff00",
    "navy": "#000080",
    "teal": "#008080",
    "brown": "#a52a2a",
    "gold": "#ffd700",
    "gray": "#808080",
    "grey": "#808080",
    "silver": "#c0c0c0",
    "black": "#000000",
    "white": "#ffffff",
    "skyblue": "#87ceeb",
    "tomato": "#ff6347",
    "coral": "#ff7f50",
    "crimson": "#dc143c",
    "violet": "#ee82ee",
    "indigo": "#4b0082",
    "salmon": "#fa8072",
}


class Snapper:
    """Moves colors to the nearest allowed one (memoized), and records what it moved."""

    def __init__(self, allowed: Sequence[str]) -> None:
        self.allowed = tuple(allowed)
        self._cache: dict[str, str] = {}
        self.moved: dict[str, str] = {}

    def color(self, value: str) -> str:
        key = value.lower()
        if key in self._cache:
            return self._cache[key]
        key6 = "#" + "".join(c * 2 for c in key[1:]) if len(key) == 4 else key
        best = min(self.allowed, key=lambda c: distance(c, key6))
        self._cache[key] = best
        if best.lower() != key6:
            self.moved[key6] = best
        return best

    def text(self, value: str) -> str:
        value = _HEX.sub(lambda m: self.color(m.group(0)), value)
        value = _RGB.sub(lambda m: self.color(to_hex([int(m.group(i)) for i in (1, 2, 3)])), value)
        stripped = value.strip().lower()
        if stripped in _NAMED:
            return self.color(_NAMED[stripped])
        return value


def snap_tree(root: etree._Element, allowed: Sequence[str]) -> dict[str, str]:
    """Snap every color in an SVG tree in place; returns {original: replacement} for the colors that moved."""
    snapper = Snapper(allowed)
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        for attr in _COLOR_ATTRS:
            value = el.get(attr)
            if value and value.strip().lower() not in ("none", "transparent", "currentcolor", "inherit") and not value.startswith("url("):
                el.set(attr, snapper.text(value))
        style = el.get("style")
        if style:
            el.set("style", snapper.text(style))
        if etree.QName(el).localname == "style" and el.text:
            el.text = _snap_css(el.text, snapper)
    return snapper.moved


def snap_svg(svg: str, allowed: Sequence[str]) -> str:
    """Snap every color in an SVG document or fragment string (a text pass: safe on fragments without a root)."""
    snapper = Snapper(allowed)

    def attr(m: re.Match[str]) -> str:
        name, quote, value = m.group(1), m.group(2), m.group(3)
        if value.strip().lower() in ("none", "transparent", "currentcolor", "inherit") or value.startswith("url("):
            return m.group(0)
        return f"{name}={quote}{snapper.text(value)}{quote}"

    names = "|".join(re.escape(a) for a in (*_COLOR_ATTRS, "style"))
    svg = re.sub(rf'\b({names})=(["\'])(.*?)\2', attr, svg)
    return re.sub(
        r"(<style[^>]*>)(.*?)(</style>)", lambda m: m.group(1) + _snap_css(m.group(2), snapper) + m.group(3), svg, flags=re.DOTALL
    )


def _snap_css(css: str, snapper: Snapper) -> str:
    """Snap colors in CSS declaration values only (after a colon), so id selectors like ``#add`` are left alone."""
    return re.sub(r"(:\s*)([^;{}]+)", lambda m: m.group(1) + snapper.text(m.group(2)), css)


def colors_in(svg: str) -> set[str]:
    """Every hex color an SVG string uses (lowercased, 6 digits)."""
    out = set()
    for m in _HEX.finditer(svg):
        v = m.group(0).lower()
        out.add("#" + "".join(c * 2 for c in v[1:]) if len(v) == 4 else v)
    return out


def menu() -> str:
    """The ramps and surfaces as a prompt reads them."""
    ramps = "; ".join(f"`{r}` ({RAMP_LABELS[r]}: {' '.join(RAMPS[r][1::2])})" for r in RAMPS)
    surfaces = ", ".join(f"`{s}` {c}" for s, c in SURFACES.items())
    return f"Ramps: {ramps}. Surfaces: {surfaces}."
