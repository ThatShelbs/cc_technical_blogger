"""Redraw with a brain: critique the current image, decide how to improve it, and add one controlled twist.

Every Redraw (opening image, closing meme and every illustration, diagram, chart, icon and screenshot between) goes
through here, so the image gets better, not just different:

1. **Brainstorm** (``ImprovementPlan``): Claude looks at the current image (the PNG when the connection can show it,
   else its source) and names what is weakest and the concrete changes that would make it clearer, sharper or funnier.
2. **Twist** (``choose_tweaks``, code, no model call): one or two experiments from the catalog below (another palette,
   another cast such as dogs or people instead of the ghost, another staging or medium), skipping what the last redraws
   already tried, so repeated redraws explore instead of circling. The author can pin any of them (*Remix*).
3. The result (``Remix``) is stored on the image so the card can say what was tried, and so the next redraw avoids it.

This module is the only place a tweak is defined. The frontend reads it from ``GET /api/remix-options``.
Brand-kit palettes and fonts are the author's own decision: a random twist never replaces them (a pinned one does).
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, replace
from typing import Any

from pydantic import BaseModel, Field

from inferno_ghostwriter.config import Settings
from inferno_ghostwriter.images.base import thumbnail_png
from inferno_ghostwriter.llm import LLM, LLMError, SystemBlock
from inferno_ghostwriter.llm.base import LLMImagesUnsupportedError, UsageSink
from inferno_ghostwriter.prompts import raw, render

log = logging.getLogger(__name__)

# What a redraw may vary.
PALETTE, CAST, STAGING, MEDIUM = "palette", "cast", "staging", "medium"
DIMENSIONS = (PALETTE, CAST, STAGING, MEDIUM)
DIMENSION_LABELS = {PALETTE: "Colors", CAST: "Who is in it", STAGING: "Staging", MEDIUM: "Medium"}
# Tweaks remembered per image so redraws do not repeat themselves.
MEMORY = 8


@dataclass(frozen=True)
class Tweak:
    dimension: str
    id: str
    label: str
    # What the drawing is told.
    direction: str
    # Dark to light hex colors (palette tweaks only): used by code-drawn images and charts as their palette.
    colors: tuple[str, ...] = ()


TWEAKS: list[Tweak] = [
    # -- colors ------------------------------------------------------------------------------------
    Tweak(
        PALETTE,
        "inferno",
        "Inferno (house)",
        "The inferno palette: deep purple through crimson and orange to pale yellow.",
        ("#000004", "#1b0c41", "#4a0c6b", "#781c6d", "#a52c60", "#cf4446", "#ed6925", "#fb9b06", "#f7d13d", "#fcffa4"),
    ),
    Tweak(
        PALETTE,
        "viridis",
        "Viridis",
        "A viridis palette: deep indigo, teal and green to bright yellow-green, calm and scientific.",
        ("#440154", "#482878", "#3e4989", "#31688e", "#26828e", "#1f9e89", "#35b779", "#6ece58", "#b5de2b", "#fde725"),
    ),
    Tweak(
        PALETTE,
        "ocean",
        "Ocean",
        "A cool ocean palette: navy, cobalt, cyan and seafoam with one coral accent.",
        ("#0b1d3a", "#1d4e89", "#00a6d6", "#7fdbca", "#ff6f59"),
    ),
    Tweak(
        PALETTE,
        "sunrise",
        "Sunrise pastel",
        "A soft sunrise pastel palette: peach, rose, lavender and butter yellow on a warm cream ground.",
        ("#5b4b8a", "#d56a8b", "#f4a78d", "#ffd9a0", "#fff4dc"),
    ),
    Tweak(
        PALETTE,
        "forest",
        "Forest",
        "An earthy forest palette: deep green, moss, ochre and clay with a warm paper ground.",
        ("#16302b", "#2f6f4f", "#8fa31e", "#d9a441", "#c4572d"),
    ),
    Tweak(
        PALETTE,
        "mono_flame",
        "One flame on grey",
        "Monochrome greys with exactly one hot orange accent for the focal point.",
        ("#1c1c24", "#4a4a58", "#8a8a98", "#d8d8e0", "#ff6a1a"),
    ),
    Tweak(
        PALETTE,
        "magma",
        "Magma noir",
        "A magma palette on near-black: purple glows to hot pink and peach, dramatic contrast.",
        ("#000004", "#180f3e", "#451077", "#721f81", "#9f2f7f", "#cd4071", "#f1605d", "#fd9567", "#fec98d", "#fcfdbf"),
    ),
    Tweak(
        PALETTE,
        "candy",
        "Candy pop",
        "A bold, playful pop palette: hot pink, electric blue, lemon and mint on white.",
        ("#2b1a4f", "#ff3d81", "#2d7dff", "#ffd23f", "#3ddc97"),
    ),
    Tweak(
        PALETTE,
        "blueprint",
        "Blueprint",
        "A blueprint palette: deep blue paper with white and pale cyan linework and one yellow highlight.",
        ("#0a2a5e", "#1e5aa8", "#6fb1e8", "#dff1ff", "#ffd23f"),
    ),
    Tweak(
        PALETTE,
        "sepia",
        "Sepia print",
        "A warm sepia print palette: ink brown, rust and tan on aged paper, like a vintage engraving.",
        ("#2b1d14", "#6b4226", "#b0703c", "#e0b98a", "#f6ead7"),
    ),
    # -- who is in it --------------------------------------------------------------------------------
    Tweak(CAST, "ghost", "The ghost", "Our friendly spectral ghost is the star of the scene (the house character)."),
    Tweak(
        CAST,
        "robots",
        "Friendly robots",
        "Replace any characters with friendly, round, expressive robots (never menacing, never a humanoid chrome android).",
    ),
    Tweak(CAST, "dogs", "Dogs", "Replace any characters with expressive cartoon dogs (a few breeds, original designs)."),
    Tweak(CAST, "cats", "Cats", "Replace any characters with expressive cartoon cats (original designs)."),
    Tweak(
        CAST,
        "people",
        "Stylized people",
        "Replace any characters with stylized, faceless-or-simple-faced original people of varied looks (never a real person's likeness).",
    ),
    Tweak(
        CAST,
        "animals",
        "Woodland animals",
        "Replace any characters with an ensemble of original woodland animals (fox, owl, hedgehog, raccoon).",
    ),
    Tweak(CAST, "octopus", "An octopus", "Replace any characters with one multitasking cartoon octopus."),
    Tweak(
        CAST,
        "objects",
        "Living objects",
        "Replace any characters with everyday objects that have simple faces and arms (a mug, a cable, a sticky note, a plant).",
    ),
    Tweak(CAST, "none", "No characters", "Leave characters out entirely; let objects, shapes and structure carry the idea."),
    # -- staging -------------------------------------------------------------------------------------
    Tweak(
        STAGING,
        "close_up",
        "Close-up",
        "Stage it as a dramatic close-up: one subject large, cropped tight, with a blurred or empty background.",
    ),
    Tweak(
        STAGING,
        "wide",
        "Wide shot",
        "Stage it as a wide shot: a small subject in a big, well-composed environment with lots of negative space.",
    ),
    Tweak(STAGING, "isometric", "Isometric", "Stage it as an isometric 3/4 view from above, like a tiny diorama."),
    Tweak(STAGING, "top_down", "Top-down", "Stage it as a flat top-down (bird's-eye) view."),
    Tweak(STAGING, "split", "Before / after split", "Stage it as a split composition that contrasts two states side by side."),
    Tweak(STAGING, "symmetry", "Strict symmetry", "Stage it with strict symmetry around the centre and one dominant focal point."),
    Tweak(
        STAGING,
        "diagonal",
        "Diagonal energy",
        "Stage it on a strong diagonal with the focal point off-centre and movement across the frame.",
    ),
    # -- medium --------------------------------------------------------------------------------------
    Tweak(MEDIUM, "flat", "Flat vector", "Flat vector shapes with crisp edges and subtle gradients."),
    Tweak(MEDIUM, "paper_cut", "Paper cut", "Layered paper-cut shapes with soft drop shadows between the layers."),
    Tweak(MEDIUM, "line_art", "Line art", "Confident monoline art with one or two flat color fills."),
    Tweak(MEDIUM, "clay", "Soft 3D clay", "Soft, rounded 3D clay-render shapes with gentle highlights (drawn with gradients)."),
    Tweak(
        MEDIUM, "woodcut", "Woodcut / risograph", "A risograph or woodcut print look: two or three overprinting inks, bold shapes, grain."
    ),
]
BY_ID = {(t.dimension, t.id): t for t in TWEAKS}
# Opening images and closing memes stay in the house palettes (images/palettes.py), with white, gray or black grounds.
HOUSE = ("inferno", "magma", "viridis")

# Where each dimension makes sense. A chart has no cast; a code-drawn template has no staging.
KIND_DIMENSIONS: dict[str, tuple[str, ...]] = {
    "hero": (PALETTE, CAST, STAGING, MEDIUM),
    "illustration": (PALETTE, CAST, STAGING, MEDIUM),
    "meme": (PALETTE, CAST),
    "icon": (PALETTE, MEDIUM),
    "diagram": (PALETTE, STAGING),
    "screenshot": (PALETTE,),
    "chart": (PALETTE,),
    # Opening styles (the hero's room): the style decides what is meaningful to vary.
    "opening:editorial": (PALETTE, CAST, STAGING, MEDIUM),
    "opening:data_art": (PALETTE, STAGING, MEDIUM),
    "opening:receipt": (PALETTE,),
    "opening:meme": (PALETTE, CAST),
}
TEMPLATE_DIMENSIONS = (PALETTE,)


def get_tweak(dimension: str, tweak_id: str) -> Tweak | None:
    return BY_ID.get((dimension, tweak_id))


def dimensions_for(kind: str, style: str = "") -> tuple[str, ...]:
    """The dimensions a redraw of this image may vary (``style`` is the opening style for a hero)."""
    if kind == "hero":
        return KIND_DIMENSIONS.get(f"opening:{style}", KIND_DIMENSIONS["hero"] if not style else TEMPLATE_DIMENSIONS)
    return KIND_DIMENSIONS.get(kind, (PALETTE,))


def choose_tweaks(
    allowed: tuple[str, ...],
    *,
    recent: list[str] | None = None,
    pinned: dict[str, str] | None = None,
    rng: random.Random | None = None,
    count: int = 2,
    keep_palette: bool = False,
    house_only: bool = False,
) -> list[Tweak]:
    """The experiments this redraw tries: the author's pins, then random ones that differ from the last redraws.

    ``recent`` holds ``"dimension:id"`` entries, newest first. A random palette is skipped when ``keep_palette``
    (the post has a brand kit palette); a pinned one still applies.
    """
    rng = rng or random.Random()
    recent = recent or []
    chosen: list[Tweak] = []
    for dimension, tweak_id in (pinned or {}).items():
        tweak = get_tweak(dimension, tweak_id)
        if tweak is not None and dimension in allowed and tweak_id != "auto":
            chosen.append(tweak)
    pinned_dims = {t.dimension for t in chosen}
    free = [d for d in allowed if d not in pinned_dims and not (d == PALETTE and keep_palette)]
    # A pinned dimension set to "auto" is free again; the rest are shuffled so the dimension that varies changes too.
    rng.shuffle(free)
    # Dimensions that were varied least recently go first.
    free.sort(key=lambda d: next((i for i, entry in enumerate(recent) if entry.startswith(f"{d}:")), len(recent) + 1), reverse=True)
    for dimension in free[: max(0, count - len(chosen))]:
        pool = [t for t in TWEAKS if t.dimension == dimension and not (house_only and dimension == PALETTE and t.id not in HOUSE)]
        options = [t for t in pool if f"{dimension}:{t.id}" not in recent[:MEMORY]] or pool
        # The ghost is the house cast: it is only a random pick when the redraw is already away from it (it can return).
        chosen.append(rng.choice(options))
    return chosen


def memory_entry(tweak: Tweak) -> str:
    return f"{tweak.dimension}:{tweak.id}"


class ImprovementPlan(BaseModel):
    """Claude's critique of the current image and how to make the next one better."""

    weakness: str = Field(description="The single biggest thing holding the current image back, in one sentence.")
    improvements: list[str] = Field(
        description="One to four concrete changes that make it clearer, sharper, funnier or more relevant (add, cut, enlarge, reframe)."
    )
    keep: list[str] = Field(description="What already works and must survive the redraw.")
    fresh_angle: str = Field(description="One bolder idea for the redraw that the first draft did not try.")


