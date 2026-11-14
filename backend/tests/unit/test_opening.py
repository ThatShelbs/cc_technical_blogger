"""The opening image: the style catalog, code templates, the fact check and the pitching/judging room."""

from __future__ import annotations

import io
import json
from typing import Any

import pytest
from PIL import Image
from pydantic import BaseModel

from proseferno.config import Settings
from proseferno.db import Persona
from proseferno.demo import DEMO_OPENING_RESEARCH, DEMO_SOURCE_URL, DRAFT, FakeLLM, opening_build_payload
from proseferno.export.bundle import _thumbnail
from proseferno.images import ImageProviderError
from proseferno.images.memes import ArtDirection, MemeContext, MemeMaker
from proseferno.images.memes.generate import position_guide
from proseferno.images.opening import facts
from proseferno.images.opening.canvas import SAFE_BOTTOM, SAFE_TOP, Canvas, frame, theme_for
from proseferno.images.opening.charts import fmt_value, nice_ticks
from proseferno.images.opening.room import OpeningContext, OpeningRoom, load_state, ranking
from proseferno.images.opening.specs import OpeningBuild, OpeningIdeas, RenderReview
from proseferno.images.opening.styles import BY_ID, STYLES, clean_style, eligible, suggested
from proseferno.images.opening.templates import TEMPLATES, apply_words, draw, slot_texts, validate
from proseferno.llm.base import Citation, LLMImagesUnsupportedError
from proseferno.writer.dials import Dials, resolve
from proseferno.writer.formulas import ARTICLE_TYPES, OPENERS

ART = ArtDirection(visual_style="flat vector")


def context(**changes: Any) -> OpeningContext:
    base = OpeningContext(
        title="Pie Charts Are Lame",
        markdown=DRAFT,
        voice_profile="",
        brief="Thumbnail",
        hook="Admit to hating pie charts.",
        humor=5,
        suggested=("cheat_sheet", "editorial", "data_art"),
        eligible=tuple(s.id for s in STYLES),
    )
    return OpeningContext(**{**base.__dict__, **changes})


def build_of(template_id: str, **changes: Any) -> OpeningBuild:
    return OpeningBuild.model_validate({**opening_build_payload(template_id), **changes})


# -- catalog and dials ------------------------------------------------------------------------


def test_catalog_names_only_real_article_types_openers_and_templates() -> None:
    known = {t.id for t in ARTICLE_TYPES} | {o.id for o in OPENERS}
    for style in STYLES:
        assert set(style.suits) <= known, style.id
        assert all(TEMPLATES[t].style == style.id for t in style.templates), style.id
    assert {t.style for t in TEMPLATES.values()} <= set(BY_ID)


def test_suggestions_fit_the_article_type_and_always_keep_the_open_styles() -> None:
    how_to = suggested("how_to", "auto", 5)
    assert how_to[:2] == ["cheat_sheet", "framework"] and how_to[-2:] == ["editorial", "data_art"]
    assert suggested("auto", "auto", 5) == ["editorial", "data_art"]
    # A joke opener invites an opening meme, unless the humor dial is too low for one.
    assert "meme" in suggested("auto", "joke_confession", 5)
    assert "meme" not in suggested("opinion", "joke_confession", 2) and "meme" not in eligible("opinion", "auto", 2)
    assert set(eligible("how_to", "auto", 5)) == set(BY_ID)


def test_opening_style_resolves_post_over_persona_and_unknown_to_auto() -> None:
    persona = Persona(name="P", default_opening_style="versus")
    assert resolve(Dials(), persona, "Pie charts", default_revisions=0).opening_style == "versus"
    assert resolve(Dials(opening_style="big_number"), persona, "x", default_revisions=0).opening_style == "big_number"
    assert resolve(Dials(opening_style="auto"), persona, "x", default_revisions=0).opening_style == "auto"
    assert resolve(Dials(opening_style="hologram"), persona, "x", default_revisions=0).opening_style == "auto"
    resolved = resolve(
        Dials(opening_note="Use the plinko idea"), Persona(name="Q"), "How to pick a chart: a step-by-step guide", default_revisions=0
    )
    assert resolved.opening_style == "auto" and resolved.opening_note == "Use the plinko idea"
    assert resolved.opening_suggested[0] == "cheat_sheet" and resolved.opening_label == "Auto (the panel picks)"
    assert clean_style("") == "auto" and clean_style("receipt") == "receipt"


# -- templates ------------------------------------------------------------------------------


