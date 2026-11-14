"""The opening room: pitch concepts across styles, let an independent panel judge them, then build the winner.

1. **Pitch** (``OpeningIdeas``): six concepts across the styles that suit the post (four in one style when the author
   chose it). On Auto at least two are open visual metaphors and one is data art, so imaginative ideas always compete.
2. **Panel** (``OpeningVerdict``): a separate call scores every concept as four judges (scroller, art director, fact
   checker, author). Code adds the scores; a fact checker or author score under 5 rules a concept out.
3. **Research** (data styles only): the winning claim's numbers are looked up with web search.
4. **Build**: Claude-drawn SVG (metaphor, data art, receipt), a code template (cheat sheet, versus, big number,
   framework, chart) or the meme room. Every number a data opener prints must pass ``facts.check``.
5. **Review** (``RenderReview``): Claude looks at the finished PNG; a failure gets one redraw with its fix, and the
   better of the two is kept. Connections that cannot show Claude an image skip this step.

A concept that cannot be built (no verifiable data, a drawing that fails twice) gives way to the next best one; the
last resort is a visual metaphor. Pitches and verdicts are kept on the image, so "New idea" and the ideas board move
between them with no new pitching or judging call.
"""

from __future__ import annotations

import io
import json
import logging
from dataclasses import dataclass, field, replace
from typing import Any

from PIL import Image

from proseferno.config import Settings
from proseferno.images.base import ImageProviderError, draw_with_retry
from proseferno.images.memes import ArtDirection, MemeContext, MemeMaker, MemeResult
from proseferno.images.memes.generate import clip_post
from proseferno.images.memes.generate import load_state as load_meme_state
from proseferno.images.opening import facts, templates
from proseferno.images.opening.specs import (
    OpeningBuild,
    OpeningConcept,
    OpeningIdeas,
    OpeningVerdict,
    RenderReview,
)
from proseferno.images.opening.styles import AUTO, BY_ID, FALLBACK, STYLES, OpeningStyle, get_style
from proseferno.images.render import svg_to_png
from proseferno.images.specs import SvgSpec
from proseferno.llm import LLM, LLMError, SystemBlock
from proseferno.llm.base import Citation, LLMImagesUnsupportedError, LLMRefusalError, ResearchResult, UsageSink
from proseferno.prompts import raw, render

log = logging.getLogger(__name__)

STATE_VERSION = 1
AUTO_COUNT = 6
FIXED_COUNT = 4
# A judge score under this rules a concept out (fact checker and author only: a dull idea can still be true).
VETO = 5
# Concepts tried before falling back to a visual metaphor drawn from scratch.
MAX_BUILDS = 3
POST_LIMIT = 16000
JUDGES = ("scroller", "art_director", "fact_checker", "author")
NOT_AN_OPENING = "This image was made before opening styles existed; click New idea to pitch openings for it."

SVG_RULES = {
    "editorial": (
        "An imaginative editorial illustration that acts out the post's central mechanism as one physical scene. Make the "
        "metaphor specific to this post; up to four short labels (one or two words each, from the post) are allowed only "
        "where they make the metaphor click, such as the buckets of a plinko board. No headline or title text."
    ),
    "data_art": (
        "Abstract, beautiful data art: network graphs, streams of coloured particles sorting into lanes, flowing lines, "
        "candlestick or line motifs, scatter clouds. It must encode the post's idea in its structure (what sorts into what, "
        "which node matters, what flows where), with the focal element in the warm colours. No text, no numbers, no axis "
        "values, nothing that reads as a real measurement."
    ),
    "receipt": (
        "An oversized, crisp mock of the one screen that proves the post's point: a code editor, a terminal, a prompt and "
        "its answer, a diff. Show 3-8 lines of the real content from the post at 34px or more (monospace "
        "'Consolas, Menlo, monospace' for code), realistic window chrome, and one highlighted line or result that is the "
        "hook. Fewer, bigger lines beat a full screen. No real product logos or brand marks."
    ),
}


