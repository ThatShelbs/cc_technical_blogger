from __future__ import annotations

import io
import json
import random
import re
from dataclasses import replace
from typing import Any

import pytest
from PIL import Image, ImageDraw
from pydantic import BaseModel

from inferno_ghostwriter.config import Settings
from inferno_ghostwriter.demo import DEMO_MEME_TEXTS, FakeLLM, meme_build_payload, meme_ideas_payload
from inferno_ghostwriter.images import ImageProviderError
from inferno_ghostwriter.images.memes import FORMATS, ArtDirection, MemeContext, MemeMaker, get_format, load_state, plan_callbacks
from inferno_ghostwriter.images.memes.compose import MASCOT_SCENE, compose, region_svg
from inferno_ghostwriter.images.memes.formats import CAST, FALLBACK, ArtRegion, build_spec, menu
from inferno_ghostwriter.images.memes.generate import clip_post, render_build
from inferno_ghostwriter.images.memes.looks import BY_ID as BY_LOOK
from inferno_ghostwriter.images.memes.looks import LOOKS, choose_look, get_look, theme_for, themed
from inferno_ghostwriter.images.memes.looks import menu as looks_menu
from inferno_ghostwriter.images.memes.specs import MemeBuild, MemeText
from inferno_ghostwriter.images.memes.stagings import COMICS, STAGINGS
from inferno_ghostwriter.images.memes.text import STYLES, fit_text
from inferno_ghostwriter.images.palettes import RAMPS, SURFACES, scheme
from inferno_ghostwriter.images.panel import FinalPick, SeatVerdict
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
    assert len(FORMATS) == 26 and len({f.id for f in FORMATS}) == 26
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
    # An older meme with freehand art regions still composes safely (scripts and handlers never survive).
    legacy = replace(FALLBACK, regions=(ArtRegion("scene", (0, 0, 1080, 1080), ""),), staged=False)
    texts = {"bottom": MemeText(slot="bottom", text="Bottom", speaker="")}
    png, _, _ = compose(legacy, texts, {"scene": '<rect width="10" height="10" onclick="x()"/><script>alert(1)</script>'})
    assert png.startswith(b"\x89PNG")
    # A slip a browser would forgive (a bare ampersand, an unclosed tag) is repaired, not sent back to Claude.
    repaired, _, _ = compose(legacy, texts, {"scene": '<g><rect width="9" height="9" fill="red"/><title>R&D</title>'})
    assert repaired.startswith(b"\x89PNG")
    with pytest.raises(ImageProviderError):
        compose(legacy, texts, {"scene": "I could not draw this."})


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
    tasks = llm.tasks()
    assert tasks[0] == "meme ideas" and not any(t.startswith("meme build") for t in tasks)
    assert {t for t in tasks if t.startswith("panel ")} >= {"panel scroller", "panel gets_it", "panel author", "panel final pick"}
    state = load_state(first.spec)
    assert state and state["format"] == "joke_pie_3d" and first.caption == "Pie logic (data: entirely made up)"
    assert "What pie charts are good for" in first.alt and "Showing two slices: 6" in first.alt

    # Another pitch in the same art-free format, and a redraw: still no call to Claude.
    before = len(llm.calls)
    await maker.make(first.spec, POST, ART, rethink=True)
    await maker.make(first.spec, POST, ART, redraw=True)
    assert len(llm.calls) == before

    # A pitch saved before pitches carried chart data cannot be drawn directly, so production is asked.
    old = json.loads(first.spec)
    for concept in old["concepts"]:
        del concept["data"], concept["caption"]
    await maker.make(json.dumps(old), POST, ART, redraw=True)
    assert llm.tasks()[-1] == "meme build (joke_pie_3d)"


async def test_famous_formats_are_staged_by_code_with_no_drawing_call() -> None:
    llm = FakeLLM()
    meme = await MemeMaker(llm, Settings()).make("", POST, ART, meme_format="this_is_fine")
    state = load_state(meme.spec)
    assert state and state["format"] == "this_is_fine" and state["scheme"]
    assert not any(t.startswith("meme build") for t in llm.tasks())
    assert "dog in a little bowler hat" in meme.alt and "calm_one played by a dog" in meme.alt
    # Recasting by instruction restages the meme (words, cast), it never redraws SVG.
    edited = await MemeMaker(llm, Settings()).edit(meme.spec, "Make it a cat instead", ART)
    after = load_state(edited.spec)
    assert after and after["build"]["cast"][0]["kind"] == "cat" and edited.png != meme.png
    assert "<kit>" in next(c for c in llm.calls if c["task"] == "meme edit (this_is_fine)")["prompt"]


