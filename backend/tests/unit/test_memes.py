from __future__ import annotations

import io
import json
import random
import re
from typing import Any

import pytest
from PIL import Image, ImageDraw
from pydantic import BaseModel

from inferno_ghostwriter.config import Settings
from inferno_ghostwriter.demo import DEMO_MEME_TEXTS, FakeLLM, meme_build_payload, meme_ideas_payload
from inferno_ghostwriter.images import ImageProviderError
from inferno_ghostwriter.images.memes import FORMATS, ArtDirection, MemeContext, MemeMaker, get_format, load_state, plan_callbacks
from inferno_ghostwriter.images.memes.compose import MASCOT_SCENE, compose, region_svg
from inferno_ghostwriter.images.memes.formats import CAST, ArtRegion, build_spec, menu
from inferno_ghostwriter.images.memes.generate import clip_post, render_build
from inferno_ghostwriter.images.memes.looks import BY_ID as BY_LOOK
from inferno_ghostwriter.images.memes.looks import LOOKS, choose_look, get_look, themed
from inferno_ghostwriter.images.memes.looks import menu as looks_menu
from inferno_ghostwriter.images.memes.specs import MemeBuild, MemeReview, MemeVerdict
from inferno_ghostwriter.images.memes.text import STYLES, fit_text
from inferno_ghostwriter.llm import LLMError
from inferno_ghostwriter.llm.base import LLMImagesUnsupportedError
from inferno_ghostwriter.prompts import raw

POST = MemeContext(title="Pie Charts Are Lame", markdown="# Pie Charts Are Lame\n\nUse bars.", voice_profile="", brief="Closing laugh")
ART = ArtDirection(visual_style="flat vector")


def render(format_id: str, **changes: Any) -> tuple[bytes, int, int]:
    fmt = get_format(format_id)
    assert fmt is not None
    build = MemeBuild.model_validate({**meme_build_payload(format_id), **changes})
    return compose(fmt, {t.slot: t for t in build.texts}, {a.region: a.svg for a in build.art}, build.cast_defs, build.data)


@pytest.mark.parametrize("fmt", FORMATS, ids=lambda f: f.id)
def test_every_format_renders(fmt: Any) -> None:
    png, width, height = render(fmt.id)
    with Image.open(io.BytesIO(png)) as img:
        assert img.size == (width, height)
    if fmt.id != "spurious_correlation":
        assert (width, height) == fmt.size


def test_catalog_is_consistent() -> None:
    assert len(FORMATS) == 23 and len({f.id for f in FORMATS}) == 23
    for fmt in FORMATS:
        names = [s.name for s in fmt.slots]
        assert len(names) == len(set(names)), fmt.id
        assert all(name in names for group in fmt.groups for name in group), fmt.id
        assert f"`{fmt.id}`" in menu() and f"Format `{fmt.id}`" in build_spec(fmt)
    assert "`venn`" in menu("venn") and "`nope_yep`" not in menu("venn")


def test_text_is_fitted_inside_its_box() -> None:
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    long_text = "An unreasonably long caption that keeps going " * 6
    fitted = fit_text(draw, long_text, 300, 120, STYLES["dark"])
    assert fitted.width <= 300 and fitted.height <= 120
    # Short text grows to fill the box, and whole words are kept when any size allows it.
    big = fit_text(draw, "Truncated y-axis", 340, 250, STYLES["dark"])
    assert big.size > 40 and not big.broke and all(line in ("Truncated", "y-axis", "Truncated y-axis") for line in big.lines)


