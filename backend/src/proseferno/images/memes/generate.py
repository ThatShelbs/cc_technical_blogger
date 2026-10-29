"""Two calls make a meme: the writers' room pitches and scores five concepts, then production
draws the winner into its format. Concepts are kept on the image, so "New idea" moves to the
next-best pitch without another ideation call, and "Redraw" draws the same joke again."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from proseferno.config import Settings
from proseferno.images.base import ImageProviderError
from proseferno.images.memes.compose import MASCOT_SCENE, compose
from proseferno.images.memes.formats import CAST, FALLBACK, MemeFormat, build_spec, get_format, menu
from proseferno.images.memes.specs import MemeArt, MemeBuild, MemeConcept, MemeIdeas, MemeText
from proseferno.llm import LLM, SystemBlock
from proseferno.llm.base import UsageSink
from proseferno.prompts import raw, render

log = logging.getLogger(__name__)

STATE_VERSION = 2
POST_LIMIT = 24000
PLACEHOLDER_RE = re.compile(r"\{\{image:[A-Za-z0-9_\-]+\}\}")
MADE_UP = "(data: entirely made up)"

HUMOR_GUIDE = {
    range(0, 3): "Dry and gentle: a wry chart joke, Venn or artifact; one quiet twist, nothing absurd.",
    range(3, 6): "Clever and relatable: one clean twist on something every practitioner has lived through.",
    range(6, 9): "Playful: famous formats, comics and puns are all welcome.",
    range(9, 11): "Go big: absurd escalation, shameless puns, callbacks to the post's running gags.",
}


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


@dataclass
class ArtDirection:
    """How the drawings should look."""

    visual_style: str
    brand: str = ""
    image_guidance: str = ""
    palette: tuple[str, ...] = ()


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


def load_state(spec: str) -> dict[str, Any] | None:
    """The meme's stored concepts and build, or None for older memes (plain SVG + captions)."""
    try:
        state = json.loads(spec) if spec else None
    except json.JSONDecodeError:
        return None
    return state if isinstance(state, dict) and state.get("version") == STATE_VERSION else None


def total(concept: MemeConcept) -> tuple[int, int]:
    s = concept.scores
    return (s.relevance + s.recognizability + s.surprise + s.clarity + s.voice_fit + s.standalone, s.relevance + s.clarity)


def pick(concepts: list[MemeConcept], preferred: int | None, skip: set[int]) -> int | None:
    """The preferred concept if usable, else the best-scoring untried concept with a known format."""
    usable = [i for i, c in enumerate(concepts) if i not in skip and get_format(c.format)]
    if preferred in usable:
        return preferred
    return max(usable, key=lambda i: total(concepts[i]), default=None)


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


