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
    MemeArt,
    MemeBuild,
    MemeConcept,
    MemeDatum,
    MemeIdeas,
    MemeReview,
    MemeText,
    MemeVerdict,
)
from inferno_ghostwriter.images.remix import PALETTE, ImprovementPlan, Tweak, variation_for
from inferno_ghostwriter.llm import LLM, LLMError, SystemBlock
from inferno_ghostwriter.llm.base import LLMImagesUnsupportedError, UsageSink
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


@dataclass
class MemeResult:
    png: bytes
    width: int
    height: int
    provider: str
    spec: str
    alt: str
    caption: str


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


def panel_total(judge: Any) -> int:
    """One panel score; a joke a cold reader does not get is ruled out (pushed far below the rest)."""
    score = judge.feed_reader + judge.comedy_editor + judge.author + judge.gets_it
    return score - 100 if judge.gets_it < 5 else score


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


def render_build(fmt: MemeFormat, build: MemeBuild, palette: tuple[str, ...] = (), look: Look | None = None) -> tuple[bytes, int, int]:
    theme = themed(look, palette) if look else None
    return compose(
        fmt,
        {t.slot: t for t in build.texts},
        {a.region: a.svg for a in build.art},
        build.cast_defs,
        build.data,
        palette=palette,
        theme=theme,
    )


def look_direction(look: Look) -> str:
    """The look as the build prompt reads it: how to draw, and the palette to draw in."""
    return (
        f"Look for this meme: **{look.label}**. {look.art}\n"
        f"Palette for the drawings, dark to light (unless a brand palette is given): {' '.join(look.palette)}."
    )


def review_score(review: MemeReview) -> int:
    return review.funny + review.craft + (5 if review.passes else 0)


def review_entry(review: MemeReview, verdict: str) -> dict[str, Any]:
    return {"verdict": verdict, "funny": review.funny, "craft": review.craft, "problems": review.problems[:5]}


def alt_text(fmt: MemeFormat, texts: list[MemeText], data: list[MemeDatum]) -> str:
    """Alt text written from the meme's own parts, so it is always right: the format and every word in it."""
    words = " / ".join(t.text.strip() for t in texts if t.text.strip())
    chart = "; ".join(f"{d.label}: {d.value:g}" for d in data)
    return f"{fmt.name} meme. Text: {words}." + (f" Data: {chart}." if chart else "")