@pytest.mark.parametrize("template_id", sorted(TEMPLATES))
def test_every_template_renders_a_16_9_image_with_text_in_the_crop_safe_band(template_id: str) -> None:
    template, build = TEMPLATES[template_id], build_of(template_id)
    assert validate(template, build) == ([], [])
    png, width, height = draw(template, build)
    with Image.open(io.BytesIO(png)) as img:
        assert img.size == (width, height) == (1600, 900)
    canvas = Canvas(theme_for())
    template.draw(canvas, build, frame(canvas, build.headline, build.subhead, "Source: x"))
    for text in canvas.texts:
        _, y, _, h = text.box
        assert y >= SAFE_TOP and y + h <= SAFE_BOTTOM, (template_id, text.text, text.box)


def test_templates_turn_down_builds_they_cannot_draw() -> None:
    blocking, _ = validate(TEMPLATES["cheat_grid"], build_of("cheat_grid", items=[{"label": "Only one", "detail": ""}]))
    assert blocking == ["`items` needs 4-9 entries; it has 1."]
    blocking, _ = validate(TEMPLATES["slope"], build_of("slope", data=[{"label": "A", "value": 1, "series": "2019"}]))
    assert any("distinct series" in p for p in blocking)
    blocking, _ = validate(TEMPLATES["ranked_bar"], build_of("ranked_bar", sources=[]))
    assert "`sources` is empty: say where the numbers come from." in blocking
    _, wordy = validate(TEMPLATES["cheat_grid"], build_of("cheat_grid", headline="x" * 120))
    assert wordy and "headline" in wordy[0]
    with pytest.raises(ImageProviderError):
        draw(TEMPLATES["versus"], build_of("versus", left_label=""))


def test_a_brand_palette_recolours_the_templates() -> None:
    dark, light = theme_for(("#0b1d2a", "#38bdf8", "#f472b6")), theme_for(("#ffffff", "#e0e7ff", "#2563eb", "#db2777"))
    assert dark.bg == "#0b1d2a" and dark.ink == "#ffffff"
    assert light.bg == "#ffffff" and light.ink == "#14101f" and "#2563eb" in light.accents
    assert theme_for(("#123456",)).bg == theme_for().bg  # fewer than three colors: the house theme


def test_words_can_be_retyped_but_numbers_are_not_among_them() -> None:
    template, build = TEMPLATES["ranked_bar"], build_of("ranked_bar")
    names = [name for name, *_ in slot_texts(template, build)]
    assert "headline" in names and "number" not in names and not any(n.startswith("data") for n in names)
    changed = apply_words(build, {"headline": "Bars win again", "items.9.label": "ignored", "data": "nope"})
    assert changed.headline == "Bars win again" and changed.data == build.data


def test_chart_helpers_format_values_and_close_axes_on_a_tick() -> None:
    assert fmt_value(62, "%") == "62%" and fmt_value(4.2e6, "$") == "$4.2M" and fmt_value(120, "ms") == "120 ms"
    assert fmt_value(1234) == "1,234" and fmt_value(-3, "%", signed=True) == "-3%" and fmt_value(12, "%", signed=True) == "+12%"
    assert fmt_value(15300) == "15.3k" and fmt_value(0.25) == "0.25"
    ticks = nice_ticks(0, 96.5)
    assert ticks[0] == 0 and ticks[-1] >= 96.5


# -- the fact check -----------------------------------------------------------------------------


def test_every_printed_number_must_come_from_the_research_or_the_post() -> None:
    research = "Accuracy was 62% with pie charts and 91% with sorted bars. Revenue reached $3.4M, up from 1,200 users."
    cites = [Citation(url="https://example.com/a", title="A")]
    rows = [{"label": "Pie", "value": 62, "series": ""}, {"label": "Bars", "value": 91, "series": ""}]
    ok = build_of("ranked_bar", data=rows, sources=[{"title": "A", "url": "https://example.com/a"}])
    assert facts.check(ok, research=research, citations=cites, post="") == []
    invented = ok.model_copy(update={"subhead": "Readers were 47% faster"})
    assert facts.check(invented, research=research, citations=cites, post="") == [
        "subhead: 47 is not in the research or the post. Use only numbers you were given."
    ]
    # The post's own numbers count, scale words and separators are understood, and years are dates, not claims.
    from_post = build_of(
        "big_number", number="3.4M", subhead="users in 2024", items=[], data=[], sources=[{"title": "This post", "url": ""}]
    )
    assert facts.check(from_post, research="", citations=[], post="We hit 3.4 million users.") == []
    assert {1200.0, 3.4, 3_400_000.0} <= facts.numbers_in(research)
    # A source URL the research never cited is refused.
    bad_source = build_of("ranked_bar", data=rows, sources=[{"title": "Made up", "url": "https://example.com/elsewhere"}])
    assert any("did not cite" in p for p in facts.check(bad_source, research=research, citations=cites, post=""))


