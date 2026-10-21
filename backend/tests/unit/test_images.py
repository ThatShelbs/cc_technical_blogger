from __future__ import annotations

import base64

import httpx
import pytest

from proseferno.db import Persona
from proseferno.demo import CHART_SPEC, DIAGRAM_SVG, png_bytes
from proseferno.images import CloudflareFluxProvider, ImageProviderError, credit_line
from proseferno.images.base import ImageProviderNotConfiguredError
from proseferno.images.render import add_meme_text, placeholder_png, sanitize_svg, svg_to_png, vega_to_png
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
    assert credit_line(persona, "cloudflare-flux") == "Author: Shelby Temple; Made with FLUX.2 [klein] on Cloudflare Workers AI"
    assert credit_line(persona, "upload") == "Image by Shelby Temple"
    persona.credit_template = "Image: {name} ({tool})"
    assert credit_line(persona, "vega-lite") == "Image: Shelby Temple (Claude + Vega-Lite)"
    persona.credit_template = "{oops}"
    assert credit_line(persona, "vega-lite").startswith("Author: Shelby Temple")


def test_image_context_marks_position() -> None:
    markdown = "Intro text.\n\n{{image:hero}}\n\nBefore.\n\n{{image:img2}}\n\nAfter."
    context = image_context(markdown, "img2")
    assert ">>> IMAGE HERE <<<" in context
    assert "{{image:" not in context


def test_image_guidance_extracts_section() -> None:
    soul = "# V\n\n## Images & Captions\nCaptions say Source.\n\n## Lexicon\nwords"
    assert image_guidance(soul) == "Captions say Source."


async def test_cloudflare_provider_sends_multipart_and_decodes() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = request.content.decode("latin-1")
        return httpx.Response(200, json={"success": True, "result": {"image": base64.b64encode(png_bytes(32, 16)).decode()}})

    provider = CloudflareFluxProvider(account_id=lambda: "acct", api_token=lambda: "tok", transport=httpx.MockTransport(handler))
    image = await provider.generate("a robot", width=1600, height=900, seed=7)

    assert seen["url"].endswith("/accounts/acct/ai/run/@cf/black-forest-labs/flux-2-klein-4b")
    assert seen["auth"] == "Bearer tok"
    body = str(seen["body"])
    assert 'name="prompt"' in body and "a robot" in body and 'name="seed"' in body
    assert 'name="height"\r\n\r\n896' in body  # snapped to a multiple of 16
    assert (image.width, image.height, image.seed) == (32, 16, 7)


async def test_cloudflare_errors_are_friendly() -> None:
    provider = CloudflareFluxProvider(
        account_id=lambda: "acct",
        api_token=lambda: "bad",
        transport=httpx.MockTransport(lambda r: httpx.Response(403, json={"success": False})),
    )
    with pytest.raises(ImageProviderError, match="Workers AI"):
        await provider.generate("x", width=512, height=512, seed=1)

    unconfigured = CloudflareFluxProvider(account_id=lambda: None, api_token=lambda: None)
    assert not unconfigured.is_configured()
    with pytest.raises(ImageProviderNotConfiguredError):
        await unconfigured.generate("x", width=512, height=512, seed=1)