def concept_build(fmt: MemeFormat, concept: MemeConcept) -> MemeBuild:
    """A format with no art needs no production call: the pitch already has its words, data and caption."""
    return MemeBuild(
        texts=concept.texts,
        cast_defs="",
        art=[],
        data=concept.data,
        alt=alt_text(fmt, concept.texts, concept.data),
        caption=concept.caption,
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
        chosen_look = choose_look(look, concept.look if concept else None, post.recent_looks, avoid=avoid)
        state["look"] = chosen_look.id
        state.pop("review", None)
        built = await self._produce(fmt, concept, post.title, art, chosen_look, redraw=redraw, usage=usage) if concept else None
        if built is None and concept is not None:
            # The format could not be drawn. Another pitch in a format with no art (it cannot fail) keeps a whole
            # joke; squeezing this one into a caption meme is the last resort.
            state["fallback_from"] = fmt.id
            for other in sorted((i for i in range(len(concepts)) if i != index), key=lambda i: total(concepts[i]), reverse=True):
                other_fmt = get_format(concepts[other].format)
                direct = self._direct(other_fmt, concepts[other], art, chosen_look, strict=False) if other_fmt else None
                if direct is not None and other_fmt is not None:
                    index, concept, fmt, built = other, concepts[other], other_fmt, direct
                    tried.add(other)
                    break
        state["chosen"] = index
        state["tried"] = sorted(tried)
        if built is not None and fmt.regions and review and self.settings.meme_review:
            premise = concept.premise if concept else ""
            built = await self._look_over(state, fmt, built, art, chosen_look, post.title, premise, usage)
        return self._finish(state, fmt, concept, built, art)

    async def edit(self, spec: str, instruction: str, art: ArtDirection, *, usage: UsageSink | None = None) -> MemeResult:
        """Change the current meme as the author asks ("make the ghost look more smug"), keeping the rest."""
        state = load_state(spec)
        if state is None or not state.get("build"):
            raise ImageProviderError(OLD_MEME)
        fmt = get_format(str(state.get("format", ""))) or FALLBACK
        built = await self._revise(fmt, MemeBuild.model_validate(state["build"]), instruction, art, get_look(state.get("look")), usage)
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
        build = current.model_copy(update={"texts": texts, "alt": alt_text(fmt, texts, current.data)})
        blocking, _ = validate(fmt, build)
        if blocking:
            raise ImageProviderError(" ".join(blocking))
        png, width, height = render_build(fmt, build, art.palette, get_look(state.get("look")))
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
            png, width, height = render_build(fmt, build, art.palette, get_look(state.get("look")))
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
            looks=looks_menu(),
            recent_looks=(
                f"\nThis author's last memes were drawn in these looks: {', '.join(post.recent_looks)}. Suggest other looks.\n"
                if post.recent_looks
                else ""
            ),
            constraint=f"\nOnly use the format `{only}`: all five concepts must use it, each with a different joke.\n" if only else "",
            exclude=f"\nThese premises were already used; pitch different jokes:\n{avoid}\n" if exclude else "",
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
        verdict = await self._judge(post, concepts, usage)
        by_concept = {j.concept: j for j in verdict.scores if 0 <= j.concept < len(concepts)} if verdict is not None else {}
        if verdict is not None and len(by_concept) == len(concepts):
            panel = [panel_total(by_concept[i]) for i in range(len(concepts))]
            usable = [i for i, c in enumerate(concepts) if get_format(c.format)]
            if 0 <= verdict.chosen < len(concepts) and panel[verdict.chosen] >= 0 and verdict.chosen in usable:
                chosen = verdict.chosen
            elif usable:
                chosen = max(usable, key=lambda i: (panel[i], total(concepts[i])))
            words = None
            fmt = get_format(concepts[chosen].format) if chosen is not None else None
            if chosen is not None and chosen == verdict.chosen and fmt is not None and verdict.punch_up:
                words = punched_up(fmt, concepts[chosen], verdict.punch_up)
            if words is not None and chosen is not None:
                concepts[chosen] = concepts[chosen].model_copy(update={"texts": words})
            why = verdict.summary or why
            state["panel"] = {
                "scores": panel,
                "notes": [by_concept[i].note for i in range(len(concepts))],
                "punched_up": words is not None,
            }
        state.update(concepts=[c.model_dump() for c in concepts], chosen=chosen, why=why)
        return state

    async def _judge(self, post: MemeContext, concepts: list[MemeConcept], usage: UsageSink | None) -> MemeVerdict | None:
        """An independent panel scores the pitches (the writers do not grade their own jokes); None if the call fails."""
        lines = []
        for i, c in enumerate(concepts):
            fmt = get_format(c.format)
            words = " | ".join(f"{t.slot}: {t.text}" for t in c.texts if t.text.strip())
            data = "; ".join(f"{d.label}: {d.value:g}" for d in c.data)
            lines.append(
                f"{i}. [{fmt.name if fmt else c.format}] {c.premise}\n   Pays off: {c.callback}\n   Words: {words}"
                + (f"\n   Chart data: {data}" if data else "")
            )
        opening = post.position == "opening"
        try:
            return await self.llm.structured(
                task="meme panel",
                system=self.system,
                prompt=render(
                    "meme_verdict",
                    position_guide=position_guide(post),
                    title=post.title,
                    humor=post.humor,
                    humor_guide=humor_guide(post.humor),
                    humor_section=voice_section(post.voice_profile, "Humor") or "(not described: dry, specific, good-natured humor)",
                    post=clip_post(post.markdown, 12000, 0 if opening else 4000),
                    concepts="\n".join(lines),
                ),
                schema=MemeVerdict,
                effort=self.settings.effort_meme_verdict,
                max_tokens=8000,
                usage=usage,
            )
        except LLMError as exc:
            log.info("Meme panel failed, using the writers own scores: %s", exc)
            return None

    def _direct(self, fmt: MemeFormat, concept: MemeConcept, art: ArtDirection, look: Look, *, strict: bool = True) -> Built | None:
        """Draw an art-free format straight from the pitch; None when it has art or the pitch is not ready to draw.

        ``strict`` also turns down a pitch whose words run long (production would tighten them)."""
        if fmt.regions:
            return None
        build = concept_build(fmt, concept)
        blocking, style = validate(fmt, build)
        if blocking or (strict and style):
            return None
        try:
            return (build, *render_build(fmt, build, art.palette, look))
        except ImageProviderError:
            return None

    async def _produce(
        self, fmt: MemeFormat, concept: MemeConcept, title: str, art: ArtDirection, look: Look, *, redraw: bool, usage: UsageSink | None
    ) -> Built | None:
        return self._direct(fmt, concept, art, look) or await self._build(fmt, concept, title, art, look, redraw=redraw, usage=usage)

    async def _build(
        self, fmt: MemeFormat, concept: MemeConcept, title: str, art: ArtDirection, look: Look, *, redraw: bool, usage: UsageSink | None
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
        return await self._attempts(fmt, prompt, art, look, task=f"meme build ({fmt.id})", usage=usage)

    async def _revise(
        self, fmt: MemeFormat, current: MemeBuild, instruction: str, art: ArtDirection, look: Look, usage: UsageSink | None
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
        return await self._attempts(fmt, prompt, art, look, task=f"meme edit ({fmt.id})", usage=usage)

    async def _review(
        self, built: Built, fmt: MemeFormat, look: Look, title: str, premise: str, usage: UsageSink | None
    ) -> MemeReview | None:
        """Claude's look at the drawn meme; None when this connection cannot show it an image (or the call fails)."""
        try:
            return await self.llm.structured(
                task="meme review",
                system=self.system,
                prompt=render(
                    "meme_review",
                    title=title,
                    format=fmt.name,
                    recognizable=fmt.recognizable,
                    look=f"{look.label}: {look.art}",
                    premise=premise or "(the joke is in the words)",
                    words=built[0].alt,
                ),
                schema=MemeReview,
                effort=self.settings.effort_meme_review,
                max_tokens=4000,
                usage=usage,
                images=[thumbnail_png(built[1])],
            )
        except LLMImagesUnsupportedError:
            return None
        except LLMError as exc:
            log.info("Meme review failed: %s", exc)
            return None

    async def _look_over(
        self,
        state: dict[str, Any],
        fmt: MemeFormat,
        built: Built,
        art: ArtDirection,
        look: Look,
        title: str,
        premise: str,
        usage: UsageSink | None,
    ) -> Built:
        """Review the drawn meme; one that reads badly gets one redraw with the reviewer's fix, and the better one is kept."""
        first = await self._review(built, fmt, look, title, premise, usage)
        if first is None:
            state["review"] = {"skipped": True, "note": "This connection cannot show Claude the image, so it was not reviewed."}
            return built
        if first.passes:
            state["review"] = review_entry(first, "passed")
            return built
        try:
            again = await self._revise(fmt, built[0], first.fix or "; ".join(first.problems), art, look, usage)
        except LLMError:
            again = None
        second = await self._review(again, fmt, look, title, premise, usage) if again else None
        if again is not None and (second is None or review_score(second) >= review_score(first)):
            state["review"] = review_entry(second, "redrawn") if second else {"verdict": "redrawn", "problems": first.problems[:5]}
            return again
        state["review"] = review_entry(first, "kept")
        return built

    async def _attempts(
        self, fmt: MemeFormat, prompt: str, art: ArtDirection, look: Look, *, task: str, usage: UsageSink | None
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
            return render_build(fmt, build, art.palette, look)

        try:
            build, (png, width, height) = await draw_with_retry(ask, draw)
        except ImageProviderError as exc:
            log.info("Meme %s could not be drawn: %s", fmt.id, exc)
            return None
        return build, png, width, height