@dataclass
class OpeningContext:
    """What the room knows about the post."""

    title: str
    markdown: str
    voice_profile: str
    # The planner's brief for this image (the hero slot's prompt); a changed brief means fresh pitches.
    brief: str
    # The author's own description of the post.
    post_brief: str = ""
    hook: str = ""
    titles: tuple[str, ...] = ()
    humor: int = 5
    # The chosen style id, or "auto"; ``eligible`` are the styles Auto may pitch, ``suggested`` the best fits first.
    style: str = AUTO
    note: str = ""
    suggested: tuple[str, ...] = ()
    eligible: tuple[str, ...] = ()
    # The post's formula, as one line for the room ("" when none is in force).
    formula: str = ""
    # Styles this author's last opening images used, newest first.
    recent_styles: tuple[str, ...] = ()
    # Builds the opening meme's context (the image service knows the plan, callbacks and recent formats).
    meme_context: MemeContext | None = None


@dataclass
class OpeningResult:
    png: bytes
    width: int
    height: int
    provider: str
    spec: str
    alt: str
    caption: str


@dataclass
class _Built:
    png: bytes
    width: int
    height: int
    provider: str
    alt: str
    caption: str
    state: dict[str, Any] = field(default_factory=dict)


def load_state(spec: str) -> dict[str, Any] | None:
    """The opening image's stored pitches, verdict and build; None for an older hero (a plain SVG)."""
    try:
        state = json.loads(spec) if spec else None
    except json.JSONDecodeError:
        return None
    return state if isinstance(state, dict) and state.get("room") == "opening" and state.get("version") == STATE_VERSION else None


def opening_meme_spec(spec: str) -> str | None:
    """The meme state inside an opening meme (so the meme tools work on it), else None."""
    state = load_state(spec)
    if state and state.get("style") == "meme" and load_meme_state(str(state.get("meme") or "")):
        return str(state["meme"])
    return None


def load_concepts(state: dict[str, Any]) -> list[OpeningConcept]:
    return [OpeningConcept.model_validate({"template": "", "content": "", "data_claim": "", **c}) for c in state.get("concepts", [])]


def total(entry: dict[str, Any]) -> tuple[int, int]:
    panel = entry.get("panel") or {}
    return sum(int(panel.get(j, 0)) for j in JUDGES), int(panel.get("scroller", 0))


def ruled_out(entry: dict[str, Any]) -> bool:
    panel = entry.get("panel") or {}
    return bool(panel) and (int(panel.get("fact_checker", 10)) < VETO or int(panel.get("author", 10)) < VETO)


def ranking(state: dict[str, Any], skip: set[int] | None = None) -> list[int]:
    """Concept indexes best first: usable ones by panel total, ruled-out ones last."""
    entries = state.get("concepts", [])
    usable = [i for i, c in enumerate(entries) if i not in (skip or set()) and get_style(c.get("style"))]
    return sorted(usable, key=lambda i: (not ruled_out(entries[i]), *total(entries[i])), reverse=True)


def fit_of(state: dict[str, Any] | None) -> str:
    style = get_style((state or {}).get("style"))
    return style.thumbnail_fit if style else "cover"


def sources_of(state: dict[str, Any] | None) -> list[dict[str, str]]:
    build = (state or {}).get("build") or {}
    return [{"title": str(s.get("title", "")), "url": str(s.get("url", ""))} for s in build.get("sources") or [] if s.get("title")]


def _style_menu(ids: list[str]) -> str:
    lines = []
    for style_id in ids:
        s = BY_ID[style_id]
        lines.append(f"- `{s.id}` ({s.label}): {s.when_to_use}")
    return "\n".join(lines)


def _concept_text(concept: OpeningConcept) -> str:
    parts = [
        f"Style: {BY_ID[concept.style].label}" if concept.style in BY_ID else "",
        f"Hook: {concept.hook}",
        f"Picture: {concept.concept}",
    ]
    if concept.content:
        parts.append(f"Content: {concept.content}")
    if concept.data_claim:
        parts.append(f"Data claim: {concept.data_claim}")
    return "\n".join(p for p in parts if p)


def _png_aspect_ok(width: int, height: int) -> bool:
    return abs(width / max(1, height) - 16 / 9) < 0.03


