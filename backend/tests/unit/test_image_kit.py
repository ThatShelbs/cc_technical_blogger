"""The image overhaul's building blocks: palettes, the character kit, SVG lint, the judging panel and the author's taste."""

from __future__ import annotations

import asyncio
import io
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from pydantic import BaseModel

from inferno_ghostwriter.config import Settings
from inferno_ghostwriter.demo import FakeLLM
from inferno_ghostwriter.images.kit import ACCESSORIES, EXPRESSIONS, KINDS, POSES, STYLES, Character, draw
from inferno_ghostwriter.images.kit.rig import REST_L, REST_R
from inferno_ghostwriter.images.lint import lint
from inferno_ghostwriter.images.opening.feedcard import feed_card
from inferno_ghostwriter.images.opening.scene import LAYOUTS, compose_scene
from inferno_ghostwriter.images.opening.specs import SceneSpec
from inferno_ghostwriter.images.palettes import (
    DARK_SURFACES,
    RAMPS,
    SURFACES,
    brand_scheme,
    choose,
    colors_in,
    from_id,
    house_ramp,
    pick,
    scheme,
    snap_svg,
)
from inferno_ghostwriter.images.panel import FinalPick, Seat, SeatVerdict, convene, final_pick, parse_seats
from inferno_ghostwriter.images.remix import HOUSE, PALETTE, choose_tweaks
from inferno_ghostwriter.images.render import svg_to_png
from inferno_ghostwriter.images.taste import features, taste_of
from inferno_ghostwriter.llm import LLMError, SystemBlock
from inferno_ghostwriter.llm.base import LLMImagesUnsupportedError
from inferno_ghostwriter.llm.claude_code import ClaudeCodeCLI, ClaudeCodeLLM

# -- palettes -----------------------------------------------------------------------------------------------------------


def test_schemes_rotate_through_the_house_ramps_and_surfaces() -> None:
    first = choose(())
    second = choose((first.id,))
    third = choose((second.id, first.id))
    assert len({first.ramp_id, second.ramp_id, third.ramp_id}) == 3  # inferno, magma and viridis take turns
    assert (first.surface_id in DARK_SURFACES) != (second.surface_id in DARK_SURFACES)  # light and dark alternate
    assert choose((), ramp="viridis", dark=True).ramp_id == "viridis" and choose((), dark=False).surface_id not in DARK_SURFACES
    assert from_id("magma:white") == scheme("magma", "white") and from_id("nope:white") is None and from_id(None) is None
    for sch in (scheme(r, s) for r in RAMPS for s in SURFACES):
        assert sch.bg in SURFACES.values() and set(sch.accents) <= set(sch.ramp) and len(sch.accents) == 6
        assert "palette on a" in sch.describe()


def test_a_brand_palette_wins_but_a_house_ramp_from_remix_keeps_the_rotation() -> None:
    brand = pick(("#003366", "#00aa88", "#ffcc00"))
    assert brand.ramp_id == "brand" and set(brand.ramp) == {"#003366", "#00aa88", "#ffcc00"}
    assert house_ramp(RAMPS["magma"]) == "magma" and house_ramp(("#003366", "#00aa88", "#ffcc00")) is None
    assert pick(RAMPS["viridis"]).ramp_id == "viridis"
    assert brand_scheme(("#ffffff",)).ramp_id == "inferno"  # too few colors: the house default


def test_snap_moves_every_color_onto_the_scheme() -> None:
    sch = scheme("viridis", "white")
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><style>.a{fill:#ff00ff}</style>'
        '<rect fill="red" stroke="rgb(10, 200, 30)" width="5" height="5"/><circle style="fill:#123" r="2"/>'
        '<linearGradient id="g"><stop stop-color="#ABCDEF"/></linearGradient><rect fill="url(#g)" width="1" height="1"/></svg>'
    )
    snapped = snap_svg(svg, sch.allowed)
    assert colors_in(snapped) <= {c.lower() for c in sch.allowed}
    assert 'fill="url(#g)"' in snapped and "red" not in snapped


def test_house_only_remixes_never_leave_inferno_magma_or_viridis() -> None:
    picked = {t.id for _ in range(40) for t in choose_tweaks((PALETTE,), house_only=True)}
    assert picked <= set(HOUSE) and len(picked) >= 2