def test_region_ids_are_made_unique_and_scripts_never_survive() -> None:
    region = ArtRegion("p1", (0, 0, 100, 100), "")
    svg = region_svg(region, '<defs><linearGradient id="g"/></defs><rect fill="url(#g)"/><use href="#ghost"/><script>x()</script>')
    assert 'id="r-p1-g"' in svg and "url(#r-p1-g)" in svg and 'href="#ghost"' in svg
    png, _, _ = render(
        "classic_caption", art=[{"region": "scene", "svg": '<rect width="10" height="10" onclick="x()"/><script>alert(1)</script>'}]
    )
    assert png.startswith(b"\x89PNG")
    # A slip a browser would forgive (a bare ampersand, an unclosed tag) is repaired, not sent back to Claude.
    repaired, _, _ = render(
        "classic_caption", art=[{"region": "scene", "svg": '<g><rect width="9" height="9" fill="red"/><title>R&D</title>'}]
    )
    assert repaired.startswith(b"\x89PNG")
    with pytest.raises(ImageProviderError):
        render("classic_caption", art=[{"region": "scene", "svg": "I could not draw this."}])


def test_brand_palette_recolors_chart_marks() -> None:
    fmt = get_format("joke_pie_3d")
    assert fmt is not None
    build = MemeBuild.model_validate(meme_build_payload("joke_pie_3d"))
    texts = {t.slot: t for t in build.texts}
    inferno, _, _ = compose(fmt, texts, {}, "", build.data)
    branded, _, _ = compose(fmt, texts, {}, "", build.data, palette=("#003366", "#00aa88", "#ffcc00"))
    assert inferno != branded


def test_plan_callbacks_feed_the_writers_room() -> None:
    plan = {"callbacks": [{"kind": "running_joke", "idea": "Pies are round because nobody stopped them", "payoff": "A pie stops itself"}]}
    assert plan_callbacks(plan) == "- Running joke: Pies are round because nobody stopped them (payoff: A pie stops itself)"
    assert plan_callbacks(None) == ""


async def test_new_idea_moves_through_pitches_without_new_ideation() -> None:
    llm = FakeLLM()
    maker = MemeMaker(llm, Settings())
    first = await maker.make("", POST, ART)
    state = load_state(first.spec)
    assert state and state["chosen"] == 0 and state["tried"] == [0] and len(state["concepts"]) == 5
    assert llm.tasks().count("meme ideas") == 1

    redrawn = await maker.make(first.spec, POST, ART, redraw=True)
    assert load_state(redrawn.spec)["chosen"] == 0  # type: ignore[index]

    spec = first.spec
    seen = [0]
    for _ in range(4):
        spec = (await maker.make(spec, POST, ART, rethink=True)).spec
        seen.append(load_state(spec)["chosen"])  # type: ignore[index]
    assert sorted(seen) == [0, 1, 2, 3, 4]
    assert llm.tasks().count("meme ideas") == 1

    # Every pitch used: the room is asked again, told what to avoid.
    await maker.make(spec, POST, ART, rethink=True)
    pitches = [c for c in llm.calls if c["task"] == "meme ideas"]
    assert len(pitches) == 2 and "already used" in pitches[-1]["prompt"]


async def test_a_format_with_no_art_is_drawn_from_the_pitch_alone() -> None:
    llm = FakeLLM()
    maker = MemeMaker(llm, Settings())
    first = await maker.make("", POST, ART, meme_format="joke_pie_3d")
    assert llm.tasks() == ["meme ideas", "meme panel"]
    state = load_state(first.spec)
    assert state and state["format"] == "joke_pie_3d" and first.caption == "Pie logic (data: entirely made up)"
    assert "What pie charts are good for" in first.alt and "Showing two slices: 6" in first.alt

    # Another pitch in the same art-free format, and a redraw: still no call to Claude.
    await maker.make(first.spec, POST, ART, rethink=True)
    await maker.make(first.spec, POST, ART, redraw=True)
    assert llm.tasks() == ["meme ideas", "meme panel"]

    # A pitch saved before pitches carried chart data cannot be drawn directly, so production is asked.
    old = json.loads(first.spec)
    for concept in old["concepts"]:
        del concept["data"], concept["caption"]
    await maker.make(json.dumps(old), POST, ART, redraw=True)
    assert llm.tasks()[-1] == "meme build (joke_pie_3d)"


