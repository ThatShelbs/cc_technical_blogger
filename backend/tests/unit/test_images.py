from __future__ import annotations

import json
from pathlib import Path

import pytest

from proseferno.db import Persona
from proseferno.demo import CHART_SPEC, DIAGRAM_SVG, png_bytes
from proseferno.images import ImageProviderError, credit_line, model_label
from proseferno.images.base import draw_with_retry
from proseferno.images.render import (
    FONT_DIR,
    ILLUSTRATIVE,
    add_meme_text,
    mark_illustrative,
    placeholder_png,
    prepare_vega_spec,
    sanitize_svg,
    svg_to_png,
    vega_to_png,
)
from proseferno.images.service import image_context, image_guidance


def test_svg_sanitizer_removes_scripts_handlers_and_external_refs() -> None:
    dirty = (
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 10 10" onload="x()">'
        "<script>alert(1)</script><foreignObject><div/></foreignObject>"
        '<image xlink:href="https://evil.example/a.png"/><use href="#ok"/><rect onclick="y()" fill="url(https://e/x)"/></svg>'
    )
    clean = sanitize_svg(dirty)

    for banned in ("script", "foreignObject", "onload", "onclick", "evil.example", "url(https"):
        assert banned not in clean
    assert 'href="#ok"' in clean


def test_svg_must_be_svg() -> None:
    with pytest.raises(ImageProviderError):
        sanitize_svg("<html></html>")


def test_renderers_produce_png() -> None:
    for png, width, _height in (svg_to_png(DIAGRAM_SVG, width=400), vega_to_png(CHART_SPEC), placeholder_png("Console settings")):
        assert png.startswith(b"\x89PNG")
        assert width > 0
    assert add_meme_text(png_bytes(300, 200), "top", "bottom").startswith(b"\x89PNG")


def test_charts_reject_remote_data() -> None:
    with pytest.raises(ImageProviderError):
        vega_to_png({"data": {"url": "https://example.com/data.csv"}, "mark": "bar"})


def test_credit_line_uses_persona_template() -> None:
    persona = Persona(name="Shelby", display_name="Shelby Temple")
    assert credit_line(persona, "claude-svg") == "Author: Shelby Temple; Made with Claude Opus 5.5 (SVG)"
    assert credit_line(persona, "claude-svg", "claude-sonnet-5-5") == "Author: Shelby Temple; Made with Claude Sonnet 5.5 (SVG)"
    assert credit_line(persona, "upload") == "Image by Shelby Temple"
    persona.credit_template = "Image: {name} ({tool})"
    assert credit_line(persona, "vega-lite") == "Image: Shelby Temple (Claude Opus 5.5 + Vega-Lite)"
    persona.credit_template = "{oops}"
    assert credit_line(persona, "vega-lite").startswith("Author: Shelby Temple")


def test_image_context_marks_position() -> None:
    markdown = "Intro text.\n\n{{image:hero}}\n\nBefore.\n\n{{image:img2}}\n\nAfter."
    context = image_context(markdown, "img2")
    assert ">>> IMAGE HERE <<<" in context
    assert "{{image:" not in context


def test_image_guidance_extracts_section() -> None:
    voice_profile = "# V\n\n## Images & Captions\nCaptions say Source.\n\n## Lexicon\nwords"
    assert image_guidance(voice_profile) == "Captions say Source."


def test_model_label() -> None:
    assert model_label("claude-opus-5-5") == "Claude Opus 5.5"
    assert model_label("claude-fable-5-1") == "Claude Fable 5.1"
    assert model_label("my-custom-model") == "my-custom-model"


def test_fonts_are_bundled_so_images_look_the_same_everywhere() -> None:
    from proseferno.images.memes.text import _FILES, font_path

    for role, files in _FILES.items():
        path = font_path(role)
        assert path is not None and Path(path).parent == FONT_DIR and Path(path).name == files[0], role


def test_slightly_broken_svg_is_repaired_instead_of_rejected() -> None:
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10"/><text>R&D</text><g></svg>'
    assert "<rect" in sanitize_svg(svg) and svg_to_png(svg, width=40)[0].startswith(b"\x89PNG")
    # Repair never lets banned content through.
    assert "script" not in sanitize_svg('<svg xmlns="http://www.w3.org/2000/svg"><script>x()</script><g onclick="y()">&</svg>')
    with pytest.raises(ImageProviderError):
        sanitize_svg("not xml at all")


def test_charts_take_the_brand_palette_and_say_when_data_is_illustrative() -> None:
    spec = json.loads(CHART_SPEC)
    assert prepare_vega_spec(spec)["config"]["range"]["category"][0] == "#781c6d"
    branded = prepare_vega_spec(spec, ("#003366", "#00aa88", "#ffcc00"))
    assert branded["config"]["range"]["category"] == ["#003366", "#00aa88", "#ffcc00"] and branded["config"]["mark"]["color"] == "#003366"
    assert prepare_vega_spec(spec, ("#003366",))["config"]["range"]["category"][0] == "#781c6d"  # too few colors to be a palette

    assert mark_illustrative({"title": "Accuracy"})["title"] == {"text": "Accuracy", "subtitle": ILLUSTRATIVE}
    assert mark_illustrative({"title": {"text": "A", "subtitle": "By type"}})["title"]["subtitle"] == ["By type", ILLUSTRATIVE]
    assert mark_illustrative({"title": "Accuracy (illustrative)"})["title"] == {"text": "Accuracy (illustrative)"}
    assert mark_illustrative({})["title"]["subtitle"] == ILLUSTRATIVE
    assert vega_to_png(spec, illustrative=True)[0] != vega_to_png(spec)[0]


async def test_draw_with_retry_quotes_the_problems_back_once() -> None:
    notes: list[str] = []

    async def ask(note: str) -> int:
        notes.append(note)
        return len(notes)

    def draw(design: int, last: bool) -> str:
        if design == 1:
            raise ImageProviderError("Text overflows.\nNo title.")
        return f"drawn {design} {last}"

    assert await draw_with_retry(ask, draw) == (2, "drawn 2 True")
    assert notes[0] == "" and "- Text overflows.\n- No title." in notes[1]

    def never(design: int, last: bool) -> str:
        raise ImageProviderError(f"still broken {design}")

    with pytest.raises(ImageProviderError, match="still broken 4"):
        await draw_with_retry(ask, never)


def test_rich_svg_features_render() -> None:
    from proseferno.demo import HERO_SVG

    png, width, height = svg_to_png(HERO_SVG, width=800)
    assert png[1:4] == b"PNG" and (width, height) == (800, 450)