# -- the character kit --------------------------------------------------------------------------------------------------


def test_every_character_expression_pose_and_look_renders_whole() -> None:
    sch = scheme("inferno", "white")
    svgs = []
    for kind in KINDS:
        for k, expression in enumerate(EXPRESSIONS):
            pose = list(POSES)[k % len(POSES)]
            look = list(STYLES)[k % len(STYLES)]
            accessory = ACCESSORIES[k % len(ACCESSORIES)]
            drawn = draw(
                Character(kind, expression, pose, "left" if k % 2 else "right", accessory, "mug", k % 3), 300, 560, 400, sch=sch, look=look
            )
            svgs.append(drawn.svg)
            x0, y0, x1, y1 = drawn.bbox
            assert x1 > x0 and y1 < y0 + 1000 and drawn.anchors["head_top"][1] < drawn.anchors["mouth"][1] < drawn.anchors["feet"][1]
    # One sheet renders (resvg would reject broken markup), and characters have ink on them.
    sheet = "".join(f'<g transform="translate({(i % 12) * 600 - 0},{(i // 12) * 600})">{s}</g>' for i, s in enumerate(svgs[:24]))
    png, _, _ = svg_to_png(f'<svg xmlns="http://www.w3.org/2000/svg" width="7200" height="1200">{sheet}</svg>', width=1800)
    with Image.open(io.BytesIO(png)) as img:
        assert img.convert("L").getextrema()[0] < 60


def test_limbs_start_inside_the_body_so_nothing_floats() -> None:
    from inferno_ghostwriter.images.kit import paint, rig, style

    sch = scheme()
    for kind, builder in (("ghost", rig._ghost), ("dog", rig._dog), ("cat", rig._cat), ("robot", rig._robot)):
        c = style.coat(kind, sch, style.kit_style(None))
        b = builder(c, paint.Painter(style.kit_style(None), c.line, "t"), rig.POSES["stand"])
        _hx, hy, hr = b.head
        for sx, sy in b.shoulders:
            # A shoulder sits inside the body's outline (within its half-width) and below the head's centre.
            assert abs(sx) < b.width and sy > hy, kind
        assert hr > 60 and b.top < hy - hr + 40, kind
    # Animals stand on their front legs at rest: the paws reach the ground.
    assert REST_R.dy > 0 and REST_L.dy > 0


def test_a_scene_places_kit_characters_props_and_one_linted_object() -> None:
    sch = scheme("magma", "charcoal")
    stray = '<circle cx="5000" cy="10" r="4" fill="#00ff00"/>'
    for layout in LAYOUTS:
        spec = SceneSpec(
            layout=layout,
            backdrop="plain",
            characters=[{"kind": "ghost", "expression": "shocked", "pose": "point", "slot": "left"}] if layout != "object" else [],
            props=[{"name": "chart_screen", "slot": "right"}],
            object_svg='<rect x="50" y="50" width="500" height="400" rx="30" fill="#ff0000"/>' + stray,
            labels=[{"text": "The object", "slot": "object"}],
            alt="a",
            caption="c",
        )
        png, width, height, problems = compose_scene(spec, sch)
        assert (width, height) == (1600, 900) and problems == [], layout
    card = feed_card(png, "A very long title that has to fit under the thumbnail in a feed card")
    with Image.open(io.BytesIO(card)) as img:
        assert img.size == (1200, 780)


# -- lint ---------------------------------------------------------------------------------------------------------------


def test_lint_removes_strays_and_reports_dead_references_and_text_outside_the_band() -> None:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900">'
        '<rect width="1600" height="900" fill="#000004"/>'
        '<circle cx="800" cy="450" r="200" fill="url(#missing)"/>'
        '<rect x="1900" y="20" width="40" height="40" fill="#fff"/>'  # off canvas
        '<circle cx="60" cy="860" r="2" fill="#fff"/>'  # a lone stray mark
        + "".join(f'<circle cx="{300 + i * 9}" cy="300" r="2" fill="#fff"/>' for i in range(6))  # a deliberate cluster
        + '<text x="100" y="40" font-size="40">Too high</text></svg>'
    )
    report = lint(svg, size=(1600, 900), safe_band=(130, 770), allowed_colors=scheme().allowed)
    assert report.removed == 2 and report.svg.count("<circle") == 7
    assert any("missing" in p for p in report.problems) and any("Too high" in p for p in report.problems)
    budget = lint('<svg xmlns="http://www.w3.org/2000/svg">' + '<rect width="1" height="1"/>' * 30 + "</svg>", size=(10, 10), budget=20)
    assert any("shapes" in p for p in budget.problems)