async def test_the_author_picks_a_pitch_and_retypes_words_without_claude() -> None:
    llm = FakeLLM()
    maker = MemeMaker(llm, Settings())
    first = await maker.make("", POST, ART, meme_format="terminal")
    llm.calls.clear()

    picked = await maker.make(first.spec, POST, ART, concept_index=3)
    state = load_state(picked.spec)
    assert state and state["chosen"] == 3 and state["tried"] == [0, 3] and llm.calls == []
    with pytest.raises(ImageProviderError):
        await maker.make(first.spec, POST, ART, concept_index=9)

    reworded = maker.reword(picked.spec, {"out3": "fatal: nobody owns this chart"}, ART)
    state = load_state(reworded.spec)
    assert state and llm.calls == [] and reworded.png != picked.png
    words = {t["slot"]: t["text"] for t in state["build"]["texts"]}
    assert words["out3"] == "fatal: nobody owns this chart" and words["cmd1"] == "python make_chart.py --type pie"
    assert "nobody owns this chart" in reworded.alt
    # The pitch keeps the new words, so a redraw does not bring the old ones back.
    assert {t["slot"]: t["text"] for t in state["concepts"][3]["texts"]}["out3"] == "fatal: nobody owns this chart"
    with pytest.raises(ImageProviderError):
        maker.reword(picked.spec, {"out3": ""}, ART)  # a required slot cannot be emptied


def test_a_long_post_keeps_its_ending_for_the_writers_room() -> None:
    post = "Opening line. " + "middle " * 6000 + "The pie stops itself."
    clipped = clip_post(post + "\n\n{{image:meme}}")
    assert len(clipped) < 24200 and clipped.startswith("Opening line.") and clipped.endswith("The pie stops itself.")
    assert "middle of the post is omitted" in clipped and "{{image" not in clipped
    assert clip_post("Short post.") == "Short post."


async def test_the_room_is_told_which_formats_the_author_just_used() -> None:
    llm = FakeLLM()
    recent = MemeContext(**{**POST.__dict__, "recent_formats": ("Venn diagram", "Terminal session")})
    await MemeMaker(llm, Settings()).make("", recent, ART)
    assert "last memes used: Venn diagram, Terminal session" in llm.calls[0]["prompt"]


async def test_a_new_brief_or_format_starts_a_fresh_pitch() -> None:
    llm = FakeLLM()
    maker = MemeMaker(llm, Settings())
    first = await maker.make("", POST, ART)
    changed = MemeContext(**{**POST.__dict__, "brief": "Make it about donuts"})
    await maker.make(first.spec, changed, ART, rethink=True)
    assert llm.tasks().count("meme ideas") == 2

    venn = await maker.make(first.spec, POST, ART, meme_format="venn")
    state = load_state(venn.spec)
    assert state and state["format"] == "venn" and {c["format"] for c in state["concepts"]} == {"venn"}
    assert "Only use the format `venn`" in [c for c in llm.calls if c["task"] == "meme ideas"][-1]["prompt"]


class BrokenBuildLLM(FakeLLM):
    """Pitches fine, but every build is missing its art."""

    async def structured(self, *, task: str, schema: type[BaseModel], **kwargs: Any) -> Any:
        result = await super().structured(task=task, schema=schema, **kwargs)
        return result.model_copy(update={"art": []}) if schema is MemeBuild else result


async def test_an_undrawable_build_is_retried_then_falls_back_to_a_caption_meme() -> None:
    llm = BrokenBuildLLM()
    maker = MemeMaker(llm, Settings())
    llm_first = await maker.make("", POST, ART, meme_format="nope_yep")
    builds = [c for c in llm.calls if c["task"].startswith("meme build")]
    assert len(builds) == 2 and "has no drawing" in builds[1]["prompt"]
    state = load_state(llm_first.spec)
    # Every pitch is in the format the author asked for, so the caption meme is all that is left.
    assert state and state["format"] == "classic_caption" and llm_first.png.startswith(b"\x89PNG")
    assert state["fallback_from"] == "nope_yep"