class Remix(BaseModel):
    """What this redraw tried; stored on the image."""

    weakness: str = ""
    improvements: list[str] = []
    fresh_angle: str = ""
    tweaks: list[dict[str, str]] = []
    # "dimension:id" of the last few redraws, newest first.
    recent: list[str] = []
    # Whether Claude critiqued the image (False when the call failed or no redraw plan was asked for).
    brainstormed: bool = False

    @property
    def summary(self) -> str:
        parts = [self.weakness] if self.weakness else []
        parts += self.improvements[:2]
        return " ".join(p.rstrip(".") + "." for p in parts)


def variation_text(plan: ImprovementPlan | None, tweaks: list[Tweak], *, kind: str = "") -> str:
    """The redraw instruction every builder gets in place of its generic "give it a fresh composition" line."""
    lines = ["This is a redraw. Make it better, not just different:"]
    if plan is not None:
        lines.append(f"- Biggest weakness to fix: {plan.weakness}")
        lines += [f"- Improve: {item}" for item in plan.improvements]
        if plan.fresh_angle:
            lines.append(f"- A bolder angle to try: {plan.fresh_angle}")
        if plan.keep:
            lines.append("- Keep: " + "; ".join(plan.keep))
    else:
        lines.append("- Keep the idea but give it a clearly stronger composition, clearer focal point and cleaner details.")
    for tweak in tweaks:
        if tweak.dimension == PALETTE and kind in ("chart",):
            continue  # applied as the chart's palette in code
        lines.append(f"- Experiment ({DIMENSION_LABELS[tweak.dimension].lower()}): {tweak.direction}")
    return "\n".join(lines)