# -- the panel ----------------------------------------------------------------------------------------------------------


class SlowLLM(FakeLLM):
    """Every seat takes a while; one seat fails, one cannot see images."""

    async def structured(self, *, task: str, schema: type[BaseModel], **kwargs: Any) -> Any:
        if schema is SeatVerdict:
            await asyncio.sleep(0.3)
            if task == "panel author":
                raise LLMError("author seat down")
        return await super().structured(task=task, schema=schema, **kwargs)


async def test_seats_run_at_once_on_their_own_models_and_a_failed_seat_is_dropped() -> None:
    llm = SlowLLM()
    seats = parse_seats(["scroller:haiku:low", "gets_it:haiku:low", "comedy_editor:sonnet:medium", "author:opus:high", "bogus:x:y"])
    assert [s.role for s in seats] == ["scroller", "gets_it", "comedy_editor", "author"]
    started = time.monotonic()
    result = await convene(llm, seats, context="ctx", candidates=["a", "b", "c"])
    assert time.monotonic() - started < 0.9  # four 0.3s seats in parallel, not 1.2s in a row
    assert result.ok and result.answered == 3 and result.asked == 4 and len(result.totals) == 3
    calls = {c["task"]: c for c in llm.calls if c["task"].startswith("panel ")}
    assert calls["panel scroller"]["model"] == "claude-haiku-5-5" and calls["panel comedy_editor"]["effort"] == "medium"
    assert result.best() == 0 and result.ranking()[0] == 0


class VetoLLM(FakeLLM):
    async def structured(self, *, task: str, schema: type[BaseModel], **kwargs: Any) -> Any:
        if schema is SeatVerdict:
            low = 2 if task == "panel gets_it" else 9
            return SeatVerdict(scores=[{"candidate": i, "score": low if i == 0 else 6, "note": "n"} for i in range(2)])  # type: ignore[list-item]
        return await super().structured(task=task, schema=schema, **kwargs)


async def test_a_veto_rules_a_candidate_out_whatever_the_other_seats_say() -> None:
    result = await convene(VetoLLM(), parse_seats(["scroller:haiku:low", "gets_it:haiku:low"]), context="", candidates=["a", "b"])
    assert 0 in result.vetoed and result.totals[0] < 0 < result.totals[1] and result.best() == 1


class BlindLLM(FakeLLM):
    """Blind readers see pictures; images may be unsupported (headless Claude Code)."""

    def __init__(self, unsupported: bool = False) -> None:
        super().__init__()
        self.unsupported = unsupported

    async def structured(self, *, task: str, schema: type[BaseModel], **kwargs: Any) -> Any:
        if kwargs.get("images") and self.unsupported:
            raise LLMImagesUnsupportedError()
        return await super().structured(task=task, schema=schema, **kwargs)


async def test_blind_readings_are_matched_against_what_each_picture_meant() -> None:
    llm = BlindLLM()
    seats = parse_seats(["blind_reader:haiku:low", "craft:sonnet:medium"])
    result = await convene(llm, seats, context="ctx", candidates=["x", "y"], images=[b"1", b"2"], intents=["one", "two"])
    assert result.readings[0] and result.match == [8, 8]
    blind = next(c for c in llm.calls if c["task"] == "panel blind_reader")
    assert "ctx" not in blind["prompt"] and blind["images"] == 2  # a stranger: no context, only the pictures
    pick_ = await final_pick(llm, context="ctx", candidates=["x", "y"], images=[b"1", b"2"], panel=result)
    assert isinstance(pick_, FinalPick) and pick_.chosen == 0
    none = await convene(BlindLLM(unsupported=True), seats, context="", candidates=["x"], images=[b"1"])
    assert none.answered == 0 and not none.ok
    assert await final_pick(BlindLLM(unsupported=True), context="", candidates=["x"], images=[b"1"], panel=None) is None