async def test_an_undrawable_format_falls_back_to_a_pitch_that_needs_no_art() -> None:
    llm = BrokenBuildLLM()
    maker = MemeMaker(llm, Settings())
    ideas = meme_ideas_payload("Only use the format `nope_yep`")
    for concept, fmt in zip(ideas["concepts"][1:], ("terminal", "venn"), strict=False):
        concept.update(format=fmt, texts=[{"slot": s, "text": t, "speaker": ""} for s, t in DEMO_MEME_TEXTS[fmt].items()])
    ideas["concepts"][2]["scores"]["surprise"] = 5  # the Venn is the best of the rest
    state = {"version": 2, "brief": POST.brief, "concepts": ideas["concepts"], "chosen": 0, "tried": []}

    meme = await maker.make(json.dumps(state), POST, ART, redraw=True)
    after = load_state(meme.spec)
    assert after and after["format"] == "venn" and after["chosen"] == 2 and after["tried"] == [0, 2]
    assert after["fallback_from"] == "nope_yep" and "Pizza" in meme.alt

    # The next meme that draws cleanly is no longer marked as a stand-in.
    again = await maker.make(meme.spec, POST, ART, redraw=True)
    assert "fallback_from" not in (load_state(again.spec) or {})


async def test_editing_a_meme_keeps_its_format_and_joke() -> None:
    llm = FakeLLM()
    maker = MemeMaker(llm, Settings())
    first = await maker.make("", POST, ART, meme_format="terminal")
    edited = await maker.edit(first.spec, "Make the last line angrier", ART)
    state = load_state(edited.spec)
    assert state and state["format"] == "terminal" and state["concepts"] == json.loads(first.spec)["concepts"]
    assert "Make the last line angrier" in llm.calls[-1]["prompt"] and "meme edit (terminal)" in llm.tasks()
    with pytest.raises(ImageProviderError):
        await maker.edit(json.dumps({"svg": "<svg/>", "top": "a", "bottom": "b"}), "Bigger", ART)


# -- Looks, the panel, the render review and the classic formats ------------------------------------------


def test_looks_catalog_is_consistent_and_templates_follow_the_look() -> None:
    assert len(LOOKS) >= 10 and len({look.id for look in LOOKS}) == len(LOOKS)
    hexa = re.compile(r"^#[0-9a-fA-F]{6}$")
    for look in LOOKS:
        colors = [*look.palette, look.theme.dark, look.theme.paper, look.theme.ink, *look.theme.accents, *look.theme.bands]
        assert all(hexa.match(c) for c in colors), look.id
        assert len(look.theme.accents) == 6 and look.art and look.cast and look.suits
        assert f"`{look.id}`" in looks_menu()
    # The comic gutters, chat header, charts and alignment bands follow the theme, so every look paints differently.
    for fmt_id in ("comic_strip_3", "chat_thread", "joke_pie_3d", "alignment_chart", "midwit_bell_curve", "spurious_correlation"):
        fmt = get_format(fmt_id)
        assert fmt is not None
        build = MemeBuild.model_validate(meme_build_payload(fmt_id))
        args = (fmt, {t.slot: t for t in build.texts}, {a.region: a.svg for a in build.art}, build.cast_defs, build.data)
        assert len({compose(*args, theme=look.theme)[0] for look in LOOKS}) >= 8, fmt_id


def test_every_format_renders_in_every_look() -> None:
    for fmt in FORMATS:
        build = MemeBuild.model_validate(meme_build_payload(fmt.id))
        for look in LOOKS[::3]:
            png, _, _ = render_build(fmt, build, (), look)
            assert png.startswith(b"\x89PNG"), (fmt.id, look.id)


def test_choose_look_honors_the_pick_avoids_recent_looks_and_lets_a_brand_palette_override() -> None:
    assert choose_look("kawaii", "soft_3d", ("kawaii",)).id == "kawaii"
    assert choose_look(None, "soft_3d", ("kawaii",)).id == "soft_3d"
    assert choose_look(None, "soft_3d", ("soft_3d", "kawaii")).id != "soft_3d"
    assert choose_look(None, "nonsense", ()).id in BY_LOOK
    rng = random.Random(7)
    seen = {choose_look(None, None, ("kawaii", "soft_3d"), rng=rng).id for _ in range(60)}
    assert len(seen) > 5 and not seen & {"kawaii", "soft_3d"}
    assert choose_look(None, None, (), avoid=("kawaii",), rng=rng).id != "kawaii"
    assert get_look("never-heard-of-it").id == "inferno_flat" and get_look(None).id == "inferno_flat"
    brand = themed(get_look("kawaii"), ("#003366", "#00aa88", "#ffcc00"))
    assert brand.accents[0] == "#003366" and brand.dark == get_look("kawaii").theme.dark