def apply_to_art(art: Any, plan: ImprovementPlan | None, tweaks: list[Tweak]) -> Any:
    """Return the art direction with the redraw folded in (``art`` is an ArtDirection).

    A palette tweak replaces the palette code-drawn images and charts use and tells SVG drawings the colors; a cast
    tweak sets the meme cast. The critique and every tweak ride along so each builder words them for its own image
    (``variation_for``).
    """
    palette = next((t for t in tweaks if t.dimension == PALETTE and t.colors), None)
    cast = next((t for t in tweaks if t.dimension == CAST), None)
    changes: dict[str, Any] = {"improvement": plan, "tweaks": tuple(tweaks)}
    if palette is not None:
        changes["palette"] = palette.colors
        changes["brand"] = "\n".join(
            part
            for part in (
                f"Palette for this redraw (use these instead of the inferno palette): {' '.join(palette.colors)}. {palette.direction}",
                art.brand if not art.palette else "",
            )
            if part
        )
    if cast is not None:
        changes["cast"] = cast.direction
    return replace(art, **changes)


def edit_note(edits: tuple[str, ...] | list[str], current: str, *, what: str = "design") -> str:
    """Prompt text that makes a redraw build on the author's edited picture instead of the original idea."""
    lines = "\n".join(f"- {e}" for e in edits)
    return (
        "\nThe author edited this image by instruction, and the edited picture is what to build on:\n"
        f"<edits>\n{lines}\n</edits>\n<current_{what}>\n{current}\n</current_{what}>\n"
        "Keep the current content and every change above; apply only the new look this redraw asks for. "
        "Do not go back to the original idea.\n"
    )