def test_every_staged_format_declares_its_signature_and_renders_without_art() -> None:
    staged = [f for f in FORMATS if f.staged]
    assert {"right_right", "this_is_fine", "this_is_fine_2", "expanding_brain", "panik_kalm_panik", "running_away_balloon"} <= {
        f.id for f in staged
    }
    for fmt in staged:
        assert not fmt.regions, fmt.id
        assert fmt.signature or fmt.family == "comic", fmt.id
        assert fmt.id in STAGINGS or fmt.id in COMICS, fmt.id
        assert "Drawn from the kit" in menu(fmt.id)
    right = get_format("right_right")
    assert right is not None and "blank stare" in " ".join(right.signature) and "Cast roles: `confident`" in menu("right_right")


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
    """Pitches fine, but every production build comes back without its chart data."""

    async def structured(self, *, task: str, schema: type[BaseModel], **kwargs: Any) -> Any:
        result = await super().structured(task=task, schema=schema, **kwargs)
        return result.model_copy(update={"data": []}) if schema is MemeBuild else result


async def test_an_undrawable_pitch_falls_back_to_a_pitch_that_needs_no_production() -> None:
    llm = BrokenBuildLLM()
    maker = MemeMaker(llm, Settings())
    ideas = meme_ideas_payload("Only use the format `joke_pie_3d`")
    for concept, fmt in zip(ideas["concepts"][1:], ("terminal", "venn"), strict=False):
        concept.update(format=fmt, texts=[{"slot": s, "text": t, "speaker": ""} for s, t in DEMO_MEME_TEXTS[fmt].items()])
    ideas["concepts"][0]["data"] = []  # an older pitch: production must draw the pie, and it cannot
    ideas["concepts"][2]["scores"]["surprise"] = 5  # the Venn is the best of the rest
    state = {"version": 2, "brief": POST.brief, "concepts": ideas["concepts"], "chosen": 0, "tried": []}

    meme = await maker.make(json.dumps(state), POST, ART, redraw=True)
    builds = [c for c in llm.calls if c["task"].startswith("meme build")]
    assert len(builds) == 2 and "needs 2-6 slices" in builds[1]["prompt"]
    after = load_state(meme.spec)
    assert after and after["format"] == "venn" and after["chosen"] == 2 and after["tried"] == [0, 2]
    assert after["fallback_from"] == "joke_pie_3d" and "Pizza" in meme.alt

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


# -- Looks, schemes, the panel and the render pick ---------------------------------------------------------


def test_looks_take_their_colors_from_the_scheme_and_templates_follow_it() -> None:
    assert len(LOOKS) >= 10 and len({look.id for look in LOOKS}) == len(LOOKS)
    hexa = re.compile(r"^#[0-9a-fA-F]{6}$")
    allowed = {c for ramp in RAMPS.values() for c in ramp} | set(SURFACES.values())
    for look in LOOKS:
        theme = look.theme
        colors = [theme.dark, theme.paper, theme.ink, *theme.accents, *theme.bands]
        assert all(hexa.match(c) for c in colors), look.id
        assert set(theme.accents) <= allowed, look.id  # only inferno, magma or viridis colors
        assert len(theme.accents) == 6 and look.art and look.cast and look.suits
        assert f"`{look.id}`" in looks_menu()
    # The same template painted in different schemes comes out different.
    for fmt_id in ("chat_thread", "joke_pie_3d", "alignment_chart"):
        fmt = get_format(fmt_id)
        assert fmt is not None
        build = MemeBuild.model_validate(meme_build_payload(fmt_id))
        args = (fmt, {t.slot: t for t in build.texts}, {}, "", build.data)
        looks = {
            compose(*args, theme=theme_for(get_look(None), scheme(r, s)), sch=scheme(r, s))[0]
            for r, s in (("inferno", "near_black"), ("magma", "white"), ("viridis", "paper"))
        }
        assert len(looks) == 3, fmt_id