def test_the_prompts_never_describe_the_old_robot_mascot() -> None:
    texts = [menu(), "\n".join(build_spec(f) for f in FORMATS), CAST, raw("meme_system"), raw("meme_build"), raw("meme_ideas")]
    for text in texts:
        assert not re.search(r"\bbot\b|robot", text, re.IGNORECASE)
    assert "robot" in get_look("inferno_robots").cast.lower()  # the one look that offers robots, on purpose
    assert "ghost" in CAST and MASCOT_SCENE.strip()


def test_the_classic_right_right_format_and_other_new_classics_are_offered() -> None:
    for fmt_id in ("right_right", "always_has_been", "change_my_mind", "shocked_strip", "is_this_a"):
        fmt = get_format(fmt_id)
        assert fmt is not None and fmt.family == "classic" and f"`{fmt_id}`" in menu()
    right = get_format("right_right")
    assert right is not None and len(right.slots) == 4 and "Right?" in right.recognizable + right.slots[3].hint
    p3 = right.slot("p3")
    assert p3 is not None and p3.optional


async def test_a_meme_is_judged_by_a_panel_looked_at_and_gets_a_look() -> None:
    llm = FakeLLM()
    maker = MemeMaker(llm, Settings())
    first = await maker.make("", POST, ART, meme_format="nope_yep")
    state = load_state(first.spec)
    assert state and state["look"] and len(state["panel"]["scores"]) == 5
    assert llm.tasks()[:2] == ["meme ideas", "meme panel"]
    assert "meme review" in llm.tasks() and state["review"]["verdict"] == "passed"
    # An art-free format has nothing to review.
    llm2 = FakeLLM()
    free = await MemeMaker(llm2, Settings()).make("", POST, ART, meme_format="terminal")
    assert "meme review" not in llm2.tasks() and "review" not in (load_state(free.spec) or {})
    # The author's pick sticks, and a redraw moves to a different look.
    picked = await maker.make(first.spec, POST, ART, redraw=True, look="kawaii")
    assert (load_state(picked.spec) or {})["look"] == "kawaii"
    again = await maker.make(picked.spec, POST, ART, redraw=True)
    assert (load_state(again.spec) or {})["look"] != "kawaii"
    # Retyping the words keeps the look and calls no model.
    before = len(llm.calls)
    worded = maker.reword(again.spec, {"nope": "Short"}, ART)
    assert (load_state(worded.spec) or {})["look"] == (load_state(again.spec) or {})["look"] and len(llm.calls) == before


class PanelLLM(FakeLLM):
    """The panel prefers the third pitch, rules out the first, and may offer new words for the winner."""

    def __init__(self, punch: list[dict[str, str]] | None = None, fail: bool = False) -> None:
        super().__init__()
        self.punch, self.fail = punch, fail

    async def structured(self, *, task: str, schema: type[BaseModel], **kwargs: Any) -> Any:
        if schema is MemeVerdict:
            self.calls.append({"kind": "structured", "task": task, "prompt": kwargs.get("prompt", "")})
            if self.fail:
                raise LLMError("panel down")
            scores = [
                {
                    "concept": i,
                    "feed_reader": 9 if i == 2 else 5,
                    "comedy_editor": 6,
                    "author": 6,
                    "gets_it": 2 if i == 0 else 8,
                    "note": "n",
                }
                for i in range(5)
            ]
            return MemeVerdict.model_validate({"scores": scores, "chosen": 2, "punch_up": self.punch or [], "summary": "Third is best."})
        return await super().structured(task=task, schema=schema, **kwargs)


