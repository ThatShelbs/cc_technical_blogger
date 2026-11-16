# ruff: noqa: E501
"""The look catalog: how a meme is drawn (rendering style, cast treatment, palette) and how its template is colored.

A look is chosen per meme (the author's pick, the room's suggestion, or a weighted pick that avoids the author's
recent looks), so memes do not all look alike. This is the only place a look is defined; the prompts, the API and
the composer read it. The ghost always keeps its shape (teardrop body, wisps, big oval eyes); the look changes how it
is rendered. Everything is our own cast: never Sanrio, Pixar or any existing character.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

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
    art: str  # rendering direction for the build call
    cast: str  # how the ghost and the supporting cast are rendered here
    palette: tuple[str, ...]  # dark to light, for the drawings
    theme: Theme
    suits: str  # what jokes it serves, read by the writers' room
    weight: int = 3  # relative chance in a random pick


LOOKS: tuple[Look, ...] = (
    Look(
        "inferno_flat",
        "Inferno flat",
        "The brand look: bold flat vector in the inferno colors.",
        "Modern flat-vector cartoon: bold shapes, clean 4-6px outlines (#14101f, round joins), simple gradients, soft shadows, "
        "generous negative space.",
        "The ghost in its brand colors: violet (#4a0c6b) through magenta (#a52c60) to orange (#ed6925) and yellow (#f7d13d) at the edges.",
        ("#000004", "#1b0c41", "#4a0c6b", "#781c6d", "#a52c60", "#cf4446", "#ed6925", "#fb9b06", "#f7d13d", "#fcffa4"),
        Theme(
            "#1b0c41",
            "#fffaf0",
            "#14101f",
            ("#ed6925", "#781c6d", "#f7d13d", "#cf4446", "#4a0c6b", "#fb9b06"),
            ("#ed6925", "#a52c60", "#4a0c6b"),
        ),
        "any joke; the safe default",
        weight=2,
    ),
    Look(
        "kawaii",
        "Kawaii",
        "Chibi cute: pastels, thick round outlines, blush cheeks, sparkles.",
        "Kawaii chibi cartoon: huge heads, tiny bodies, thick soft rounded outlines in a darker tint of each fill, pastel flat color with a "
        "single soft highlight, blush circles on cheeks, tiny sparkles and hearts, simple dot eyes with a glint, pastel gradient backdrops.",
        "The ghost as a round, squishy chibi blob in pastel pink with lavender wisps, a tiny bow, and sparkly dot eyes. Supporting cast are "
        "cute pastel blobs and chibi people with dot eyes. Original characters only: never Hello Kitty, Sanrio or any existing brand.",
        ("#4a2d5f", "#6b4a8f", "#b9a2ff", "#ff8fb8", "#ffc09f", "#ffe58f", "#9be3c8", "#8fd3ff", "#fff5fa"),
        Theme(
            "#6b4a8f",
            "#fff5fa",
            "#4a2d5f",
            ("#ff8fb8", "#9be3c8", "#b9a2ff", "#ffc09f", "#8fd3ff", "#ffe58f"),
            ("#d94f8a", "#7a5fd0", "#4a2d5f"),
        ),
        "wholesome, relatable, gently absurd jokes; cute art against a brutal caption is gold",
    ),
    Look(
        "soft_3d",
        "Soft 3D",
        "Clay-render realism: gradient shading, rim light, glossy highlights.",
        "Soft 3D clay render look in SVG: smooth radial and linear gradients for volume, rim light on one edge, glossy specular highlights, "
        "soft contact shadows, subtle ambient occlusion, no outlines, shallow-depth-of-field blurred backgrounds.",
        "The ghost as a glossy, slightly translucent vinyl-toy figure with real volume, a warm inner glow and soft shadows. Supporting cast "
        "are smooth clay people and objects.",
        ("#1f2233", "#2b2f45", "#5b7cfa", "#9a6bd6", "#ef8fb0", "#e8704f", "#f2c14e", "#3fb8a5", "#f3f1ee"),
        Theme(
            "#2b2f45",
            "#f3f1ee",
            "#1f2233",
            ("#e8704f", "#5b7cfa", "#f2c14e", "#3fb8a5", "#9a6bd6", "#ef8fb0"),
            ("#c4553a", "#3f5fd6", "#2b2f45"),
        ),
        "product-demo and keynote parody, anything that benefits from deadpan seriousness",
    ),
    Look(
        "viridis_lab",
        "Viridis lab",
        "A scientific poster on grid paper in the viridis palette.",
        "Scientific-poster illustration: faint graph-paper grid or lab-bench backdrop, clean uniform line weights, flat fills from the "
        "viridis palette, small tick marks and figure-label flourishes (never real words), calm and precise.",
        "The ghost as a tidy lab-coat ghost in viridis teal and green with a yellow glow, wearing goggles or holding a clipboard. "
        "Supporting cast are simple scientists with dot eyes.",
        ("#440154", "#482878", "#3e4989", "#31688e", "#26828e", "#1f9e89", "#35b779", "#6ece58", "#b5de2b", "#fde725"),
        Theme(
            "#440154",
            "#f7fbe8",
            "#1b1030",
            ("#31688e", "#35b779", "#fde725", "#482878", "#1f9e89", "#b5de2b"),
            ("#31688e", "#482878", "#440154"),
        ),
        "data-science, experiment, statistics and causal-inference jokes",
    ),
    Look(
        "magma_noir",
        "Magma noir",
        "Film-noir spotlight and long shadows in the magma palette.",
        "Film-noir illustration: a hard spotlight cone, long diagonal shadows, venetian-blind light stripes, rain streaks, heavy darks, "
        "magma-palette glows (deep purple to hot pink to peach), bold graphic shapes.",
        "The ghost as a trench-coated detective ghost with a fedora and glowing eyes, lit from one side. Supporting cast are silhouettes "
        "with glowing eyes.",
        ("#000004", "#180f3e", "#451077", "#721f81", "#9f2f7f", "#cd4071", "#f1605d", "#fd9567", "#fec98d", "#fcfdbf"),
        Theme(
            "#180f3e",
            "#fdf3e7",
            "#0b0716",
            ("#cd4071", "#f1605d", "#fd9567", "#721f81", "#fec98d", "#9f2f7f"),
            ("#cd4071", "#721f81", "#180f3e"),
        ),
        "debugging mysteries, incident postmortems, 'who did this' jokes, dramatic understatement",
    ),
    Look(
        "corporate_slate",
        "Corporate slate",
        "Professional blues and grays, enterprise-deck illustration.",
        "Corporate-deck illustration: restrained flat vector in blues and grays, thin consistent outlines, subtle gradients, tidy "
        "front-on office scenes, one single accent color for the punchline object, lots of calm negative space.",
        "The ghost as a composed, translucent slate-blue ghost with a tiny lanyard, holding a laptop, completely deadpan. Supporting cast "
        "are generic office figures with dot eyes.",
        ("#16202b", "#1f2d3d", "#1d4e89", "#2f6fb0", "#4a90c2", "#6b7c8f", "#9db4cc", "#a3acb8", "#f4f6f8"),
        Theme(
            "#1f2d3d",
            "#f4f6f8",
            "#16202b",
            ("#2f6fb0", "#6b7c8f", "#9db4cc", "#1d4e89", "#4a90c2", "#a3acb8"),
            ("#2f6fb0", "#1d4e89", "#1f2d3d"),
        ),
        "enterprise, leadership, stakeholder and process jokes where the dry look is the joke",
    ),
    Look(
        "retro_comic",
        "Retro comic",
        "Pop-art halftone dots, bold primaries, action lines.",
        "Vintage pop-art comic: heavy black ink outlines, halftone dot shading (patterns of circles), bold primary colors on cream paper, "
        "speed lines and starburst shapes, high contrast.",
        "The ghost as a bold comic-book ghost with thick ink, halftone-shaded wisps and big expressive eyebrows. Supporting cast are "
        "pop-art figures in bold flat colors.",
        ("#111111", "#1a1a2e", "#1d6fd1", "#8338ec", "#e63946", "#f77f00", "#f4c20d", "#2a9d5c", "#fff6d6"),
        Theme(
            "#1a1a2e",
            "#fff6d6",
            "#111111",
            ("#e63946", "#f4c20d", "#1d6fd1", "#2a9d5c", "#f77f00", "#8338ec"),
            ("#c5303c", "#1d6fd1", "#1a1a2e"),
        ),
        "big reactions, hot takes, absurd escalation and sound-effect gags",
    ),
    Look(
        "pixel_arcade",
        "Pixel arcade",
        "16-bit pixel art on a rect grid, plasma palette.",
        "16-bit pixel art: build every shape from square <rect> pixels on a coarse grid (one pixel = 8-12 canvas units), no curves, "
        "limited plasma palette, dithering, a scanline or CRT-glow feel, chunky game-UI frames.",
        "The ghost as a classic arcade sprite: a pixel dome with a wavy pixel hem and big square eyes with glints, in plasma pink and "
        "yellow. Supporting cast are pixel sprites.",
        ("#0d0887", "#46039f", "#7201a8", "#9c179e", "#bd3786", "#d8576b", "#ed7953", "#fb9f3a", "#fdca26", "#f0f921"),
        Theme(
            "#0d0887",
            "#fdf6ff",
            "#1a0a3d",
            ("#bd3786", "#fdca26", "#46039f", "#ed7953", "#9c179e", "#fb9f3a"),
            ("#bd3786", "#7201a8", "#0d0887"),
        ),
        "gaming metaphors, 'game over' jokes, training runs, levels, boss fights and lives",
    ),
    Look(
        "whiteboard",
        "Whiteboard doodle",
        "Dry-erase marker sketch: wobbly lines, three marker colors.",
        "Whiteboard marker doodle: off-white board with faint smudges, wobbly hand-drawn marker lines with round caps, only three or four "
        "marker colors, simple stick-and-blob figures, arrows and underlines, no gradients.",
        "The ghost as a simple marker doodle: a wobbly teardrop outline with two oval eyes and a wavy hem, colored with one marker. "
        "Supporting cast are stick figures.",
        ("#263238", "#37474f", "#546e7a", "#1e88e5", "#43a047", "#fb8c00", "#e53935", "#8e24aa", "#fbfbf8"),
        Theme(
            "#37474f",
            "#fbfbf8",
            "#263238",
            ("#1e88e5", "#e53935", "#43a047", "#fb8c00", "#8e24aa", "#546e7a"),
            ("#1e88e5", "#546e7a", "#263238"),
        ),
        "process and architecture gags, 'the plan' and whiteboard-meeting humor",
    ),
    Look(
        "blueprint",
        "Blueprint",
        "Cyanotype technical drawing with dimension lines.",
        "Cyanotype blueprint: deep blue paper with a fine white grid, thin white and pale-cyan line drawings (no fills except light "
        "hatching), dimension arrows and callout leaders, construction circles, cividis yellow only for the one highlighted part.",
        "The ghost drawn as an engineering schematic: a white outline teardrop with dimension lines and an exploded-view hem, the eyes "
        "picked out in cividis yellow.",
        ("#00204d", "#0b2a4a", "#31446b", "#666970", "#948e77", "#c8b866", "#ffea46", "#cfe3f5", "#e8f1fa"),
        Theme(
            "#0b2a4a",
            "#e8f1fa",
            "#0b2a4a",
            ("#31446b", "#948e77", "#ffea46", "#00204d", "#c8b866", "#666970"),
            ("#31446b", "#00204d", "#0b2a4a"),
        ),
        "architecture, systems-design and over-engineering jokes",
    ),
    Look(
        "inferno_robots",
        "Inferno robots",
        "Retro tin robots in the inferno colors (the ghost cameos).",
        "Retro tin-toy illustration: chunky riveted metal shapes, simple gradients for a brushed-metal sheen, warm inferno glow, bold "
        "outlines (#14101f), stylized and friendly, never menacing.",
        "The cast are friendly retro tin robots in inferno colors (boxy bodies, round antenna bulbs, dot-matrix faces), and the Inferno "
        "Ghostwriter ghost makes a small cameo in the scene (peeking in, or as the robots' ghostwriter).",
        ("#000004", "#1b0c41", "#4a0c6b", "#781c6d", "#a52c60", "#cf4446", "#ed6925", "#fb9b06", "#f7d13d", "#fcffa4"),
        Theme(
            "#1b0c41",
            "#fffaf0",
            "#14101f",
            ("#ed6925", "#a52c60", "#f7d13d", "#cf4446", "#4a0c6b", "#fb9b06"),
            ("#cf4446", "#781c6d", "#1b0c41"),
        ),
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
) -> Look:
    """The author's pick, else the room's suggestion unless used lately, else a weighted pick that avoids recent looks.

    ``avoid`` is used by a redraw: the look being replaced."""
    if pick and is_look(pick):
        return BY_ID[pick.strip()]
    banned = {*recent[:2], *avoid}
    if suggested and is_look(suggested) and suggested.strip() not in banned:
        return BY_ID[suggested.strip()]
    pool = [look for look in LOOKS if look.id not in banned] or [look for look in LOOKS if look.id not in avoid] or list(LOOKS)
    return (rng or random).choices(pool, weights=[look.weight for look in pool])[0]


def themed(look: Look, palette: tuple[str, ...] = ()) -> Theme:
    """The look's theme; a brand palette (3+ colors) replaces its chart accents but keeps its surfaces."""
    if len(palette) < 3:
        return look.theme
    accents = tuple(palette[i % len(palette)] for i in range(6))
    t = look.theme
    return Theme(t.dark, t.paper, t.ink, accents, t.bands, t.bubble_fill)


def menu() -> str:
    """The look menu for the ideation prompt."""
    return "\n".join(f"- `{look.id}`: **{look.label}**. {look.description} Suits: {look.suits}." for look in LOOKS)