def test_waterfall_steps_may_be_differences_but_words_may_not() -> None:
    build = build_of("waterfall")
    cites = [Citation(url=DEMO_SOURCE_URL)]
    assert facts.check(build, research=DEMO_OPENING_RESEARCH, citations=cites, post="", steps=True) == []
    assert facts.check(build, research=DEMO_OPENING_RESEARCH, citations=cites, post="", steps=False)
    claim = build.model_copy(update={"annotation": "A 29 point drop"})
    assert any("annotation: 29" in p for p in facts.check(claim, research=DEMO_OPENING_RESEARCH, citations=cites, post="", steps=True))


# -- the room ------------------------------------------------------------------------------------


async def test_auto_pitches_mix_styles_and_the_panel_picks_the_winner() -> None:
    llm = FakeLLM()
    room = OpeningRoom(llm, Settings(), MemeMaker(llm, Settings()))
    result = await room.make("", context(), ART)
    state = load_state(result.spec)
    assert state is not None and state["mode"] == "auto" and len(state["concepts"]) == 6
    styles = [c["style"] for c in state["concepts"]]
    assert styles.count("editorial") >= 2 and "data_art" in styles and styles[0] == "cheat_sheet"
    assert state["chosen"] == 0 and state["style"] == "cheat_sheet" and state["template"] == "cheat_grid"
    assert all(set(c["panel"]) >= {"scroller", "art_director", "fact_checker", "author", "note"} for c in state["concepts"])
    assert state["review"]["verdict"] == "passed" and result.provider == "claude-opening"
    assert llm.tasks()[:2] == ["opening ideas", "opening panel"] and llm.calls[-1]["images"] == 1
    pitch = llm.calls[0]["prompt"]
    assert (
        "Pitch exactly 6" in pitch
        and "at least two concepts are open visual metaphors" in pitch
        and "plinko" in llm.calls[0]["system"][0].text
    )


async def test_a_pitch_missing_the_open_styles_is_sent_back_once(monkeypatch: pytest.MonkeyPatch) -> None:
    llm = FakeLLM()
    room = OpeningRoom(llm, Settings(), MemeMaker(llm, Settings()))
    original = llm.structured
    first = {"done": False}

    async def literal_first(**kwargs: Any) -> Any:
        result = await original(**kwargs)
        if kwargs["schema"] is OpeningIdeas and not first["done"]:
            first["done"] = True
            return result.model_copy(update={"concepts": [c.model_copy(update={"style": "versus"}) for c in result.concepts]})
        return result

    monkeypatch.setattr(llm, "structured", literal_first)
    state = load_state((await room.make("", context(), ART)).spec)
    pitches = [c for c in llm.calls if c["task"] == "opening ideas"]
    assert len(pitches) == 2 and "at least two open visual metaphors" in pitches[1]["prompt"]
    assert state and sum(c["style"] == "editorial" for c in state["concepts"]) >= 2


async def test_a_chosen_style_pitches_four_ideas_in_it() -> None:
    llm = FakeLLM()
    room = OpeningRoom(llm, Settings(), MemeMaker(llm, Settings()))
    state = load_state((await room.make("", context(style="versus"), ART)).spec)
    assert state and state["mode"] == "versus" and [c["style"] for c in state["concepts"]] == ["versus"] * 4
    assert "All 4 concepts use the style `versus`" in llm.calls[0]["prompt"]


async def test_data_openers_are_researched_and_unverifiable_ones_give_way(monkeypatch: pytest.MonkeyPatch) -> None:
    llm = FakeLLM()
    room = OpeningRoom(llm, Settings(), MemeMaker(llm, Settings()))
    chart = load_state((await room.make("", context(style="data_chart"), ART)).spec)
    assert chart and chart["style"] == "data_chart" and chart["research"]["citations"][0]["url"] == DEMO_SOURCE_URL
    assert chart["build"]["sources"] and "research" in llm.tasks()

    # When research finds nothing and the build invents numbers, the data concept is dropped for the next best.
    async def nothing(**_: Any) -> Any:
        from proseferno.llm.base import ResearchResult

        return ResearchResult(text="", citations=[])

    monkeypatch.setattr(llm, "research", nothing)
    state = {
        "version": 1,
        "room": "opening",
        "brief": "Thumbnail",
        "mode": "auto",
        "concepts": [
            {"style": "big_number", "template": "big_number", "hook": "h", "concept": "c", "content": "", "data_claim": "d",
             "panel": {"scroller": 9, "art_director": 9, "fact_checker": 9, "author": 9}},
            {"style": "editorial", "template": "", "hook": "h", "concept": "A plinko board", "content": "", "data_claim": "",
             "panel": {"scroller": 7, "art_director": 7, "fact_checker": 9, "author": 8}},
        ],
        "chosen": 0,
        "tried": [],
    }  # fmt: skip
    result = await room.make(json.dumps(state), context(), ART, redraw=True)
    after = load_state(result.spec)
    assert after and after["style"] == "editorial" and after["chosen"] == 1 and after["fallback_from"] == "big_number"
    assert after["tried"] == [0, 1]


