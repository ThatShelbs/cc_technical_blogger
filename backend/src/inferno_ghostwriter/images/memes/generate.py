"""The writers' room pitches and scores five concepts, then the winner is drawn into its format.

A format with art needs a second call (production draws it); a format with none (chat, terminal, label,
charts) is composed straight from the pitch. Concepts are kept on the image, so "New idea" and the ideas
board move between pitches without another ideation call, "Redraw" draws the same joke again, and the
author can retype the words with no model call at all."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from inferno_ghostwriter.config import Settings
from inferno_ghostwriter.images.base import PLACEHOLDER_RE, ImageProviderError, draw_with_retry, thumbnail_png
from inferno_ghostwriter.images.memes.compose import MASCOT_SCENE, compose
from inferno_ghostwriter.images.memes.formats import CAST, FALLBACK, MemeFormat, build_spec, get_format, menu
from inferno_ghostwriter.images.memes.looks import Look, choose_look, get_look, themed
from inferno_ghostwriter.images.memes.looks import menu as looks_menu
from inferno_ghostwriter.images.memes.specs import (
    CastPick,
    MemeArt,
    MemeBuild,
    MemeConcept,
    MemeDatum,
    MemeIdeas,
    MemeStagingEdit,
    MemeText,
    PanelPick,
)
from inferno_ghostwriter.images.palettes import Scheme, brand_scheme, from_id, house_ramp
from inferno_ghostwriter.images.palettes import pick as pick_colors
from inferno_ghostwriter.images.panel import PanelResult, convene, final_pick, parse_seats
from inferno_ghostwriter.images.remix import PALETTE, ImprovementPlan, Tweak, edit_note, variation_for
from inferno_ghostwriter.llm import LLM, LLMError, SystemBlock
from inferno_ghostwriter.llm.base import UsageSink
from inferno_ghostwriter.prompts import raw, render

log = logging.getLogger(__name__)

STATE_VERSION = 2
POST_LIMIT = 24000
POST_TAIL = 8000
MADE_UP = "(data: entirely made up)"
OLD_MEME = "This meme was made by an older version; click New idea to make one that can be edited."

HUMOR_GUIDE = {
    range(0, 3): "Dry and gentle: a wry chart joke, Venn or artifact; one quiet twist, nothing absurd.",
    range(3, 6): "Clever and relatable: one clean twist on something every practitioner has lived through.",
    range(6, 9): "Playful: famous formats, comics and puns are all welcome.",
    range(9, 11): "Go big: absurd escalation, shameless puns, callbacks to the post's running gags.",
}

Built = tuple[MemeBuild, bytes, int, int]


@dataclass
class MemeContext:
    """What the writers' room knows about the post."""

    title: str
    markdown: str
    voice_profile: str
    brief: str
    joke: str = ""
    callbacks: str = ""
    humor: int = 5
    # Formats this author's last memes used, newest first: the room avoids repeating them.
    recent_formats: tuple[str, ...] = ()
    # The post's formula as the room should read it (``writer.formulas.meme_note``); "" when none is in force.
    formula: str = ""
    # Looks this author's latest memes used, newest first: a new meme avoids them so the memes vary.
    recent_looks: tuple[str, ...] = ()
    # "closing" (the last image) or "opening" (the first image and thumbnail, see ``images.opening``).
    position: str = "closing"
    # For a closing meme when the post also opens with one (a meme sandwich): the opener's format and premise.
    opening: str = ""
    # Color schemes ("ramp:surface") this author's latest images used, newest first: a new one rotates away from them.
    recent_schemes: tuple[str, ...] = ()
    # The author's image taste (liked and passed formats, looks, casts) as the room should read it; "" when unknown.
    taste: str = ""
    # Look weights from the author's ratings (1.0 = neutral).
    look_weights: dict[str, float] | None = None


def position_guide(post: MemeContext) -> str:
    """What the room is pitching: the closer, the closer of a meme sandwich, or the opener."""
    if post.position == "opening":
        return (
            "Pitch the opening meme for this post: the first thing a reader sees, and the post's thumbnail. It sets up the "
            "tension, pain or question the post resolves, so it must land for someone who has not read the post yet: no "
            "spoilers and no callbacks to things the post explains later. Favor formats that still read as a wide thumbnail. "
            "The post closes with its own meme, so save the big payoff for the ending."
        )
    if post.opening:
        return (
            "Pitch the closing meme for this post. The post also opens with a meme, so this is a meme sandwich. The opener: "
            f"{post.opening}. Use a different format family from the opener and never repeat its joke; the best closer pays "
            "it off (a bookend) now that the reader has the whole story."
        )
    return "Pitch the closing meme for this post."


