from __future__ import annotations

import io
import json
from typing import Any

import pytest
from PIL import Image, ImageDraw
from pydantic import BaseModel

from proseferno.config import Settings
from proseferno.demo import FakeLLM, meme_build_payload
from proseferno.images import ImageProviderError
from proseferno.images.memes import FORMATS, ArtDirection, MemeContext, MemeMaker, get_format, load_state, plan_callbacks
from proseferno.images.memes.compose import compose, region_svg
from proseferno.images.memes.formats import ArtRegion, build_spec, menu
from proseferno.images.memes.specs import MemeBuild
from proseferno.images.memes.text import STYLES, fit_text

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
    assert len(FORMATS) == 18 and len({f.id for f in FORMATS}) == 18
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
    svg = region_svg(region, '<defs><linearGradient id="g"/></defs><rect fill="url(#g)"/><use href="#bot"/><script>x()</script>')
    assert 'id="r-p1-g"' in svg and "url(#r-p1-g)" in svg and 'href="#bot"' in svg
    png, _, _ = render(
        "classic_caption", art=[{"region": "scene", "svg": '<rect width="10" height="10" onclick="x()"/><script>alert(1)</script>'}]
    )
    assert png.startswith(b"\x89PNG")
    with pytest.raises(ImageProviderError):
        render("classic_caption", art=[{"region": "scene", "svg": "<rect"}])


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
    assert llm.tasks().count("meme ideas") == 2 and "already used" in llm.calls[-2]["prompt"]


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
    assert state and state["format"] == "classic_caption" and llm_first.png.startswith(b"\x89PNG")


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