def test_seat_specs_and_settings_line_up() -> None:
    settings = Settings()
    for specs in (settings.image_panel_meme, settings.image_panel_opening, settings.image_panel_render):
        assert len(parse_seats(specs)) == len(specs)
    assert {s.model for s in parse_seats(settings.image_panel_meme)} == {"haiku", "sonnet", "opus"}
    assert Seat("author", "opus", "high").model_id == "claude-opus-5-5"


FAKE = Path(__file__).parents[1] / "fixtures" / "fake_claude.py"


class Plan(BaseModel):
    title: str


async def test_a_seat_runs_on_its_own_model_through_claude_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    record = tmp_path / "call.json"
    monkeypatch.setenv("FAKE_CLAUDE_RECORD", str(record))
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "structured")
    monkeypatch.setenv("FAKE_CLAUDE_PAYLOAD", json.dumps({"title": "x"}))
    llm = ClaudeCodeLLM(Settings(_env_file=None), ClaudeCodeCLI([sys.executable, str(FAKE)]))  # type: ignore[call-arg]
    await llm.structured(task="t", system=[SystemBlock("s")], prompt="p", schema=Plan, effort="low", model="claude-haiku-5-5")
    args = json.loads(record.read_text(encoding="utf-8"))["args"]
    assert args[args.index("--model") + 1] == "claude-haiku-5-5"


def test_the_api_backend_sends_the_seat_model_and_skips_fallbacks_on_haiku() -> None:
    from inferno_ghostwriter.llm.claude import ClaudeLLM

    llm = ClaudeLLM(Settings(), lambda: None)  # type: ignore[arg-type, return-value]
    haiku = llm._common([SystemBlock("s")], "low", 1000, "claude-haiku-5-5")
    default = llm._common([SystemBlock("s")], "low", 1000)
    assert haiku["model"] == "claude-haiku-5-5" and "fallbacks" not in haiku
    assert default["model"] == "claude-opus-5-5" and default.get("fallbacks") == "default"


# -- taste ----------------------------------------------------------------------------------------------------------------


def test_the_authors_thumbs_become_look_weights_and_prompt_notes() -> None:
    meme = json.dumps(
        {"version": 2, "format": "this_is_fine", "look": "kawaii", "scheme": "magma:white", "build": {"cast": [{"kind": "dog"}]}}
    )
    other = json.dumps({"version": 2, "format": "venn", "look": "blueprint"})
    hero = json.dumps({"room": "opening", "style": "editorial", "scene": {"characters": [{"kind": "cat"}]}})
    assert features("meme", meme) == ["format:this_is_fine", "look:kawaii", "cast:dog", "ramp:magma"]
    taste = taste_of([("meme", meme, 1), ("meme", meme, 1), ("meme", other, -1), ("hero", hero, 1), ("meme", other, 0)])
    weights = taste.look_weights()
    assert weights["kawaii"] > 1.5 and weights["blueprint"] < 1
    note = taste.note(("format", "look", "cast"))
    assert re.search(r"liked .*this is fine", note) and "turned down" in note and "venn" in note
    assert "editorial" in taste.note(("style",)) and taste_of([]).empty


def test_snap_leaves_css_id_selectors_alone() -> None:
    sch = scheme("inferno", "white")
    snapped = snap_svg("<svg><style>#add { fill: #00ff00 } #bad{stroke:#0000ff}</style></svg>", sch.allowed)
    assert "#add" in snapped and "#bad" in snapped and "#00ff00" not in snapped


async def test_the_final_pick_reads_scores_before_vetoes() -> None:
    llm = VetoLLM()
    result = await convene(llm, parse_seats(["scroller:haiku:low", "gets_it:haiku:low"]), context="", candidates=["a", "b"])
    assert result.raw[0] > 0 > result.totals[0] and result.summary()["totals"][0] > 0
    await final_pick(llm, context="", candidates=["a", "b"], images=[b"1", b"2"], panel=result)
    prompt = next(c for c in llm.calls if c["task"] == "panel final pick")["prompt"]
    assert "-9" not in prompt and "(ruled out)" in prompt