def variation_for(art: Any, allowed: tuple[str, ...] | None = None, *, kind: str = "") -> str:
    """The redraw instruction for one builder: the critique plus the twists that make sense for what it draws.

    ``allowed`` limits the twists to those dimensions (a data-art drawing takes no cast; a meme takes its cast
    separately). Empty when the art direction carries no redraw."""
    if art.improvement is None and not art.tweaks:
        return ""
    tweaks = [t for t in art.tweaks if allowed is None or t.dimension in allowed]
    return variation_text(art.improvement, tweaks, kind=kind)


def to_remix(plan: ImprovementPlan | None, tweaks: list[Tweak], previous: dict[str, Any] | None) -> dict[str, Any]:
    recent = [*(memory_entry(t) for t in tweaks), *[str(e) for e in (previous or {}).get("recent", [])]]
    remix = Remix(
        weakness=plan.weakness if plan else "",
        improvements=plan.improvements if plan else [],
        fresh_angle=plan.fresh_angle if plan else "",
        tweaks=[{"dimension": t.dimension, "id": t.id, "label": t.label} for t in tweaks],
        recent=recent[:MEMORY],
        brainstormed=plan is not None,
    )
    return remix.model_dump()


def pins_from(raw_pins: dict[str, str] | None) -> dict[str, str]:
    """Only real dimensions and tweak ids (anything else, including ``auto``, is left to chance)."""
    return {d: i for d, i in (raw_pins or {}).items() if d in DIMENSIONS and get_tweak(d, i) is not None}


async def brainstorm(
    llm: LLM,
    settings: Settings,
    *,
    kind: str,
    title: str,
    caption: str,
    design: str,
    png: bytes | None,
    context: str,
    previous: dict[str, Any] | None,
    usage: UsageSink | None = None,
) -> ImprovementPlan | None:
    """Claude critiques the current image and proposes the improvement; None when the call fails (the redraw goes on)."""
    tried = [str(e) for e in (previous or {}).get("improvements", [])]
    prompt = render(
        "image_improve",
        kind=kind,
        title=title,
        caption=caption or "(none)",
        design=design[:9000] or "(not available: judge from the picture)",
        context=context or "(none)",
        tried=(
            "\nImprovements the last redraw already made (do not repeat them; find what is still weak):\n"
            + "\n".join(f"- {t}" for t in tried)
            + "\n"
        )
        if tried
        else "",
        shown="The current image is attached." if png else "The image itself cannot be shown to you; judge it from its source above.",
    )
    try:
        return await llm.structured(
            task="image improvement plan",
            system=[SystemBlock(raw("image_improve_system"), cache=True)],
            prompt=prompt,
            schema=ImprovementPlan,
            effort=settings.effort_image_improve,
            max_tokens=4000,
            usage=usage,
            images=[thumbnail_png(png)] if png else None,
        )
    except LLMImagesUnsupportedError:
        if png is None:
            return None
        return await brainstorm(
            llm, settings, kind=kind, title=title, caption=caption, design=design, png=None, context=context, previous=previous, usage=usage
        )
    except LLMError as exc:
        log.info("Image improvement plan failed (%s); redrawing with a twist only", exc)
        return None