def test_every_format_renders_in_every_look() -> None:
    # Each format in one look, and every look on the formats that use the kit most (a render takes ~0.3s).
    for i, fmt in enumerate(FORMATS):
        build = MemeBuild.model_validate(meme_build_payload(fmt.id))
        look = LOOKS[i % len(LOOKS)]
        assert render_build(fmt, build, (), look)[0].startswith(b"\x89PNG"), (fmt.id, look.id)
    for fmt_id in ("right_right", "comic_grid_4"):
        fmt = get_format(fmt_id)
        assert fmt is not None
        build = MemeBuild.model_validate(meme_build_payload(fmt_id))
        assert len({render_build(fmt, build, (), look)[0] for look in LOOKS}) == len(LOOKS), fmt_id


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
    assert set(brand.accents) <= {"#003366", "#00aa88", "#ffcc00"}
    # The author's taste (look weights) can all but rule a look out.
    taste = {look.id: 0.0 for look in LOOKS if look.id != "blueprint"}
    picks = [choose_look(None, None, (), rng=rng, weights=taste).id for _ in range(40)]
    assert picks.count("blueprint") >= 28


def test_the_ghost_is_the_star_and_robots_are_only_a_cast_option() -> None:
    assert "ghost" in CAST and MASCOT_SCENE.strip()
    for text in (menu(), CAST):
        assert not re.search(r"\bbot\b|robot", text, re.IGNORECASE)
    assert "default star" in raw("meme_system") and "robot" in get_look("inferno_robots").cast.lower()


def test_the_classic_right_right_format_and_other_new_classics_are_offered() -> None:
    for fmt_id in ("right_right", "always_has_been", "change_my_mind", "shocked_strip", "is_this_a", "panik_kalm_panik"):
        fmt = get_format(fmt_id)
        assert fmt is not None and fmt.family == "classic" and f"`{fmt_id}`" in menu()
    right = get_format("right_right")
    assert right is not None and len(right.slots) == 4 and "Right?" in right.slots[3].hint
    p3 = right.slot("p3")
    assert p3 is not None and p3.optional


async def test_a_meme_is_judged_by_a_parallel_panel_on_mixed_models_and_gets_a_look() -> None:
    llm = FakeLLM()
    maker = MemeMaker(llm, Settings())
    first = await maker.make("", POST, ART, meme_format="nope_yep")
    state = load_state(first.spec)
    assert state and state["look"] and len(state["panel"]["scores"]) == 5 and state["panel"]["answered"] == "6/6"
    seats = [c for c in llm.calls if c["task"].startswith("panel ") and c["task"] not in ("panel match", "panel final pick")]
    assert {c["model"] for c in seats} == {"claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"}
    assert {c["effort"] for c in seats} >= {"low", "medium"}
    # Two renders were judged as pictures: the blind reader saw images, the final pick chose.
    assert state["review"]["verdict"] == "passed" and len(state["review"]["candidates"]) == 2
    assert all(c["images"] == 2 for c in llm.calls if c["task"] in ("panel blind_reader", "panel craft", "panel final pick"))
    # The author's pick sticks, and a redraw moves to a different look and scheme, with no panel.
    before = len(llm.calls)
    picked = await maker.make(first.spec, POST, ART, redraw=True, look="kawaii")
    assert (load_state(picked.spec) or {})["look"] == "kawaii" and len(llm.calls) == before
    again = await maker.make(picked.spec, POST, ART, redraw=True)
    assert (load_state(again.spec) or {})["look"] != "kawaii"
    assert (load_state(again.spec) or {})["scheme"] != (load_state(picked.spec) or {})["scheme"]
    worded = maker.reword(again.spec, {"nope": "Short"}, ART)
    assert (load_state(worded.spec) or {})["look"] == (load_state(again.spec) or {})["look"] and len(llm.calls) == before


class PanelLLM(FakeLLM):
    """Seats prefer the third pitch, the cold reader rules out the first, the comedy editor may punch up the winner."""

    def __init__(self, punch: list[dict[str, str]] | None = None, fail: bool = False) -> None:
        super().__init__()
        self.punch, self.fail = punch, fail

    async def structured(self, *, task: str, schema: type[BaseModel], **kwargs: Any) -> Any:
        if schema is SeatVerdict and "nothing is drawn yet" in kwargs.get("prompt", ""):
            self.calls.append({"kind": "structured", "task": task, "prompt": kwargs.get("prompt", ""), "model": kwargs.get("model")})
            if self.fail:
                raise LLMError("seat down")
            scores = [
                {"candidate": i, "score": (2 if i == 0 and task == "panel gets_it" else 9 if i == 2 else 5), "note": "n", "reading": ""}
                for i in range(5)
            ]
            punch = self.punch if task == "panel comedy_editor" else []
            return SeatVerdict.model_validate({"scores": scores, "punch_up": punch or [], "punch_for": 2 if punch else -1})
        return await super().structured(task=task, schema=schema, **kwargs)


