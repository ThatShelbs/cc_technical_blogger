"""How the kit is rendered in each meme look, and the colors each character wears in a scheme.

A look changes the treatment (outline weight, shading, cheek blush, proportions); the colors always come from the
image's ``Scheme`` (inferno, magma or viridis), plus a few natural colors (skin tones, white eyes) that no palette
should recolor.
"""

from __future__ import annotations

from dataclasses import dataclass

from inferno_ghostwriter.images.palettes import INK_DARK, Scheme, luminance, mix

SKIN_TONES = ("#f9d9c0", "#eebf98", "#d39a6e", "#a8714a", "#7a4f33", "#5b3a26")
HAIR = ("#2b1d17", "#5a3a22", "#8a5a2b", "#d9a35b", "#1b0c41", "#c9c4cf")


@dataclass(frozen=True)
class KitStyle:
    """The rendering treatment of one look."""

    id: str
    outline: float = 6.0  # outline width at scale 1 (0 = no outline)
    shading: str = "soft"  # flat | soft | volume | halftone | line | marker
    ink: str = ""  # outline color ("" = a dark shade of each fill)
    blush: bool = True
    sparkle: bool = False
    head: float = 1.0  # head scale (chibi looks enlarge it)
    pixel: int = 0  # the art layer is pixelated to this cell size after rendering (0 = off)
    wobble: bool = False  # hand-drawn marker wobble


STYLES: dict[str, KitStyle] = {
    "inferno_flat": KitStyle("inferno_flat", 6.0, "soft", INK_DARK),
    "kawaii": KitStyle("kawaii", 7.0, "soft", "", blush=True, sparkle=True, head=1.12),
    "soft_3d": KitStyle("soft_3d", 0.0, "volume"),
    "viridis_lab": KitStyle("viridis_lab", 4.5, "flat", INK_DARK),
    "magma_noir": KitStyle("magma_noir", 5.0, "volume", INK_DARK, blush=False),
    "corporate_slate": KitStyle("corporate_slate", 3.5, "flat", INK_DARK, blush=False),
    "retro_comic": KitStyle("retro_comic", 9.0, "halftone", "#111111"),
    "pixel_arcade": KitStyle("pixel_arcade", 6.0, "flat", INK_DARK, pixel=9),
    "whiteboard": KitStyle("whiteboard", 6.0, "marker", "", blush=False, wobble=True),
    "blueprint": KitStyle("blueprint", 4.0, "line", "", blush=False),
    "inferno_robots": KitStyle("inferno_robots", 6.0, "soft", INK_DARK),
}
DEFAULT_STYLE = STYLES["inferno_flat"]


def kit_style(look_id: str | None) -> KitStyle:
    return STYLES.get((look_id or "").strip(), DEFAULT_STYLE)


@dataclass(frozen=True)
class Coat:
    """The colors one character wears: its main fill (top and bottom of a soft gradient), a secondary fill (ears,
    shirt, panel), an accent (collar, hat, antenna), the eye color and the outline."""

    top: str
    bottom: str
    second: str
    accent: str
    eye: str
    line: str
    cheek: str
    light: str  # a highlight color

    @property
    def mid(self) -> str:
        return mix(self.top, self.bottom, 0.5)


def blueprint_ground(scheme: Scheme) -> str:
    """The paper a blueprint is drawn on: the scheme's own dark surface, else a deep blueprint blue. Line art is filled
    with it, so shapes stay opaque (an arm behind a body never shows through) while reading as linework."""
    return scheme.bg if scheme.dark else "#14396a"


def _line(fill: str, style: KitStyle) -> str:
    if style.ink:
        return style.ink
    return mix(fill, "#000000", 0.55)


def coat(kind: str, scheme: Scheme, style: KitStyle, variant: int = 0) -> Coat:
    """A character's colors in this scheme. ``variant`` gives a second (or third) character of the same kind a
    different coat, so two ghosts or two dogs in one scene are told apart."""
    ramp = scheme.ramp
    n = len(ramp)

    def r(i: int) -> str:
        return ramp[max(0, min(n - 1, i))]

    eye_dark = mix(r(1), "#000000", 0.35) if luminance(r(1)) > 0.02 else "#1a1024"
    cheek = mix(r(n // 2 + 1), "#ff8fa0", 0.55)
    if style.shading == "line":
        ground = blueprint_ground(scheme)
        ink = mix(ground, "#ffffff", 0.85)
        return Coat(ground, ground, mix(ground, "#ffffff", 0.1), r(n - 2), ink, ink, ground, ink)
    if style.shading == "marker":
        marker = (r(2), r(5), r(3))[variant % 3]
        return Coat("#ffffff", "#ffffff", mix("#ffffff", marker, 0.15), r(6), mix(r(1), "#000000", 0.3), marker, "#ffd0d6", "#ffffff")

    if kind == "ghost":
        palettes = [
            (mix(r(4), "#ffffff", 0.25), r(n - 2), r(6)),
            (mix(r(2), "#ffffff", 0.35), mix(r(5), "#ffffff", 0.1), r(7)),
            (mix(r(n - 1), "#ffffff", 0.3), mix(r(7), "#ffffff", 0.05), r(4)),
        ]
        top, bottom, accent = palettes[variant % len(palettes)]
        coat_ = Coat(top, bottom, mix(top, bottom, 0.4), accent, eye_dark, "", cheek, "#ffffff")
    elif kind == "dog":
        furs = [
            ("#fff1dc", "#f6d6a8", "#c8834a"),  # cream pup with caramel ears
            ("#f4c27e", "#e09a4f", "#8a4f2a"),  # golden pup
            ("#f4f1ee", "#dedad6", "#4a4450"),  # white pup with dark ears
        ]
        top, bottom, second = furs[variant % len(furs)]
        coat_ = Coat(top, bottom, second, r(5) if n > 5 else r(n - 1), "#1c1418", "", cheek, "#ffffff")
    elif kind == "cat":
        furs = [
            ("#c9c6cf", "#a9a5b2", "#6d6878"),  # gray tabby
            ("#f6b26b", "#e8893a", "#b85e1f"),  # orange tabby
            ("#3a3540", "#2a2630", "#18151c"),  # black cat
        ]
        top, bottom, second = furs[variant % len(furs)]
        coat_ = Coat(top, bottom, second, r(n - 3), "#1c1418" if variant % 3 != 2 else r(n - 2), "", cheek, "#ffffff")
    elif kind == "person":
        skin = SKIN_TONES[(variant * 2 + 1) % len(SKIN_TONES)]
        shirts = (r(5), r(3), r(7), r(2), r(6))
        shirt = shirts[variant % len(shirts)]
        hair = HAIR[variant % len(HAIR)]
        coat_ = Coat(skin, mix(skin, "#000000", 0.08), shirt, hair, "#1c1418", "", mix(skin, "#ff7f8f", 0.35), "#ffffff")
    else:  # robot
        metal = ("#d9dbe3", "#b9bcc8")
        bodies = (r(n - 3), r(5), r(3))
        coat_ = Coat(metal[0], metal[1], bodies[variant % len(bodies)], r(n - 2), mix(r(n - 1), "#ffffff", 0.2), "", r(n - 3), "#ffffff")

    line = _line(coat_.bottom if kind != "ghost" else coat_.top, style)
    if style.shading == "volume" and not style.outline:
        line = "none"
    return Coat(coat_.top, coat_.bottom, coat_.second, coat_.accent, coat_.eye, line, coat_.cheek, coat_.light)