@dataclass
class ArtDirection:
    """How the drawings should look."""

    visual_style: str
    brand: str = ""
    image_guidance: str = ""
    palette: tuple[str, ...] = ()
    # A redraw's critique and twists (see images/remix.py), and the cast it asks for ("" = the house ghost).
    improvement: ImprovementPlan | None = None
    tweaks: tuple[Tweak, ...] = ()
    cast: str = ""
    # The author's edit instructions for the image being redrawn: when set, a redraw builds on the edited picture.
    edits: tuple[str, ...] = ()


@dataclass
class MemeResult:
    png: bytes
    width: int
    height: int
    provider: str
    spec: str
    alt: str
    caption: str


def _kit_menu() -> str:
    from inferno_ghostwriter.images.kit import menu as kit_menu
    from inferno_ghostwriter.images.kit.props import menu as props_menu

    return kit_menu() + "\n" + props_menu()


def humor_guide(level: int) -> str:
    return next(text for span, text in HUMOR_GUIDE.items() if max(0, min(10, level)) in span)


def voice_section(voice_profile: str, heading: str) -> str:
    """The body of the voice profile's ``## <heading>...`` section ('' when there is none)."""
    match = re.search(rf"^##\s+{heading}.*?$(.*?)(?=^##\s|\Z)", voice_profile, flags=re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else ""


def plan_callbacks(plan: dict[str, Any] | None) -> str:
    """The plan's running jokes and key concepts: the best raw material for a closing callback."""
    lines = []
    for item in (plan or {}).get("callbacks") or []:
        if isinstance(item, dict) and item.get("idea"):
            kind = "Running joke" if item.get("kind") == "running_joke" else "Key concept"
            payoff = f" (payoff: {item['payoff']})" if item.get("payoff") else ""
            lines.append(f"- {kind}: {item['idea']}{payoff}")
    return "\n".join(lines)


def clip_post(markdown: str, limit: int = POST_LIMIT, tail: int = POST_TAIL) -> str:
    """The post without image placeholders. A long post keeps its opening and its ending, where the callbacks pay off."""
    text = PLACEHOLDER_RE.sub("", markdown).strip()
    if len(text) <= limit:
        return text
    if tail <= 0:
        return f"{text[:limit].rstrip()}\n\n[... the rest of the post is omitted ...]"
    return f"{text[: limit - tail].rstrip()}\n\n[... the middle of the post is omitted ...]\n\n{text[-tail:].lstrip()}"


def load_state(spec: str) -> dict[str, Any] | None:
    """The meme's stored concepts and build, or None for older memes (plain SVG + captions)."""
    try:
        state = json.loads(spec) if spec else None
    except json.JSONDecodeError:
        return None
    return state if isinstance(state, dict) and state.get("version") == STATE_VERSION else None


def load_concepts(state: dict[str, Any]) -> list[MemeConcept]:
    """The stored pitches (ones saved before pitches carried chart data and a caption get empty ones)."""
    return [MemeConcept.model_validate({"data": [], "caption": "", **c}) for c in state.get("concepts", [])]


def total(concept: MemeConcept) -> tuple[int, int]:
    s = concept.scores
    return (s.relevance + s.recognizability + s.surprise + s.clarity + s.voice_fit + s.standalone, s.relevance + s.clarity)


def panel_scores(state: dict[str, Any], count: int) -> list[int] | None:
    """The independent panel's score per stored concept (a joke it ruled out scores far below the rest), or None."""
    scores = (state.get("panel") or {}).get("scores")
    return [int(x) for x in scores] if isinstance(scores, list) and len(scores) == count else None


def pick(concepts: list[MemeConcept], preferred: int | None, skip: set[int], panel: list[int] | None = None) -> int | None:
    """The preferred concept if usable, else the best-scoring untried concept with a known format.

    The panel's scores rank the concepts when there are any; the writers' own scores break ties and stand in without."""
    usable = [i for i, c in enumerate(concepts) if i not in skip and get_format(c.format)]
    if preferred in usable:
        return preferred
    return max(usable, key=lambda i: ((panel[i] if panel else 0), total(concepts[i])), default=None)


def punched_up(fmt: MemeFormat, concept: MemeConcept, punch: list[MemeText]) -> list[MemeText] | None:
    """The panel's sharper words, when they cover every required slot and fit every limit; else None."""
    words = {t.slot: t.text.strip() for t in punch}
    old = {t.slot: t for t in concept.texts}
    texts = []
    for slot in fmt.slots:
        text = words.get(slot.name, "")
        if not text and not slot.optional:
            return None
        if len(text) > slot.max_chars:
            return None
        if text:
            texts.append(MemeText(slot=slot.name, text=text, speaker=old[slot.name].speaker if slot.name in old else ""))
    return texts


def validate(fmt: MemeFormat, build: MemeBuild) -> tuple[list[str], list[str]]:
    """(blocking problems, style problems). Overlong text still renders (it is shrunk to fit) but reads worse."""
    texts = {t.slot: t.text.strip() for t in build.texts}
    art = {a.region: a.svg.strip() for a in build.art}
    blocking, style = [], []
    for slot in fmt.slots:
        text = texts.get(slot.name, "")
        if not text and not slot.optional:
            blocking.append(f"Text slot `{slot.name}` is empty.")
        elif len(text) > slot.max_chars * 1.25:
            style.append(f"Text slot `{slot.name}` has {len(text)} characters; the limit is {slot.max_chars}.")
    blocking += [f"Art region `{r.name}` has no drawing." for r in fmt.regions if not art.get(r.name)]
    if fmt.id == "joke_pie_3d" and sum(1 for d in build.data if d.value > 0) < 2:
        blocking.append("The pie needs 2-6 slices with positive values in `data`.")
    if fmt.id == "spurious_correlation" and len({d.series for d in build.data}) < 2:
        blocking.append("The correlation chart needs two series ('a' and 'b') in `data`.")
    return blocking, style


def cast_dict(cast: list[CastPick]) -> dict[str, dict[str, str]]:
    return {c.role: {"kind": c.kind, "expression": c.expression, "accessory": c.accessory} for c in cast if c.role}


def scheme_of(state: dict[str, Any] | None, palette: tuple[str, ...], look: Look | None) -> Scheme:
    """The colors a meme is drawn in: a brand palette first, then the stored scheme, then the look's default."""
    if len(palette) >= 3 and house_ramp(palette) is None:
        return brand_scheme(palette)
    stored = from_id(str((state or {}).get("scheme") or ""))
    return stored or (look or get_look(None)).default_scheme


def pick_scheme(post: MemeContext, look: Look, palette: tuple[str, ...], avoid: str = "") -> Scheme:
    """A new meme's colors: the brand palette, else a ramp and surface the author's latest images did not use."""
    dark = True if look.tone == "dark" else False if look.tone == "light" else None
    return pick_colors(palette, post.recent_schemes, ramp=look.ramp or None, dark=dark, avoid=[avoid] if avoid else ())


def render_build(
    fmt: MemeFormat, build: MemeBuild, palette: tuple[str, ...] = (), look: Look | None = None, sch: Scheme | None = None
) -> tuple[bytes, int, int]:
    look = look or get_look(None)
    sch = sch or scheme_of(None, palette, look)
    palette = palette if house_ramp(palette) is None else ()  # a house ramp is a scheme, not a brand palette
    return compose(
        fmt,
        {t.slot: t for t in build.texts},
        {a.region: a.svg for a in build.art},
        build.cast_defs,
        build.data,
        palette=palette,
        theme=themed(look, palette, sch),
        look=look.id,
        sch=sch,
        cast=cast_dict(build.cast),
        panels=[p.model_dump() for p in build.panels],
    )


def look_direction(look: Look) -> str:
    """The look as the build prompt reads it: how to draw, and the palette to draw in."""
    return (
        f"Look for this meme: **{look.label}**. {look.art}\n"
        f"Palette for the drawings, dark to light (unless a brand palette is given): {' '.join(look.palette)}."
    )


def alt_text(
    fmt: MemeFormat,
    texts: list[MemeText],
    data: list[MemeDatum],
    cast: list[CastPick] | None = None,
    panels: list[PanelPick] | None = None,
) -> str:
    """Alt text written from the meme's own parts, so it is always right: the format, who is in it and every word."""
    words = " / ".join(t.text.strip() for t in texts if t.text.strip())
    chart = "; ".join(f"{d.label}: {d.value:g}" for d in data)
    who = ""
    if panels:
        who = " " + " ".join(
            f"Panel {i + 1}: " + ", ".join(f"a {c.expression.replace('_', ' ')} {c.kind}" for c in p.characters) + "."
            for i, p in enumerate(panels)
        )
    elif fmt.staged and fmt.family != "comic":
        who = f" {fmt.recognizable}"
        recast = [f"{c.role} played by a {c.kind}" for c in (cast or []) if c.kind and c.kind != "ghost"]
        if recast:
            who += " (" + ", ".join(recast) + ")"
    return f"{fmt.name} meme.{who} Text: {words}." + (f" Data: {chart}." if chart else "")


def concept_build(fmt: MemeFormat, concept: MemeConcept) -> MemeBuild:
    """A format with no art needs no production call: the pitch already has its words, data and caption."""
    return MemeBuild(
        texts=concept.texts,
        cast_defs="",
        art=[],
        data=concept.data,
        alt=alt_text(fmt, concept.texts, concept.data, concept.cast, concept.panels),
        caption=concept.caption,
        cast=concept.cast,
        panels=concept.panels,
    )


def fallback_build(concept: MemeConcept | None) -> MemeBuild:
    """The classic caption meme over the house mascot: used when a format cannot be drawn."""
    words = [t.text.strip() for t in (concept.texts if concept else []) if t.text.strip()]
    top, bottom = (words[0], words[-1]) if len(words) > 1 else ("", words[0] if words else "This is fine")
    return MemeBuild(
        texts=[MemeText(slot="top", text=top[:80], speaker=""), MemeText(slot="bottom", text=bottom[:90], speaker="")],
        cast_defs="",
        art=[MemeArt(region="scene", svg=MASCOT_SCENE)],
        data=[],
        alt="The Inferno Ghostwriter ghost with the captions: " + " / ".join(w for w in (top, bottom) if w),
        caption=(concept.caption or concept.premise) if concept else "",
    )


class MemeMaker:
    def __init__(self, llm: LLM, settings: Settings) -> None:
        self.llm = llm
        self.settings = settings
        self.system = [SystemBlock(raw("meme_system"), cache=True)]

    async def make(
        self,
        spec: str,
        post: MemeContext,
        art: ArtDirection,
        *,
        redraw: bool = False,
        rethink: bool = False,
        meme_format: str | None = None,
        concept_index: int | None = None,
        look: str | None = None,
        review: bool = True,
        usage: UsageSink | None = None,
    ) -> MemeResult:
        """Make the meme. ``concept_index`` draws that stored pitch (the author picked it from the ideas board).

        ``look`` is the author's pick of how to draw it; without one the room's suggestion or a fresh look is used (a
        redraw or a new idea always moves to a different look). ``review`` lets Claude look at a drawn meme once."""
        state = load_state(spec)
        previous_look = str(state.get("look") or "") if state else ""
        index: int | None = None
        if concept_index is not None:
            if state is None or not 0 <= concept_index < len(state.get("concepts", [])):
                raise ImageProviderError("That idea is no longer available. Click New idea for fresh pitches.")
            index = concept_index
        elif state is not None and state.get("brief") == post.brief and not meme_format and (redraw or rethink):
            concepts = load_concepts(state)
            panel = panel_scores(state, len(concepts))
            index = (
                pick(concepts, None, set(state.get("tried", [])), panel) if rethink else pick(concepts, state.get("chosen"), set(), panel)
            )
            if index is None:
                # Every pitch has been used: ask the room for fresh ones that avoid them.
                state = await self._ideate(post, None, [c.premise for c in concepts], usage)
        else:
            state = await self._ideate(post, meme_format, [], usage)

        concepts = load_concepts(state)
        if index is None:
            index = pick(concepts, state.get("chosen"), set(), panel_scores(state, len(concepts)))
        concept = concepts[index] if index is not None else None
        tried = {*state.get("tried", []), *([index] if index is not None else [])}
        state.pop("fallback_from", None)

        fmt = (get_format(concept.format) if concept else None) or FALLBACK
        avoid = [previous_look] if previous_look and (redraw or rethink) and not look else []
        chosen_look = choose_look(look, concept.look if concept else None, post.recent_looks, avoid=avoid, weights=post.look_weights)
        state["look"] = chosen_look.id
        previous_scheme = str(state.get("scheme") or "")
        sch = pick_scheme(post, chosen_look, art.palette, avoid=previous_scheme if (redraw or rethink) else "")
        state["scheme"] = sch.id
        state.pop("review", None)
        # A redraw of an edited meme keeps the edits: its current art and words go into the build.
        current = state.get("build") if art.edits and redraw and not meme_format and concept_index is None and not rethink else None
        built = (
            await self._produce(fmt, concept, post.title, art, chosen_look, redraw=redraw, current=current, usage=usage, sch=sch)
            if concept
            else None
        )
        if built is None and concept is not None:
            # The format could not be drawn. Another pitch in a format with no art (it cannot fail) keeps a whole
            # joke; squeezing this one into a caption meme is the last resort.
            state["fallback_from"] = fmt.id
            for other in sorted((i for i in range(len(concepts)) if i != index), key=lambda i: total(concepts[i]), reverse=True):
                other_fmt = get_format(concepts[other].format)
                direct = self._direct(other_fmt, concepts[other], art, chosen_look, strict=False, sch=sch) if other_fmt else None
                if direct is not None and other_fmt is not None:
                    index, concept, fmt, built = other, concepts[other], other_fmt, direct
                    tried.add(other)
                    break
        state["chosen"] = index
        state["tried"] = sorted(tried)
        fresh = not (redraw or rethink or concept_index is not None)
        if built is not None and concept is not None and review and self.settings.meme_review and fresh and index is not None:
            index, concept, fmt, built = await self._choose_render(
                state, post, art, chosen_look, sch, concepts, (index, concept, fmt, built), tried, usage
            )
            state["chosen"] = index
            state["tried"] = sorted(tried)
        return self._finish(state, fmt, concept, built, art)

    async def _choose_render(
        self,
        state: dict[str, Any],
        post: MemeContext,
        art: ArtDirection,
        look: Look,
        sch: Scheme,
        concepts: list[MemeConcept],
        first: tuple[int, MemeConcept, MemeFormat, Built],
        tried: set[int],
        usage: UsageSink | None,
    ) -> tuple[int, MemeConcept, MemeFormat, Built]:
        """Draw the best pitches (code renders, no model call), let the render panel look at them, and keep the pick.

        A blind reader who sees only the picture says what it means; that is matched against the pitch, so a meme that
        does not make sense to a stranger loses. The final pick may ask for one fix, applied by restaging."""
        panel_scores_ = panel_scores(state, len(concepts)) or [0] * len(concepts)
        ranked = sorted(
            (i for i in range(len(concepts)) if i != first[0] and get_format(concepts[i].format)),
            key=lambda i: (panel_scores_[i], total(concepts[i])),
            reverse=True,
        )
        options: list[tuple[int, MemeConcept, MemeFormat, Built]] = [first]
        for i in ranked:
            if len(options) >= max(1, self.settings.image_render_candidates):
                break
            if panel_scores_[i] < 0:
                continue
            other_fmt = get_format(concepts[i].format)
            built = self._direct(other_fmt, concepts[i], art, look, strict=False, sch=sch) if other_fmt else None
            if built is not None and other_fmt is not None:
                options.append((i, concepts[i], other_fmt, built))
        if len(options) < 2 and not parse_seats(self.settings.image_panel_render):
            return first
        pngs = [thumbnail_png(o[3][1]) for o in options]
        render_panel = await convene(
            self.llm,
            parse_seats(self.settings.image_panel_render),
            context=self._context(post),
            candidates=[f"[{o[2].name}] {o[1].premise}" for o in options],
            images=pngs,
            intents=[o[1].premise for o in options],
            usage=usage,
        )
        if not render_panel.answered:
            state["review"] = {"skipped": True, "note": "This connection cannot show Claude the image, so it was not reviewed."}
            return first
        order = render_panel.ranking()
        pick_ = await final_pick(
            self.llm,
            context=self._context(post),
            candidates=[f"[{o[2].name}] {o[1].premise}" for o in options],
            images=pngs,
            panel=render_panel,
            spec=self.settings.image_panel_final,
            usage=usage,
        )
        best = (
            pick_.chosen
            if pick_ is not None and (pick_.chosen not in render_panel.vetoed or len(render_panel.vetoed) == len(options))
            else order[0]
        )
        winner = options[best]
        tried.add(winner[0])
        verdict = "passed"
        if pick_ is not None and pick_.fix.strip() and winner[2].staged:
            fixed = await self._restage(state, winner[2], winner[3][0], pick_.fix, art, usage)
            if fixed is not None:
                winner = (winner[0], winner[1], winner[2], fixed)
                verdict = "redrawn"
        state["review"] = {
            "verdict": verdict,
            "panel": render_panel.summary(),
            "why": pick_.why if pick_ is not None else "",
            "fix": pick_.fix if pick_ is not None else "",
            "candidates": [o[0] for o in options],
            "winner": best,
        }
        return winner

    async def edit(self, spec: str, instruction: str, art: ArtDirection, *, usage: UsageSink | None = None) -> MemeResult:
        """Change the current meme as the author asks ("make the ghost look more smug"), keeping the rest."""
        state = load_state(spec)
        if state is None or not state.get("build"):
            raise ImageProviderError(OLD_MEME)
        fmt = get_format(str(state.get("format", ""))) or FALLBACK
        current = MemeBuild.model_validate(state["build"])
        if fmt.staged and not current.art:
            built = await self._restage(state, fmt, current, instruction, art, usage)
        else:
            look_ = get_look(state.get("look"))
            built = await self._revise(fmt, current, instruction, art, look_, usage, scheme_of(state, art.palette, look_))
        if built is None:
            raise ImageProviderError("Claude's edit could not be drawn. Try rewording the instruction.")
        return self._finish(state, fmt, None, built, art)

    def reword(self, spec: str, words: dict[str, str], art: ArtDirection) -> MemeResult:
        """Set the meme's words as the author typed them and draw it again. No model call: the art is kept as it is."""
        state = load_state(spec)
        if state is None or not state.get("build"):
            raise ImageProviderError(OLD_MEME)
        fmt = get_format(str(state.get("format", ""))) or FALLBACK
        current = MemeBuild.model_validate(state["build"])
        old = {t.slot: t for t in current.texts}
        texts = [
            MemeText(
                slot=s.name,
                text=words.get(s.name, old[s.name].text if s.name in old else "").strip(),
                speaker=old[s.name].speaker if s.name in old else "",
            )
            for s in fmt.slots
        ]
        build = current.model_copy(update={"texts": texts, "alt": alt_text(fmt, texts, current.data, current.cast, current.panels)})
        blocking, _ = validate(fmt, build)
        if blocking:
            raise ImageProviderError(" ".join(blocking))
        look_ = get_look(state.get("look"))
        png, width, height = render_build(fmt, build, art.palette, look_, scheme_of(state, art.palette, look_))
        return self._finish(state, fmt, None, (build, png, width, height), art)

    def _finish(
        self,
        state: dict[str, Any],
        fmt: MemeFormat,
        concept: MemeConcept | None,
        built: Built | None,
        art: ArtDirection,
    ) -> MemeResult:
        if built is None:
            fmt = FALLBACK
            build = fallback_build(concept)
            look_ = get_look(state.get("look"))
            png, width, height = render_build(fmt, build, art.palette, look_, scheme_of(state, art.palette, look_))
        else:
            build, png, width, height = built
        caption = build.caption.strip()
        if fmt.family == "chart" and build.data and not re.search(r"made up|illustrative|fake", caption, re.IGNORECASE):
            caption = f"{caption} {MADE_UP}".strip()
        state.update(format=fmt.id, build=build.model_dump())
        # The chosen pitch keeps the final words, so a redraw or the ideas board never brings back an older wording.
        chosen, pitches = state.get("chosen"), state.get("concepts", [])
        if isinstance(chosen, int) and 0 <= chosen < len(pitches) and pitches[chosen].get("format") == fmt.id:
            pitches[chosen]["texts"] = [t.model_dump() for t in build.texts if t.text.strip()]
        provider = "vega-lite" if fmt.id == "spurious_correlation" else "claude-meme"
        return MemeResult(png, width, height, provider, json.dumps(state), build.alt, caption)

    async def _ideate(self, post: MemeContext, only: str | None, exclude: list[str], usage: UsageSink | None) -> dict[str, Any]:
        avoid = "\n".join(f"- {p}" for p in exclude)
        recent = ", ".join(post.recent_formats)
        opening = post.position == "opening"
        prompt = render(
            "meme_ideas",
            position_guide=position_guide(post),
            title=post.title,
            joke=post.joke or "(none given)",
            callbacks=post.callbacks or "(none planned)",
            brief=post.brief
            or ("A joke that sets up the problem this post solves." if opening else "A funny, relevant joke that lands the ending."),
            humor=post.humor,
            humor_guide=humor_guide(post.humor),
            formula=f"\n{post.formula}\n" if post.formula else "",
            humor_section=voice_section(post.voice_profile, "Humor") or "(not described: use dry, specific, good-natured humor)",
            # The opener is pitched from the post's beginning; the closer keeps its ending, where callbacks pay off.
            post=clip_post(post.markdown, tail=0) if opening else clip_post(post.markdown),
            menu=menu(only),
            kit=_kit_menu(),
            looks=looks_menu(),
            recent_looks=(
                f"\nThis author's last memes were drawn in these looks: {', '.join(post.recent_looks)}. Suggest other looks.\n"
                if post.recent_looks
                else ""
            ),
            constraint=f"\nOnly use the format `{only}`: all five concepts must use it, each with a different joke.\n" if only else "",
            exclude=f"\nThese premises were already used; pitch different jokes:\n{avoid}\n" if exclude else "",
            taste=f"\n{post.taste}\n" if post.taste else "",
            recent=(
                f"\nThis author's last memes used: {recent}. Readers notice a repeated format, so prefer other formats "
                "unless one of these is clearly the funniest fit.\n"
                if recent and not only
                else ""
            ),
        )
        ideas = await self.llm.structured(
            task="meme ideas",
            system=self.system,
            prompt=prompt,
            schema=MemeIdeas,
            effort=self.settings.effort_meme_ideas,
            max_tokens=16000,
            usage=usage,
        )
        concepts = [c.model_copy(update={"format": only}) for c in ideas.concepts] if only else ideas.concepts
        if not concepts:
            raise ImageProviderError("Claude did not pitch any meme ideas. Click New idea to try again.")
        chosen: int | None = ideas.chosen if 0 <= ideas.chosen < len(concepts) else None
        why = ideas.why
        state: dict[str, Any] = {"version": STATE_VERSION, "brief": post.brief, "tried": []}
        panel = await self._judge(post, concepts, usage)
        if panel is not None:
            usable = [i for i, c in enumerate(concepts) if get_format(c.format)]
            if usable:
                chosen = max(usable, key=lambda i: (panel.totals[i], total(concepts[i])))
            words = None
            fmt = get_format(concepts[chosen].format) if chosen is not None else None
            if chosen is not None and panel.punch_for == chosen and fmt is not None and panel.punch_up:
                words = punched_up(fmt, concepts[chosen], [MemeText(slot=w.slot, text=w.text, speaker="") for w in panel.punch_up])
            if words is not None and chosen is not None:
                concepts[chosen] = concepts[chosen].model_copy(update={"texts": words})
            if chosen is not None and panel.notes[chosen]:
                why = panel.notes[chosen][0].split(": ", 1)[-1]
            state["panel"] = {**panel.summary(), "punched_up": words is not None}
        state.update(concepts=[c.model_dump() for c in concepts], chosen=chosen, why=why)
        return state

    def _pitch_lines(self, concepts: list[MemeConcept]) -> list[str]:
        lines = []
        for c in concepts:
            fmt = get_format(c.format)
            words = " | ".join(f"{t.slot}: {t.text}" for t in c.texts if t.text.strip())
            data = "; ".join(f"{d.label}: {d.value:g}" for d in c.data)
            cast = ", ".join(f"{k.role} = {k.kind}" for k in c.cast if k.kind)
            lines.append(
                f"[{fmt.name if fmt else c.format}] {c.premise}\n   Pays off: {c.callback}\n   Words: {words}"
                + (f"\n   Cast: {cast}" if cast else "")
                + (f"\n   Chart data: {data}" if data else "")
                + (f"\n   Format limits: {', '.join(f'{sl.name} <= {sl.max_chars}' for sl in fmt.slots)}" if fmt else "")
            )
        return lines

    def _context(self, post: MemeContext) -> str:
        opening = post.position == "opening"
        humor = voice_section(post.voice_profile, "Humor") or "(dry, specific, good-natured)"
        return (
            f"{position_guide(post)}\n\nPost title: {post.title}\nHumor level {post.humor}/10: {humor_guide(post.humor)}\n"
            f"The author's sense of humor:\n<humor>\n{humor}\n</humor>\n"
            f"The post:\n<post>\n{clip_post(post.markdown, 9000, 0 if opening else 3000)}\n</post>"
        )

    async def _judge(self, post: MemeContext, concepts: list[MemeConcept], usage: UsageSink | None) -> PanelResult | None:
        """The independent pitch panel (images/panel.py): every seat at once; None when too few seats answered."""
        seats = parse_seats(self.settings.image_panel_meme)
        if not seats:
            return None
        result = await convene(self.llm, seats, context=self._context(post), candidates=self._pitch_lines(concepts), usage=usage)
        if not result.ok:
            log.info("Meme panel: too few seats answered (%d/%d); using the writers' own scores", result.answered, result.asked)
            return None
        return result

    def _direct(
        self,
        fmt: MemeFormat,
        concept: MemeConcept,
        art: ArtDirection,
        look: Look,
        *,
        strict: bool = True,
        sch: Scheme | None = None,
    ) -> Built | None:
        """Draw an art-free format straight from the pitch; None when it has art or the pitch is not ready to draw.

        ``strict`` also turns down a pitch whose words run long (production would tighten them)."""
        if fmt.regions:
            return None
        build = concept_build(fmt, concept)
        blocking, style = validate(fmt, build)
        if blocking or (strict and style):
            return None
        try:
            return (build, *render_build(fmt, build, art.palette, look, sch))
        except ImageProviderError:
            return None

    async def _produce(
        self,
        fmt: MemeFormat,
        concept: MemeConcept,
        title: str,
        art: ArtDirection,
        look: Look,
        *,
        redraw: bool,
        current: dict[str, Any] | None = None,
        usage: UsageSink | None,
        sch: Scheme | None = None,
    ) -> Built | None:
        if current and fmt.staged:
            # A redraw of an edited staged meme keeps its edited words and casting; only the look and colors move.
            try:
                build = MemeBuild.model_validate(current)
                if not build.art:
                    return (build, *render_build(fmt, build, art.palette, look, sch))
            except (ImageProviderError, ValueError):
                pass
        return self._direct(fmt, concept, art, look, sch=sch) or await self._build(
            fmt, concept, title, art, look, redraw=redraw, current=current, usage=usage, sch=sch
        )

    async def _build(
        self,
        fmt: MemeFormat,
        concept: MemeConcept,
        title: str,
        art: ArtDirection,
        look: Look,
        *,
        redraw: bool,
        current: dict[str, Any] | None = None,
        usage: UsageSink | None,
        sch: Scheme | None = None,
    ) -> Built | None:
        concept_text = json.dumps(
            {
                "premise": concept.premise,
                "callback": concept.callback,
                "texts": [t.model_dump() for t in concept.texts],
                "data": [d.model_dump() for d in concept.data],
                "caption": concept.caption,
            },
            indent=1,
        )
        prompt = render(
            "meme_build",
            title=title,
            concept=concept_text,
            spec=build_spec(fmt),
            cast=f"{art.cast} {look.cast}" if art.cast else f"{CAST} {look.cast}",
            look=look_direction(look),
            visual_style=art.visual_style,
            brand=art.brand,
            variation=(
                (variation_for(art, (PALETTE,)) + "\nKeep the joke and the words; only the art changes.")
                if redraw and variation_for(art, (PALETTE,))
                else "This is a redraw: keep the joke and words but give the art a fresh composition and staging."
                if redraw
                else ""
            ),
            image_guidance=art.image_guidance,
        )
        if current:
            prompt += edit_note(art.edits, json.dumps(current, indent=1), what="build")
        return await self._attempts(fmt, prompt, art, look, task=f"meme build ({fmt.id})", usage=usage, sch=sch)

    async def _revise(
        self,
        fmt: MemeFormat,
        current: MemeBuild,
        instruction: str,
        art: ArtDirection,
        look: Look,
        usage: UsageSink | None,
        sch: Scheme | None = None,
    ) -> Built | None:
        """Change a built meme as asked, keeping the rest; None when the change could not be drawn."""
        prompt = render(
            "meme_edit",
            instruction=instruction.strip(),
            spec=build_spec(fmt),
            current=current.model_dump_json(indent=1),
            brand=art.brand,
            look=look_direction(look),
        )
        return await self._attempts(fmt, prompt, art, look, task=f"meme edit ({fmt.id})", usage=usage, sch=sch)

    async def _restage(
        self,
        state: dict[str, Any],
        fmt: MemeFormat,
        current: MemeBuild,
        instruction: str,
        art: ArtDirection,
        usage: UsageSink | None,
    ) -> Built | None:
        """Edit a code-staged meme: Claude changes the words, the casting or the comic panels; the kit redraws it."""
        from inferno_ghostwriter.images.kit import menu as kit_menu
        from inferno_ghostwriter.images.kit.props import menu as props_menu

        snapshot = {
            "texts": [t.model_dump() for t in current.texts],
            "cast": [c.model_dump() for c in current.cast],
            "panels": [p.model_dump() for p in current.panels],
        }
        prompt = render(
            "meme_restage",
            instruction=instruction.strip(),
            spec=build_spec(fmt),
            current=json.dumps(snapshot, indent=1),
            kit=kit_menu() + "\n" + props_menu(),
        )
        try:
            edit = await self.llm.structured(
                task=f"meme edit ({fmt.id})",
                system=self.system,
                prompt=prompt,
                schema=MemeStagingEdit,
                effort=self.settings.effort_images,
                max_tokens=8000,
                usage=usage,
            )
        except LLMError as exc:
            log.info("Meme restage failed: %s", exc)
            return None
        build = current.model_copy(
            update={
                "texts": edit.texts or current.texts,
                "cast": edit.cast or current.cast,
                "panels": edit.panels if fmt.family == "comic" and edit.panels else current.panels,
            }
        )
        build = build.model_copy(update={"alt": alt_text(fmt, build.texts, build.data, build.cast, build.panels)})
        blocking, _ = validate(fmt, build)
        if blocking:
            return None
        look_ = get_look(state.get("look"))
        try:
            return (build, *render_build(fmt, build, art.palette, look_, scheme_of(state, art.palette, look_)))
        except ImageProviderError:
            return None

    async def _attempts(
        self, fmt: MemeFormat, prompt: str, art: ArtDirection, look: Look, *, task: str, usage: UsageSink | None, sch: Scheme | None = None
    ) -> Built | None:
        """Ask for a build and draw it, retrying once with the problems quoted back; None means it could not be drawn."""

        async def ask(note: str) -> MemeBuild:
            return await self.llm.structured(
                task=task,
                system=self.system,
                prompt=prompt + note,
                schema=MemeBuild,
                effort=self.settings.effort_images,
                max_tokens=32000,
                usage=usage,
            )

        def draw(build: MemeBuild, last: bool) -> tuple[bytes, int, int]:
            # Overlong text still renders (it is shrunk to fit), so it only costs a retry, never the meme.
            blocking, style = validate(fmt, build)
            if blocking or (style and not last):
                raise ImageProviderError("\n".join(blocking + style))
            return render_build(fmt, build, art.palette, look, sch)

        try:
            build, (png, width, height) = await draw_with_retry(ask, draw)
        except ImageProviderError as exc:
            log.info("Meme %s could not be drawn: %s", fmt.id, exc)
            return None
        return build, png, width, height