async def test_the_panel_overrides_the_writers_choice_and_its_punch_up_is_applied_only_within_limits() -> None:
    settings = Settings(image_render_candidates=1)
    result = await MemeMaker(PanelLLM(), settings).make("", POST, ART, meme_format="venn")
    state = load_state(result.spec)
    assert state and state["chosen"] == 2 and state["panel"]["scores"][0] < 0 and 0 in state["panel"]["vetoed"]

    words = {**DEMO_MEME_TEXTS["venn"], "center": "Pizza, again"}
    ok = [{"slot": s, "text": t} for s, t in words.items()]
    sharp = await MemeMaker(PanelLLM(punch=ok), settings).make("", POST, ART, meme_format="venn")
    sharp_state = load_state(sharp.spec)
    assert sharp_state and sharp_state["panel"]["punched_up"] and "Pizza, again" in sharp.alt
    too_long = [{**t, "text": "x" * 300} for t in ok]
    unchanged = load_state((await MemeMaker(PanelLLM(punch=too_long), settings).make("", POST, ART, meme_format="venn")).spec)
    assert unchanged and not unchanged["panel"]["punched_up"]


async def test_a_failing_panel_falls_back_to_the_writers_own_scores() -> None:
    result = await MemeMaker(PanelLLM(fail=True), Settings()).make("", POST, ART, meme_format="nope_yep")
    state = load_state(result.spec)
    assert state and state["chosen"] in (0, 1) and "panel" not in state and result.png.startswith(b"\x89PNG")


class RenderLLM(FakeLLM):
    """The final pick prefers the second render and may ask for a fix; images may be unsupported."""

    def __init__(self, fix: str = "", unsupported: bool = False) -> None:
        super().__init__()
        self.fix, self.unsupported = fix, unsupported

    async def structured(self, *, task: str, schema: type[BaseModel], **kwargs: Any) -> Any:
        if kwargs.get("images") and self.unsupported:
            self.calls.append({"kind": "structured", "task": task, "prompt": kwargs.get("prompt", "")})
            raise LLMImagesUnsupportedError()
        if schema is FinalPick:
            self.calls.append({"kind": "structured", "task": task, "prompt": kwargs.get("prompt", ""), "images": len(kwargs["images"])})
            return FinalPick(chosen=1, fix=self.fix, why="The second one reads instantly.")
        return await super().structured(task=task, schema=schema, **kwargs)


async def test_the_render_panel_picks_between_drawn_memes_and_may_fix_the_winner() -> None:
    llm = RenderLLM()
    result = await MemeMaker(llm, Settings()).make("", POST, ART)
    state = load_state(result.spec)
    assert state and state["review"]["verdict"] == "passed" and state["chosen"] == state["review"]["candidates"][1]
    assert "Strangers read it as" in next(c for c in llm.calls if c["task"] == "panel match")["prompt"]

    fixer = RenderLLM(fix="Make it a robot")
    staged = await MemeMaker(fixer, Settings()).make("", POST, ART, meme_format="this_is_fine")
    fixed = load_state(staged.spec)
    assert fixed and fixed["review"]["verdict"] == "redrawn" and "meme edit (this_is_fine)" in fixer.tasks()


async def test_the_render_panel_is_skipped_when_images_cannot_be_sent_or_when_asked() -> None:
    llm = RenderLLM(unsupported=True)
    result = await MemeMaker(llm, Settings()).make("", POST, ART, meme_format="nope_yep")
    assert (load_state(result.spec) or {})["review"]["skipped"] is True and "panel final pick" not in llm.tasks()
    off = FakeLLM()
    await MemeMaker(off, Settings()).make("", POST, ART, meme_format="nope_yep", review=False)
    assert not any(t in ("panel blind_reader", "panel final pick") for t in off.tasks())