class OpeningRoom:
    def __init__(self, llm: LLM, settings: Settings, memes: MemeMaker) -> None:
        self.llm = llm
        self.settings = settings
        self.memes = memes
        self.system = [SystemBlock(raw("opening_system"), cache=True)]

    # -- public ------------------------------------------------------------------------

    async def make(
        self,
        spec: str,
        ctx: OpeningContext,
        art: ArtDirection,
        *,
        redraw: bool = False,
        rethink: bool = False,
        style: str | None = None,
        concept_index: int | None = None,
        usage: UsageSink | None = None,
    ) -> OpeningResult:
        """Make the opening image. ``style`` re-pitches in one style; ``concept_index`` builds that stored pitch."""
        state = load_state(spec)
        index: int | None = None
        if concept_index is not None:
            if state is None or not 0 <= concept_index < len(state.get("concepts", [])):
                raise ImageProviderError("That idea is no longer available. Click New idea for fresh pitches.")
            index = concept_index
        elif state is not None and state.get("brief") == ctx.brief and not style and (redraw or rethink):
            tried = set(state.get("tried", []))
            order = ranking(state, tried) if rethink else [state["chosen"]] if isinstance(state.get("chosen"), int) else ranking(state)
            index = order[0] if order else None
            if index is None:
                # Every pitch has been used: pitch fresh ones that avoid them.
                state = await self._pitch(ctx, None, [c.concept for c in load_concepts(state)], usage)
        else:
            state = await self._pitch(ctx, style if style in BY_ID else None, [], usage)
        assert state is not None

        order = ranking(state)
        if index is not None:
            order = [index, *(i for i in order if i != index)]
        tried = set(state.get("tried", []))
        state.pop("fallback_from", None)
        first_style = state["concepts"][order[0]]["style"] if order else FALLBACK
        built: _Built | None = None
        for attempt, i in enumerate(order[:MAX_BUILDS]):
            concept = load_concepts(state)[i]
            tried.add(i)
            built = await self._build(concept, state, ctx, art, redraw=redraw and attempt == 0, usage=usage)
            if built is not None:
                state["chosen"] = i
                break
        if built is None:
            # Nothing pitched could be built: a visual metaphor of the post's idea always can be.
            concept = OpeningConcept(
                style=FALLBACK,
                template="",
                hook="The post's central idea at a glance.",
                concept=f"An imaginative visual metaphor for: {ctx.title}. {ctx.hook}",
                content="",
                data_claim="",
            )
            built = await self._build(concept, state, ctx, art, redraw=False, usage=usage)
            if built is None:
                raise ImageProviderError("The opening image could not be drawn. Click Redraw to try again.")
            state["chosen"] = None
        if built.state.get("style", FALLBACK) != first_style:
            state["fallback_from"] = first_style
        state["tried"] = sorted(tried)
        return await self._finish(state, built, ctx, art, usage)

    async def edit(
        self, spec: str, instruction: str, ctx: OpeningContext, art: ArtDirection, *, usage: UsageSink | None = None
    ) -> OpeningResult:
        """Change the current opening image as the author asks, keeping the rest."""
        state = load_state(spec)
        if state is None or not state.get("style"):
            raise ImageProviderError(NOT_AN_OPENING)
        style = BY_ID.get(state["style"]) or BY_ID[FALLBACK]
        note = (
            "\nThe author asked for this change; keep everything else exactly as it is:\n"
            f"<instruction>\n{instruction.strip()}\n</instruction>\n"
        )
        if style.builder == "meme":
            meme = await self.memes.edit(str(state.get("meme") or ""), instruction, art, usage=usage)
            return self._from_meme(state, meme)
        concept = self._chosen_concept(state)
        if style.builder == "svg":
            note += f"\nThe current SVG to edit:\n<current>\n{state.get('svg', '')}\n</current>\n"
        else:
            note += f"\nThe current build to edit:\n<current>\n{json.dumps(state.get('build') or {}, indent=1)}\n</current>\n"
        built = await self._build(concept, state, ctx, art, redraw=False, usage=usage, fix=note, keep_research=True)
        if built is None:
            raise ImageProviderError("Claude's edit could not be drawn. Try rewording the instruction.")
        return await self._finish(state, built, ctx, art, usage, review=False)

    def reword(self, spec: str, words: dict[str, str], art: ArtDirection) -> OpeningResult:
        """Retype the words of a code-drawn opening image and draw it again. No model call; numbers stay as they are."""
        state = load_state(spec)
        if state is None or not state.get("build"):
            raise ImageProviderError("Only cheat sheets, versus splits, big numbers, frameworks and charts have words to retype.")
        template = templates.get_template(str(state.get("template", "")))
        if template is None:
            raise ImageProviderError("This opening image has no words to retype.")
        build = templates.apply_words(OpeningBuild.model_validate(state["build"]), words)
        if BY_ID[template.style].needs_data:
            research = state.get("research") or {}
            problems = facts.check(
                build,
                research=str(research.get("text", "")),
                citations=[Citation(**c) for c in research.get("citations", [])],
                post=str(state.get("post_numbers", "")),
                steps=template.id == "waterfall",
                percent=build.unit.strip() == "%",
            )
            if problems:
                raise ImageProviderError("New words cannot add numbers that were not researched: " + " ".join(problems[:2]))
        png, width, height = templates.draw(template, build, art.palette)
        state["build"] = build.model_dump()
        caption = self._caption(build.caption, build)
        return OpeningResult(png, width, height, "claude-opening", json.dumps(state), build.alt, caption)

    def with_meme(self, spec: str, meme: MemeResult) -> OpeningResult:
        """Store a changed opening meme (retyped words, another pitch) back into the opening state."""
        state = load_state(spec)
        if state is None:
            raise ImageProviderError(NOT_AN_OPENING)
        return self._from_meme(state, meme)

    # -- pitching and judging --------------------------------------------------------------

    def _styles_for(self, ctx: OpeningContext, only: str | None) -> list[str]:
        if only:
            return [only]
        if ctx.style in BY_ID:
            return [ctx.style]
        allowed = [s for s in (ctx.eligible or tuple(s.id for s in STYLES)) if s in BY_ID and ctx.humor >= BY_ID[s].min_humor]
        return allowed or [FALLBACK]

    async def _pitch(self, ctx: OpeningContext, only: str | None, exclude: list[str], usage: UsageSink | None) -> dict[str, Any]:
        styles = self._styles_for(ctx, only)
        fixed = len(styles) == 1
        count = FIXED_COUNT if fixed else AUTO_COUNT
        suggested = [s for s in ctx.suggested if s in styles]
        mix_rule = (
            f"\nAll {count} concepts use the style `{styles[0]}`, each a different idea.\n"
            if fixed
            else (
                f"\nMix: at least two concepts are open visual metaphors (`editorial`) and at least one is `data_art`; the rest "
                f"use other styles, best fits for this post first: {', '.join(f'`{s}`' for s in suggested) or 'any'}.\n"
            )
        )
        recent = ", ".join(BY_ID[s].label for s in ctx.recent_styles if s in BY_ID)
        prompt = render(
            "opening_ideas",
            title=ctx.title,
            titles=("Other titles the author is considering: " + "; ".join(ctx.titles) + "\n") if ctx.titles else "",
            hook=ctx.hook or "(not planned)",
            image_brief=ctx.brief or "(none)",
            brief=ctx.post_brief.strip() or "(see the post)",
            humor=ctx.humor,
            formula=f"{ctx.formula}\n" if ctx.formula else "",
            note=f"The author's direction for this image: {ctx.note}\n" if ctx.note else "",
            styles=_style_menu(styles),
            templates=templates.menu(styles) or "(none of the chosen styles uses a template)",
            mix_rule=mix_rule,
            recent=(
                f"\nThis author's last opening images were: {recent}. Vary the look unless one of these is clearly best.\n"
                if recent and not fixed
                else ""
            ),
            exclude=("\nThese ideas were already used; pitch different ones:\n" + "\n".join(f"- {e}" for e in exclude) + "\n")
            if exclude
            else "",
            post=clip_post(ctx.markdown, POST_LIMIT, tail=0),
            count=count,
        )

        async def ask(note: str) -> OpeningIdeas:
            return await self.llm.structured(
                task="opening ideas",
                system=self.system,
                prompt=prompt + note,
                schema=OpeningIdeas,
                effort=self.settings.effort_opening_ideas,
                max_tokens=16000,
                usage=usage,
            )

        ideas = await ask("")
        concepts = self._clean(ideas.concepts, styles, fixed)
        problems = self._mix_problems(concepts, fixed, count)
        if problems:
            # One more pitch with the gaps quoted back; a second miss is accepted rather than failing the image.
            retry = self._clean(
                (
                    await ask("\n\nYour previous pitch had these problems; fix every one:\n" + "\n".join(f"- {p}" for p in problems))
                ).concepts,
                styles,
                fixed,
            )
            if len(self._mix_problems(retry, fixed, count)) < len(problems):
                concepts = retry
        if not concepts:
            raise ImageProviderError("Claude did not pitch any opening ideas. Click New idea to try again.")
        entries = [c.model_dump() for c in concepts]
        summary = await self._judge(ctx, concepts, entries, usage)
        return {
            "version": STATE_VERSION,
            "room": "opening",
            "brief": ctx.brief,
            "mode": styles[0] if fixed else AUTO,
            "concepts": entries,
            "summary": summary,
            "chosen": None,
            "tried": [],
        }

    @staticmethod
    def _clean(concepts: list[OpeningConcept], styles: list[str], fixed: bool) -> list[OpeningConcept]:
        """Force a fixed style, drop styles not allowed, and give code-drawn styles a template they have."""
        out = []
        for concept in concepts:
            style_id = styles[0] if fixed else concept.style
            style = BY_ID.get(style_id)
            if style is None or style_id not in styles:
                continue
            template = concept.template if concept.template in style.templates else (style.templates[0] if style.templates else "")
            out.append(concept.model_copy(update={"style": style_id, "template": template}))
        return out

    @staticmethod
    def _mix_problems(concepts: list[OpeningConcept], fixed: bool, count: int) -> list[str]:
        problems = []
        if len(concepts) < count:
            problems.append(f"Pitch {count} usable concepts (you gave {len(concepts)}).")
        if not fixed:
            if sum(c.style == "editorial" for c in concepts) < 2:
                problems.append("Include at least two open visual metaphors (`editorial`).")
            if not any(c.style == "data_art" for c in concepts):
                problems.append("Include at least one `data_art` concept.")
        return problems

    async def _judge(
        self, ctx: OpeningContext, concepts: list[OpeningConcept], entries: list[dict[str, Any]], usage: UsageSink | None
    ) -> str:
        listing = "\n\n".join(f"Concept {i}:\n{_concept_text(c)}" for i, c in enumerate(concepts))
        prompt = render(
            "opening_judge",
            title=ctx.title,
            hook=ctx.hook or "(not planned)",
            humor=ctx.humor,
            note=f"The author asked: {ctx.note}" if ctx.note else "",
            concepts=listing,
            post=clip_post(ctx.markdown, 6000, tail=0),
        )
        try:
            verdict = await self.llm.structured(
                task="opening panel",
                system=self.system,
                prompt=prompt,
                schema=OpeningVerdict,
                effort=self.settings.effort_opening_judge,
                max_tokens=8000,
                usage=usage,
            )
        except LLMError as exc:
            # Without a verdict the concepts keep the order they were pitched in (the pitcher put its best first).
            log.info("Opening panel failed (%s); using pitch order", exc)
            for i, entry in enumerate(entries):
                entry["panel"] = {j: max(1, 6 - i) for j in JUDGES} | {"note": "Not judged (the panel call failed)."}
            return ""
        for score in verdict.scores:
            if 0 <= score.concept < len(entries):
                entries[score.concept]["panel"] = {
                    **{j: max(1, min(10, int(getattr(score, j)))) for j in JUDGES},
                    "note": score.note,
                }
        for entry in entries:
            entry.setdefault("panel", {j: 1 for j in JUDGES} | {"note": "The panel did not score this one."})
        return verdict.summary

    # -- building ------------------------------------------------------------------------

    def _chosen_concept(self, state: dict[str, Any]) -> OpeningConcept:
        chosen = state.get("chosen")
        concepts = load_concepts(state)
        if isinstance(chosen, int) and 0 <= chosen < len(concepts):
            return concepts[chosen]
        return OpeningConcept(
            style=str(state.get("style") or FALLBACK),
            template=str(state.get("template") or ""),
            hook="",
            concept="",
            content="",
            data_claim="",
        )

    async def _build(
        self,
        concept: OpeningConcept,
        state: dict[str, Any],
        ctx: OpeningContext,
        art: ArtDirection,
        *,
        redraw: bool,
        usage: UsageSink | None,
        fix: str = "",
        keep_research: bool = False,
    ) -> _Built | None:
        style = BY_ID.get(concept.style) or BY_ID[FALLBACK]
        try:
            if style.builder == "meme":
                previous = str(state.get("meme") or "") if redraw and state.get("style") == "meme" else ""
                return await self._build_meme(concept, previous, ctx, art, usage)
            if style.builder == "svg":
                return await self._build_svg(style, concept, ctx, art, redraw=redraw, fix=fix, usage=usage)
            return await self._build_template(
                style, concept, state, ctx, art, redraw=redraw, fix=fix, keep_research=keep_research, usage=usage
            )
        except (ImageProviderError, LLMRefusalError) as exc:
            # This concept cannot be drawn (or researched); the next one gets its turn. Connection and credential
            # errors are not caught: they would fail every concept the same way.
            log.info("Opening %s could not be built: %s", style.id, exc)
            return None

    async def _build_svg(
        self,
        style: OpeningStyle,
        concept: OpeningConcept,
        ctx: OpeningContext,
        art: ArtDirection,
        *,
        redraw: bool,
        fix: str,
        usage: UsageSink | None,
    ) -> _Built:
        prompt = render(
            "opening_build_svg",
            style_label=style.label,
            style_rules=SVG_RULES.get(style.id, SVG_RULES[FALLBACK]),
            title=ctx.title,
            concept=_concept_text(concept),
            visual_style=art.visual_style,
            brand=art.brand,
            variation="This is a redraw: keep the idea but give it a fresh composition and staging." if redraw else "",
            fix=fix,
            image_guidance=art.image_guidance,
            post=clip_post(ctx.markdown, 5000, tail=0),
        )

        async def ask(note: str) -> SvgSpec:
            return await self.llm.structured(
                task=f"opening {style.id} drawing",
                system=self.system,
                prompt=prompt + note,
                schema=SvgSpec,
                effort=self.settings.effort_images,
                max_tokens=24000,
                usage=usage,
            )

        def draw(made: SvgSpec, _last: bool) -> tuple[bytes, int, int]:
            png, width, height = svg_to_png(made.svg, width=1600)
            if not _png_aspect_ok(width, height):
                raise ImageProviderError("Use viewBox `0 0 1600 900`: the opening image must be 16:9.")
            return png, width, height

        made, (png, width, height) = await draw_with_retry(ask, draw)
        return _Built(
            png, width, height, "claude-svg", made.alt, made.caption, {"style": style.id, "template": "", "svg": made.svg, "build": None}
        )

    async def _build_template(
        self,
        style: OpeningStyle,
        concept: OpeningConcept,
        state: dict[str, Any],
        ctx: OpeningContext,
        art: ArtDirection,
        *,
        redraw: bool,
        fix: str,
        keep_research: bool,
        usage: UsageSink | None,
    ) -> _Built:
        template = templates.get_template(concept.template) or templates.get_template(style.templates[0])
        assert template is not None
        post_text = clip_post(ctx.markdown, POST_LIMIT, tail=0)
        research_text, citations = "", []
        if style.needs_data:
            stored = state.get("research") or {}
            if keep_research or (stored.get("claim") == concept.data_claim and stored.get("text")):
                research_text = str(stored.get("text", ""))
                citations = [Citation(**c) for c in stored.get("citations", [])]
            else:
                try:
                    result = await self.llm.research(
                        system=[SystemBlock(raw("reference_research_system"))],
                        prompt=render(
                            "opening_research",
                            title=ctx.title,
                            claim=concept.data_claim or concept.concept,
                            post=clip_post(ctx.markdown, 8000, tail=0),
                        ),
                        effort=self.settings.effort_research,
                        max_searches=self.settings.opening_max_searches,
                        usage=usage,
                    )
                except LLMError as exc:
                    # Without research the post's own numbers may still carry the chart; the fact check decides.
                    log.info("Opening research failed: %s", exc)
                    result = ResearchResult(text="", citations=[])
                research_text, citations = result.text, result.citations
            state["research"] = {
                "claim": concept.data_claim,
                "text": research_text,
                "citations": [{"url": c.url, "title": c.title, "cited_text": c.cited_text} for c in citations],
            }
        facts_block = ""
        if style.needs_data:
            cites = "\n".join(f"- [{c.title or c.url}]({c.url})" + (f': "{c.cited_text}"' if c.cited_text else "") for c in citations)
            facts_block = (
                "\nEvery number you print must appear in this research or in the post, exactly as found (no estimates, "
                "no rounding a range into a point). Source URLs must be ones listed here; for a number from the post, "
                "use the source title 'This post' and an empty URL. If the research did not find the numbers, use the "
                "post's own numbers or a different point the found numbers support.\n"
                f"<research>\n{research_text or '(nothing found)'}\n</research>\n<citations>\n{cites or '(none)'}\n</citations>\n"
            )

        prompt = render(
            "opening_build_template",
            data_word=" and data" if template.is_chart or style.needs_data else "",
            spec=templates.build_spec(template),
            title=ctx.title,
            concept=_concept_text(concept),
            variation="This is a redraw: keep the idea but find fresher, sharper wording." if redraw else "",
            fix=fix,
            facts=facts_block,
            image_guidance=art.image_guidance,
            post=post_text,
        )

        async def ask(note: str) -> OpeningBuild:
            return await self.llm.structured(
                task=f"opening {template.id} build",
                system=self.system,
                prompt=prompt + note,
                schema=OpeningBuild,
                effort=self.settings.effort_images,
                max_tokens=16000,
                usage=usage,
            )

        def draw(build: OpeningBuild, last: bool) -> tuple[bytes, int, int]:
            blocking, wordy = templates.validate(template, build)
            if style.needs_data:
                blocking += facts.check(
                    build,
                    research=research_text,
                    citations=citations,
                    post=post_text,
                    steps=template.id == "waterfall",
                    percent=build.unit.strip() == "%",
                )
            if blocking or (wordy and not last):
                raise ImageProviderError("\n".join(blocking + wordy))
            return templates.draw(template, build, art.palette)

        build, (png, width, height) = await draw_with_retry(ask, draw)
        extra = {"style": style.id, "template": template.id, "svg": None, "build": build.model_dump()}
        if style.needs_data:
            extra["post_numbers"] = " ".join(f"{n:g}" for n in sorted(facts.numbers_in(post_text)))
        return _Built(png, width, height, "claude-opening", build.alt, self._caption(build.caption, build), extra)

    async def _build_meme(
        self, concept: OpeningConcept, previous: str, ctx: OpeningContext, art: ArtDirection, usage: UsageSink | None
    ) -> _Built:
        """The meme room pitches and draws the opener from the winning premise; a redraw keeps its joke."""
        base = ctx.meme_context or MemeContext(
            title=ctx.title, markdown=ctx.markdown, voice_profile=ctx.voice_profile, brief="", humor=ctx.humor
        )
        meme_ctx = replace(base, brief=f"{concept.concept} ({concept.hook})", position="opening", opening="", joke="")
        meme = await self.memes.make(previous, meme_ctx, art, redraw=bool(previous), usage=usage)
        return _Built(
            meme.png,
            meme.width,
            meme.height,
            meme.provider,
            meme.alt,
            meme.caption,
            {"style": "meme", "template": "", "svg": None, "build": None, "meme": meme.spec},
        )

    # -- review and finish ------------------------------------------------------------------

    async def _review(
        self, png: bytes, concept: str, style: OpeningStyle, ctx: OpeningContext, usage: UsageSink | None
    ) -> RenderReview | None:
        """Claude's look at the finished picture; None when this connection cannot show it an image (or the call fails)."""
        try:
            return await self.llm.structured(
                task="opening review",
                system=self.system,
                prompt=render("opening_review", title=ctx.title, style_label=style.label, concept=concept or "(the post's central idea)"),
                schema=RenderReview,
                effort=self.settings.effort_opening_review,
                max_tokens=6000,
                usage=usage,
                images=[_thumbnail_png(png)],
            )
        except LLMImagesUnsupportedError:
            return None
        except LLMError as exc:
            log.info("Opening review failed: %s", exc)
            return None

    async def _finish(
        self, state: dict[str, Any], built: _Built, ctx: OpeningContext, art: ArtDirection, usage: UsageSink | None, *, review: bool = True
    ) -> OpeningResult:
        state.update(built.state)
        style = BY_ID.get(str(state.get("style"))) or BY_ID[FALLBACK]
        concept = self._chosen_concept(state)
        concept_text = _concept_text(concept) if concept.concept else ""
        if review:
            first = await self._review(built.png, concept_text, style, ctx, usage)
            if first is None:
                state["review"] = {"skipped": True, "note": "This connection cannot show Claude the image, so it was not reviewed."}
            elif first.passes:
                state["review"] = _review_entry(first, "passed")
            else:
                fix = (
                    "\nA reviewer looked at the rendered image and sent it back. Fix every problem:\n"
                    + "\n".join(f"- {p}" for p in first.problems)
                    + (f"\nWhat to change: {first.fix}\n" if first.fix else "\n")
                )
                again: _Built | None
                if style.builder == "meme":
                    try:
                        meme = await self.memes.edit(str(state.get("meme") or ""), first.fix or "; ".join(first.problems), art, usage=usage)
                        again = _Built(meme.png, meme.width, meme.height, meme.provider, meme.alt, meme.caption, {"meme": meme.spec})
                    except (ImageProviderError, LLMRefusalError):
                        again = None
                else:
                    again = await self._build(concept, state, ctx, art, redraw=False, usage=usage, fix=fix, keep_research=True)
                second = await self._review(again.png, concept_text, style, ctx, usage) if again else None
                if again is not None and (second is None or _score(second) >= _score(first)):
                    built = again
                    state.update(again.state)
                    state["review"] = _review_entry(second, "redrawn") if second else {"verdict": "redrawn", "problems": first.problems}
                else:
                    state["review"] = _review_entry(first, "kept")
        return OpeningResult(built.png, built.width, built.height, built.provider, json.dumps(state), built.alt, built.caption)

    def _from_meme(self, state: dict[str, Any], meme: MemeResult) -> OpeningResult:
        state["meme"] = meme.spec
        state["style"] = "meme"
        return OpeningResult(meme.png, meme.width, meme.height, meme.provider, json.dumps(state), meme.alt, meme.caption)

    @staticmethod
    def _caption(caption: str, build: OpeningBuild) -> str:
        line = templates.source_line(build)
        caption = caption.strip()
        if line and "source" not in caption.lower():
            caption = f"{caption} {line}.".strip()
        return caption


def _score(review: RenderReview) -> int:
    return review.clickability + review.craft + (5 if review.passes else 0)


def _review_entry(review: RenderReview, verdict: str) -> dict[str, Any]:
    return {"verdict": verdict, "clickability": review.clickability, "craft": review.craft, "problems": review.problems[:5]}


def _thumbnail_png(png: bytes, width: int = 800) -> bytes:
    """A smaller copy for the review: cheaper to send, and closer to how a feed shows it."""
    with Image.open(io.BytesIO(png)) as source:
        img = source.convert("RGB")
    if img.width > width:
        img = img.resize((width, round(img.height * width / img.width)), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()