async def test_the_panel_overrides_the_writers_choice_and_its_punch_up_is_applied_only_within_limits() -> None:
    result = await MemeMaker(PanelLLM(), Settings()).make("", POST, ART, meme_format="venn")
    state = load_state(result.spec)
    assert state and state["chosen"] == 2 and state["panel"]["scores"][0] < 0 and state["why"] == "Third is best."

    words = {**DEMO_MEME_TEXTS["venn"], "center": "Pizza, again"}
    ok = [{"slot": s, "text": t, "speaker": ""} for s, t in words.items()]
    sharp = await MemeMaker(PanelLLM(punch=ok), Settings()).make("", POST, ART, meme_format="venn")
    sharp_state = load_state(sharp.spec)
    assert sharp_state and sharp_state["panel"]["punched_up"] and "Pizza, again" in sharp.alt
    too_long = [{**t, "text": "x" * 300} for t in ok]
    unchanged = load_state((await MemeMaker(PanelLLM(punch=too_long), Settings()).make("", POST, ART, meme_format="venn")).spec)
    assert unchanged and not unchanged["panel"]["punched_up"]


async def test_a_failing_panel_falls_back_to_the_writers_own_scores() -> None:
    result = await MemeMaker(PanelLLM(fail=True), Settings()).make("", POST, ART, meme_format="nope_yep")
    state = load_state(result.spec)
    assert state and state["chosen"] == 0 and "panel" not in state and result.png.startswith(b"\x89PNG")


class ReviewLLM(FakeLLM):
    def __init__(self, reviews: list[dict[str, Any]], unsupported: bool = False) -> None:
        super().__init__()
        self.reviews, self.unsupported = list(reviews), unsupported

    async def structured(self, *, task: str, schema: type[BaseModel], **kwargs: Any) -> Any:
        if schema is MemeReview:
            self.calls.append({"kind": "structured", "task": task, "prompt": kwargs.get("prompt", ""), "images": kwargs.get("images")})
            if self.unsupported:
                raise LLMImagesUnsupportedError()
            return MemeReview.model_validate(self.reviews.pop(0))
        return await super().structured(task=task, schema=schema, **kwargs)


BAD = {"passes": False, "funny": 3, "craft": 3, "problems": ["The ghost covers the label"], "fix": "Move the ghost left"}
GOOD = {"passes": True, "funny": 8, "craft": 8, "problems": [], "fix": ""}


async def test_a_meme_that_reads_badly_is_redrawn_once_and_the_better_one_is_kept() -> None:
    llm = ReviewLLM([BAD, GOOD])
    result = await MemeMaker(llm, Settings()).make("", POST, ART, meme_format="nope_yep")
    assert llm.tasks().count("meme review") == 2 and llm.tasks().count("meme edit (nope_yep)") == 1
    assert "Move the ghost left" in next(c for c in llm.calls if c["task"] == "meme edit (nope_yep)")["prompt"]
    assert (load_state(result.spec) or {})["review"]["verdict"] == "redrawn"
    assert all(c["images"] for c in llm.calls if c["task"] == "meme review")

    worse = ReviewLLM([BAD, {**BAD, "funny": 1, "craft": 1}])
    kept = await MemeMaker(worse, Settings()).make("", POST, ART, meme_format="nope_yep")
    assert worse.tasks().count("meme edit (nope_yep)") == 1 and (load_state(kept.spec) or {})["review"]["verdict"] == "kept"


async def test_the_review_is_skipped_when_images_cannot_be_sent_or_when_asked() -> None:
    llm = ReviewLLM([], unsupported=True)
    result = await MemeMaker(llm, Settings()).make("", POST, ART, meme_format="nope_yep")
    assert (load_state(result.spec) or {})["review"]["skipped"] is True and "meme edit (nope_yep)" not in llm.tasks()
    off = FakeLLM()
    await MemeMaker(off, Settings()).make("", POST, ART, meme_format="nope_yep", review=False)
    assert "meme review" not in off.tasks()