def render_build(fmt: MemeFormat, build: MemeBuild, palette: tuple[str, ...] = ()) -> tuple[bytes, int, int]:
    return compose(
        fmt, {t.slot: t for t in build.texts}, {a.region: a.svg for a in build.art}, build.cast_defs, build.data, palette=palette
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
        alt="The Proseferno robot with the captions: " + " / ".join(w for w in (top, bottom) if w),
        caption=concept.premise if concept else "",
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
        usage: UsageSink | None = None,
    ) -> MemeResult:
        state = load_state(spec)
        index: int | None = None
        if state is not None and state.get("brief") == post.brief and not meme_format and (redraw or rethink):
            concepts = [MemeConcept.model_validate(c) for c in state["concepts"]]
            index = pick(concepts, None, set(state.get("tried", []))) if rethink else pick(concepts, state.get("chosen"), set())
            if index is None:
                # Every pitch has been used: ask the room for fresh ones that avoid them.
                state = await self._ideate(post, None, [c.premise for c in concepts], usage)
        else:
            state = await self._ideate(post, meme_format, [], usage)

        concepts = [MemeConcept.model_validate(c) for c in state["concepts"]]
        if index is None:
            index = pick(concepts, state.get("chosen"), set())
        concept = concepts[index] if index is not None else None
        state["chosen"] = index
        state["tried"] = sorted({*state.get("tried", []), *([index] if index is not None else [])})

        fmt = (get_format(concept.format) if concept else None) or FALLBACK
        built = await self._build(fmt, concept, post.title, art, redraw=redraw, usage=usage) if concept else None
        return self._finish(state, fmt, concept, built, art)

    async def edit(self, spec: str, instruction: str, art: ArtDirection, *, usage: UsageSink | None = None) -> MemeResult:
        """Change the current meme as the author asks ("make the robot look more smug"), keeping the rest."""
        state = load_state(spec)
        if state is None or not state.get("build"):
            raise ImageProviderError("This meme was made by an older version; click New idea to make one that can be edited.")
        fmt = get_format(str(state.get("format", ""))) or FALLBACK
        current = MemeBuild.model_validate(state["build"])
        prompt = render(
            "meme_edit",
            instruction=instruction.strip(),
            spec=build_spec(fmt),
            current=current.model_dump_json(indent=1),
            brand=art.brand,
        )
        built = await self._attempts(fmt, prompt, art, task=f"meme edit ({fmt.id})", usage=usage)
        if built is None:
            raise ImageProviderError("Claude's edit could not be drawn. Try rewording the instruction.")
        return self._finish(state, fmt, None, built, art)

    def _finish(
        self,
        state: dict[str, Any],
        fmt: MemeFormat,
        concept: MemeConcept | None,
        built: tuple[MemeBuild, bytes, int, int] | None,
        art: ArtDirection,
    ) -> MemeResult:
        if built is None:
            fmt = FALLBACK
            build = fallback_build(concept)
            png, width, height = render_build(fmt, build)
        else:
            build, png, width, height = built
        caption = build.caption.strip()
        if fmt.family == "chart" and build.data and not re.search(r"made up|illustrative|fake", caption, re.IGNORECASE):
            caption = f"{caption} {MADE_UP}".strip()
        state.update(format=fmt.id, build=build.model_dump())
        provider = "vega-lite" if fmt.id == "spurious_correlation" else "claude-meme"
        return MemeResult(png, width, height, provider, json.dumps(state), build.alt, caption)

    async def _ideate(self, post: MemeContext, only: str | None, exclude: list[str], usage: UsageSink | None) -> dict[str, Any]:
        avoid = "\n".join(f"- {p}" for p in exclude)
        prompt = render(
            "meme_ideas",
            title=post.title,
            joke=post.joke or "(none given)",
            callbacks=post.callbacks or "(none planned)",
            brief=post.brief or "A funny, relevant joke that lands the ending.",
            humor=post.humor,
            humor_guide=humor_guide(post.humor),
            humor_section=voice_section(post.voice_profile, "Humor") or "(not described: use dry, specific, good-natured humor)",
            post=PLACEHOLDER_RE.sub("", post.markdown).strip()[:POST_LIMIT],
            menu=menu(only),
            constraint=f"\nOnly use the format `{only}`: all five concepts must use it, each with a different joke.\n" if only else "",
            exclude=f"\nThese premises were already used; pitch different jokes:\n{avoid}\n" if exclude else "",
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
        return {
            "version": STATE_VERSION,
            "brief": post.brief,
            "concepts": [c.model_dump() for c in concepts],
            "chosen": ideas.chosen if 0 <= ideas.chosen < len(concepts) else None,
            "why": ideas.why,
            "tried": [],
        }

    async def _build(
        self, fmt: MemeFormat, concept: MemeConcept, title: str, art: ArtDirection, *, redraw: bool, usage: UsageSink | None
    ) -> tuple[MemeBuild, bytes, int, int] | None:
        concept_text = json.dumps(
            {"premise": concept.premise, "callback": concept.callback, "texts": [t.model_dump() for t in concept.texts]}, indent=1
        )
        prompt = render(
            "meme_build",
            title=title,
            concept=concept_text,
            spec=build_spec(fmt),
            cast=CAST,
            visual_style=art.visual_style,
            brand=art.brand,
            variation="This is a redraw: keep the joke and words but give the art a fresh composition and staging." if redraw else "",
            image_guidance=art.image_guidance,
        )
        return await self._attempts(fmt, prompt, art, task=f"meme build ({fmt.id})", usage=usage)

    async def _attempts(
        self, fmt: MemeFormat, prompt: str, art: ArtDirection, *, task: str, usage: UsageSink | None
    ) -> tuple[MemeBuild, bytes, int, int] | None:
        """Ask for a build and draw it, retrying once with the problems quoted back; None means it could not be drawn."""
        errors = ""
        for attempt in range(2):
            build = await self.llm.structured(
                task=task,
                system=self.system,
                prompt=prompt + errors,
                schema=MemeBuild,
                effort=self.settings.effort_images,
                max_tokens=32000,
                usage=usage,
            )
            blocking, style = validate(fmt, build)
            problems = blocking + style
            if not blocking and (not style or attempt == 1):
                try:
                    png, width, height = render_build(fmt, build, art.palette)
                    return build, png, width, height
                except ImageProviderError as exc:
                    problems = [str(exc)]
            log.info("Meme %s needs another pass: %s", fmt.id, problems)
            errors = "\n\nYour previous attempt had these problems; fix every one:\n" + "\n".join(f"- {p}" for p in problems) + "\n"
        return None
