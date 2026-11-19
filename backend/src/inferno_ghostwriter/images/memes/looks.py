# ruff: noqa: E501
"""The look catalog: how a meme is drawn (rendering treatment of the kit and its template), never its colors.

Colors always come from a ``Scheme`` (images/palettes.py): inferno, magma or viridis on white, gray or near-black. A
look may prefer a ramp (viridis lab) or a tone (blueprint is dark, whiteboard is light); otherwise the scheme rotates
against the author's recent memes. A look is chosen per meme (the author's pick, the room's suggestion, or a weighted
pick that avoids the author's recent looks), so memes do not all look alike. This is the only place a look is defined.
Everything is our own cast: never Sanrio, Pixar or any existing character.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

from inferno_ghostwriter.images.palettes import INK_DARK, SURFACES, Scheme, brand_scheme, contrast, house_ramp, mix, scheme

DEFAULT_LOOK = "inferno_flat"


@dataclass(frozen=True)
class Theme:
    """The colors the composer paints templates with (comic gutters, chat header, chart marks, alignment bands)."""

    dark: str  # gutters, headers, dark surfaces
    paper: str  # light chart and card backgrounds
    ink: str  # outlines, frames, bubble borders
    accents: tuple[str, ...]  # six chart and avatar colors, most vivid first
    bands: tuple[str, str, str]  # three dark colors that carry white text
    bubble_fill: str = "#ffffff"


@dataclass(frozen=True)
class Look:
    id: str
    label: str
    description: str
    art: str  # rendering direction for anything still drawn by Claude (a custom prop)
    cast: str  # how the cast is treated in this look
    suits: str  # what jokes it serves, read by the writers' room
    weight: int = 3  # relative chance in a random pick
    ramp: str = ""  # a preferred ramp ("" = rotate)
    tone: str = ""  # "dark", "light" or "" (either)

    @property
    def default_scheme(self) -> Scheme:
        return scheme(self.ramp or "inferno", "near_black" if self.tone == "dark" else "white" if self.tone == "light" else "near_black")

    @property
    def palette(self) -> tuple[str, ...]:
        return self.default_scheme.ramp

    @property
    def theme(self) -> Theme:
        return theme_for(self, self.default_scheme)


LOOKS: tuple[Look, ...] = (
    Look(
        "inferno_flat",
        "Inferno flat",
        "The brand look: bold flat vector with soft gradients and clean outlines.",
        "Modern flat-vector cartoon: bold shapes, clean 4-6px dark outlines with round joins, simple gradients, soft shadows, generous negative space.",
        "The cast in clean outlines with soft gradient shading and rosy cheeks.",
        "any joke; the safe default",
        weight=3,
    ),
    Look(
        "kawaii",
        "Kawaii",
        "Chibi cute: bigger heads, thick soft outlines, blush and sparkles.",
        "Kawaii chibi cartoon: thick soft rounded outlines in a darker tint of each fill, flat color with one soft highlight, blush circles, tiny sparkles.",
        "The cast as chibis with big heads, blush and sparkles.",
        "wholesome, relatable, gently absurd jokes; cute art against a brutal caption is gold",
        tone="light",
    ),
    Look(
        "soft_3d",
        "Soft 3D",
        "Clay-render volume: radial shading, rim light, glossy highlights, no outlines.",
        "Soft 3D clay render in SVG: radial gradients for volume, rim light on one edge, glossy highlights, soft contact shadows, no outlines.",
        "The cast as glossy vinyl-toy figures with real volume.",
        "product-demo and keynote parody, anything that benefits from deadpan seriousness",
    ),
    Look(
        "viridis_lab",
        "Viridis lab",
        "A scientific poster: uniform thin lines, flat viridis fills.",
        "Scientific-poster illustration: clean uniform line weights, flat fills, small tick marks and figure-label flourishes (never real words).",
        "The cast in flat fills with thin, uniform outlines.",
        "data-science, experiment, statistics and causal-inference jokes",
        ramp="viridis",
        tone="light",
    ),
    Look(
        "magma_noir",
        "Magma noir",
        "Film-noir drama: heavy darks and magma glows.",
        "Film-noir illustration: a hard spotlight, long diagonal shadows, heavy darks, magma glows, bold graphic shapes.",
        "The cast lit from one side with deep shadows.",
        "debugging mysteries, incident postmortems, 'who did this' jokes, dramatic understatement",
        ramp="magma",
        tone="dark",
    ),
    Look(
        "corporate_slate",
        "Corporate slate",
        "Restrained enterprise-deck illustration on light gray.",
        "Corporate-deck illustration: restrained flat vector, thin consistent outlines, tidy front-on scenes, lots of calm negative space.",
        "The cast deadpan and tidy with thin outlines.",
        "enterprise, leadership, stakeholder and process jokes where the dry look is the joke",
        tone="light",
    ),
    Look(
        "retro_comic",
        "Retro comic",
        "Pop-art halftone dots and heavy ink outlines.",
        "Vintage pop-art comic: heavy black ink outlines, halftone dot shading, high contrast.",
        "The cast in thick ink with halftone shading.",
        "big reactions, hot takes, absurd escalation and sound-effect gags",
    ),
    Look(
        "pixel_arcade",
        "Pixel arcade",
        "16-bit pixel art: the whole picture snapped to a pixel grid.",
        "16-bit pixel art: square pixels on a coarse grid, no curves, chunky game-UI frames.",
        "The cast as pixel sprites.",
        "gaming metaphors, 'game over' jokes, training runs, levels, boss fights and lives",
        tone="dark",
    ),
    Look(
        "whiteboard",
        "Whiteboard doodle",
        "Dry-erase marker sketch: wobbly lines on a white board.",
        "Whiteboard marker doodle: wobbly hand-drawn marker lines with round caps, three marker colors, no gradients.",
        "The cast as wobbly marker doodles.",
        "process and architecture gags, 'the plan' and whiteboard-meeting humor",
        tone="light",
    ),
    Look(
        "blueprint",
        "Blueprint",
        "A technical drawing: pale linework on a dark ground.",
        "Blueprint: thin pale line drawings on a dark ground, no fills, dimension arrows and callout leaders.",
        "The cast drawn as pale outlines.",
        "architecture, systems-design and over-engineering jokes",
        tone="dark",
    ),
    Look(
        "inferno_robots",
        "Inferno robots",
        "Friendly retro robots (the ghost cameos).",
        "Retro tin-toy illustration: chunky shapes, a brushed sheen, bold outlines, friendly and never menacing.",
        "The cast are friendly retro robots with screen faces; the Inferno Ghostwriter ghost makes a small cameo.",
        "AI and agent jokes where machines are the subject, retro-tech nostalgia",
        weight=1,
    ),
)

BY_ID = {look.id: look for look in LOOKS}


def get_look(look_id: str | None) -> Look:
    """The look for an id; unknown or empty ids (older memes) read as the brand look."""
    return BY_ID.get((look_id or "").strip(), BY_ID[DEFAULT_LOOK])


def is_look(look_id: str | None) -> bool:
    return (look_id or "").strip() in BY_ID


def choose_look(
    pick: str | None = None,
    suggested: str | None = None,
    recent: Sequence[str] = (),
    *,
    rng: random.Random | None = None,
    avoid: Sequence[str] = (),
    weights: dict[str, float] | None = None,
) -> Look:
    """The author's pick, else the room's suggestion unless used lately, else a weighted pick that avoids recent looks.

    ``avoid`` is used by a redraw: the look being replaced. ``weights`` multiplies each look's chance (the author's
    taste: looks they liked go up, looks they turned down go down)."""
    if pick and is_look(pick):
        return BY_ID[pick.strip()]
    banned = {*recent[:2], *avoid}
    if suggested and is_look(suggested) and suggested.strip() not in banned and (weights or {}).get(suggested.strip(), 1.0) >= 0.5:
        return BY_ID[suggested.strip()]
    pool = [look for look in LOOKS if look.id not in banned] or [look for look in LOOKS if look.id not in avoid] or list(LOOKS)
    taste = weights or {}
    return (rng or random).choices(pool, weights=[max(0.05, look.weight * taste.get(look.id, 1.0)) for look in pool])[0]


def theme_for(look: Look, sch: Scheme) -> Theme:
    """The template colors for a look in a scheme."""
    light = brand_scheme(sch.ramp, "white") if sch.ramp_id == "brand" else scheme(sch.ramp_id, "white")
    dark = sch.bg if sch.dark else mix(sch.ramp[1], "#000000", 0.15)
    paper = sch.bg if not sch.dark else SURFACES["paper"]
    bands = [c for c in reversed(sch.ramp) if contrast(c, "#ffffff") >= 4.5]
    if len(bands) >= 3:
        picked = (bands[0], bands[len(bands) // 2], bands[-1])
    else:
        deep = sorted(sch.ramp, key=lambda c: contrast(c, "#ffffff"))
        picked = (deep[-1], deep[-1], deep[-1]) if len(deep) < 3 else (deep[-3], deep[-2], deep[-1])
    return Theme(dark, paper, INK_DARK, light.accents, picked)


def themed(look: Look, palette: tuple[str, ...] = (), sch: Scheme | None = None) -> Theme:
    """The look's theme in a scheme; a brand palette (3+ colors) builds the scheme."""
    if len(palette) >= 3 and house_ramp(palette) is None:
        return theme_for(look, brand_scheme(palette))
    return theme_for(look, sch or look.default_scheme)


def menu() -> str:
    """The look menu for the ideation prompt."""
    return "\n".join(f"- `{look.id}`: **{look.label}**. {look.description} Suits: {look.suits}." for look in LOOKS)