async def test_ruled_out_concepts_rank_last_and_stored_pitches_need_no_new_calls() -> None:
    state = {
        "concepts": [
            {"style": "editorial", "panel": {"scroller": 10, "art_director": 10, "fact_checker": 3, "author": 10}},
            {"style": "versus", "panel": {"scroller": 6, "art_director": 6, "fact_checker": 8, "author": 8}},
            {"style": "hologram", "panel": {"scroller": 10, "art_director": 10, "fact_checker": 10, "author": 10}},
        ]
    }
    assert ranking(state) == [1, 0]

    llm = FakeLLM()
    room = OpeningRoom(llm, Settings(), MemeMaker(llm, Settings()))
    first = await room.make("", context(), ART)
    llm.calls.clear()
    picked = await room.make(first.spec, context(), ART, concept_index=1)
    assert load_state(picked.spec)["chosen"] == 1  # type: ignore[index]
    assert "opening ideas" not in llm.tasks() and "opening panel" not in llm.tasks()
    with pytest.raises(ImageProviderError):
        await room.make(first.spec, context(), ART, concept_index=40)


class NoEyesLLM(FakeLLM):
    """A connection that cannot show Claude an image (like headless Claude Code)."""

    async def structured(self, *, task: str, schema: type[BaseModel], **kwargs: Any) -> Any:
        if kwargs.get("images"):
            raise LLMImagesUnsupportedError()
        return await super().structured(task=task, schema=schema, **kwargs)


async def test_the_render_review_is_skipped_without_image_input_and_a_failure_is_redrawn_once(monkeypatch: pytest.MonkeyPatch) -> None:
    llm = NoEyesLLM()
    room = OpeningRoom(llm, Settings(), MemeMaker(llm, Settings()))
    state = load_state((await room.make("", context(), ART)).spec)
    assert state and state["review"]["skipped"] is True

    picky = FakeLLM()
    room = OpeningRoom(picky, Settings(), MemeMaker(picky, Settings()))
    original = picky.structured
    reviews = iter(
        [
            RenderReview(passes=False, clickability=5, craft=4, problems=["Tiles are cramped"], fix="Use fewer, larger tiles."),
            RenderReview(passes=True, clickability=8, craft=8),
        ]
    )

    async def strict(**kwargs: Any) -> Any:
        if kwargs["schema"] is RenderReview:
            await original(**kwargs)
            return next(reviews)
        return await original(**kwargs)

    monkeypatch.setattr(picky, "structured", strict)
    state = load_state((await room.make("", context(), ART)).spec)
    builds = [c for c in picky.calls if c["task"] == "opening cheat_grid build"]
    assert len(builds) == 2 and "Use fewer, larger tiles." in builds[1]["prompt"]
    assert state and state["review"]["verdict"] == "redrawn"


async def test_an_opening_meme_is_pitched_by_the_meme_room_as_an_opener() -> None:
    llm = FakeLLM()
    room = OpeningRoom(llm, Settings(), MemeMaker(llm, Settings()))
    result = await room.make("", context(style="meme"), ART)
    state = load_state(result.spec)
    assert state and state["style"] == "meme" and json.loads(state["meme"])["version"] == 2
    ideas = next(c for c in llm.calls if c["task"] == "meme ideas")
    assert "Pitch the opening meme" in ideas["prompt"] and "a 14-slice pie chart" in ideas["prompt"]

    words = await room.edit(result.spec, "Make the robot smug", context(), ART)
    assert load_state(words.spec)["style"] == "meme"  # type: ignore[index]


def test_the_closing_meme_of_a_meme_sandwich_knows_the_opener() -> None:
    post = MemeContext(title="T", markdown="", voice_profile="", brief="b")
    assert position_guide(post) == "Pitch the closing meme for this post."
    sandwich = position_guide(MemeContext(**{**post.__dict__, "opening": "a Venn meme: pies and pizza"}))
    assert "meme sandwich" in sandwich and "different format family" in sandwich and "pies and pizza" in sandwich


def test_a_contain_thumbnail_keeps_the_whole_image(tmp_path: Any) -> None:
    path = tmp_path / "meme.png"
    Image.new("RGB", (1080, 1080), "#fb9b06").save(path)
    with Image.open(io.BytesIO(_thumbnail(path, (1500, 600), "contain"))) as thumb:
        assert thumb.size == (1500, 600)
        assert thumb.getpixel((750, 300)) == (251, 155, 6) and thumb.getpixel((5, 300)) == (251, 155, 6)
    with Image.open(io.BytesIO(_thumbnail(path, (1500, 600)))) as cropped:
        assert cropped.size == (1500, 600)
