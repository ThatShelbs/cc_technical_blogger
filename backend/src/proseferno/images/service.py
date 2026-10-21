"""Design and render every image in a post, with credits and redraw history."""

from __future__ import annotations

import random
import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Engine
from sqlmodel import Session

from proseferno.config import Settings
from proseferno.db import Persona, ProjectImage
from proseferno.images.base import ImageProviderError, RasterProvider
from proseferno.images.render import add_meme_text, placeholder_png, svg_to_png, vega_to_png
from proseferno.images.specs import ChartSpec, MemeSpec, RasterSpec, SvgSpec
from proseferno.llm import LLM, LLMError, SystemBlock
from proseferno.llm.base import UsageSink
from proseferno.prompts import raw, render
from proseferno.storage import Storage

RASTER_KINDS = {"hero", "illustration", "meme"}
SIZES = {"hero": (1600, 896), "illustration": (1280, 720), "meme": (1024, 1024)}
TOOL_LABELS = {
    "cloudflare-flux": "FLUX.2 [klein] on Cloudflare Workers AI",
    "claude-svg": "Claude (SVG)",
    "vega-lite": "Claude + Vega-Lite",
    "placeholder": "Proseferno",
}
PLACEHOLDER_RE = re.compile(r"\{\{image:([A-Za-z0-9_\-]+)\}\}")


class SvgMemeSpec(SvgSpec):
    top_text: str
    bottom_text: str


def credit_line(persona: Persona, provider: str) -> str:
    name = persona.display_name or persona.name
    if provider == "upload":
        return f"Image by {name}"
    tool = TOOL_LABELS.get(provider, provider)
    try:
        return persona.credit_template.format(name=name, tool=tool)
    except (KeyError, IndexError, ValueError):
        return f"Author: {name}; Made with {tool}"


def image_context(markdown: str, slot_id: str, before: int = 1500, after: int = 700) -> str:
    marker = f"{{{{image:{slot_id}}}}}"
    index = markdown.find(marker)
    if index < 0:
        return markdown[:before]
    start = max(0, index - before)
    snippet = markdown[start:index] + ">>> IMAGE HERE <<<" + markdown[index + len(marker) : index + len(marker) + after]
    return PLACEHOLDER_RE.sub("", snippet).strip()


def image_guidance(voice_soul: str) -> str:
    match = re.search(r"^##\s+Images.*?$(.*?)(?=^##\s|\Z)", voice_soul, flags=re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else "Use clear, relevant images with short captions and a credit."


class ImageService:
    def __init__(self, *, engine: Engine, llm: LLM, settings: Settings, storage: Storage, raster: RasterProvider) -> None:
        self.engine = engine
        self.llm = llm
        self.settings = settings
        self.storage = storage
        self.raster = raster

    async def create(
        self,
        image_id: int,
        *,
        persona: Persona,
        title: str,
        markdown: str,
        voice_soul: str,
        redraw: bool = False,
        rethink: bool = False,
        usage: UsageSink | None = None,
    ) -> ProjectImage:
        """Design (when needed) and render one image, then persist the result."""
        with Session(self.engine) as session:
            image = session.get(ProjectImage, image_id)
            if image is None:
                raise KeyError(image_id)
        try:
            updates = await self._produce(
                image,
                persona=persona,
                title=title,
                markdown=markdown,
                voice_soul=voice_soul,
                redraw=redraw,
                rethink=rethink,
                usage=usage,
            )
            updates["status"] = "placeholder" if image.kind == "screenshot" else "ready"
            updates["error"] = None
        except (ImageProviderError, LLMError) as exc:
            updates = {"status": "error", "error": str(exc)}
        return self._save(image_id, updates)

    def save_upload(self, image_id: int, png: bytes, width: int, height: int, persona: Persona) -> ProjectImage:
        with Session(self.engine) as session:
            image = session.get(ProjectImage, image_id)
            if image is None:
                raise KeyError(image_id)
        file_name = self._write(image.project_id, image.slot_id, png)
        return self._save(
            image_id,
            {
                "file_name": file_name,
                "provider": "upload",
                "seed": None,
                "width": width,
                "height": height,
                "credit": credit_line(persona, "upload"),
                "status": "ready",
                "error": None,
            },
        )

    def revert(self, image_id: int, index: int) -> ProjectImage:
        with Session(self.engine) as session:
            image = session.get(ProjectImage, image_id)
            if image is None:
                raise KeyError(image_id)
            if not 0 <= index < len(image.history):
                raise IndexError(index)
            entry = image.history[index]
        fields: dict[str, Any] = {
            k: entry[k]
            for k in ("file_name", "provider", "seed", "prompt", "spec", "alt", "caption", "credit", "width", "height")
            if k in entry
        }
        return self._save(image_id, {**fields, "status": "ready", "error": None}, record=False)

    # -- internals -------------------------------------------------------------

    async def _produce(
        self,
        image: ProjectImage,
        *,
        persona: Persona,
        title: str,
        markdown: str,
        voice_soul: str,
        redraw: bool,
        rethink: bool,
        usage: UsageSink | None,
    ) -> dict[str, Any]:
        kind = image.kind
        if kind == "screenshot":
            png, w, h = placeholder_png(image.purpose or image.prompt)
            return self._result(image, png, w, h, "placeholder", persona, alt=image.purpose, caption=image.caption or image.purpose)

        seed = random.randint(1, 2**31 - 1)
        use_flux = kind in RASTER_KINDS and self.raster.is_configured()

        # A plain redraw of a FLUX image keeps the prompt and only changes the seed.
        if redraw and not rethink and use_flux and image.prompt and image.provider == "cloudflare-flux":
            width, height = SIZES[kind]
            rendered = await self.raster.generate(image.prompt, width=width, height=height, seed=seed)
            png = rendered.png
            if kind == "meme":
                captions = _meme_captions(image.spec)
                png = add_meme_text(png, captions.get("top", ""), captions.get("bottom", ""))
            return self._result(image, png, rendered.width, rendered.height, "cloudflare-flux", persona, seed=seed)

        variation = ""
        if redraw:
            variation = (
                f"This is a redraw: create a clearly different take from the previous version (previous caption: {image.caption!r})."
            )
        prompt = render(
            "image_spec",
            kind=kind,
            slot_id=image.slot_id,
            title=title,
            purpose=image.purpose,
            brief=image.prompt or image.purpose,
            visual_style=persona.visual_style or "warm editorial illustration in inferno tones",
            variation=variation,
            image_guidance=image_guidance(voice_soul),
            context=image_context(markdown, image.slot_id),
        )
        system = [SystemBlock(raw("image_system"), cache=True)]

        async def design(schema: type[Any], extra: str = "") -> Any:
            return await self.llm.structured(
                task=f"{kind} image design",
                system=system,
                prompt=prompt + extra,
                schema=schema,
                effort=self.settings.effort_images,
                usage=usage,
            )

        if use_flux:
            width, height = SIZES[kind]
            if kind == "meme":
                meme = await design(MemeSpec)
                rendered = await self.raster.generate(meme.prompt, width=width, height=height, seed=seed)
                png = add_meme_text(rendered.png, meme.top_text, meme.bottom_text)
                spec = _meme_spec_json(meme.top_text, meme.bottom_text)
                return self._result(
                    image,
                    png,
                    rendered.width,
                    rendered.height,
                    "cloudflare-flux",
                    persona,
                    seed=seed,
                    prompt=meme.prompt,
                    spec=spec,
                    alt=meme.alt,
                    caption=meme.caption,
                )
            raster = await design(RasterSpec)
            rendered = await self.raster.generate(raster.prompt, width=width, height=height, seed=seed)
            return self._result(
                image,
                rendered.png,
                rendered.width,
                rendered.height,
                "cloudflare-flux",
                persona,
                seed=seed,
                prompt=raster.prompt,
                alt=raster.alt,
                caption=raster.caption,
            )

        if kind == "chart":
            chart = await design(ChartSpec)
            png, w, h = vega_to_png(chart.vega_lite_json)
            caption = chart.caption
            if chart.data_is_illustrative and "illustrative" not in caption.lower():
                caption = f"{caption} (illustrative data)"
            return self._result(image, png, w, h, "vega-lite", persona, spec=chart.vega_lite_json, alt=chart.alt, caption=caption)

        # Diagrams, plus hero/illustration/meme when no text-to-image provider is configured.
        fallback_note = ""
        if kind in RASTER_KINDS:
            fallback_note = (
                "\n\nNo text-to-image model is available, so draw this as a polished flat-vector editorial "
                "illustration in SVG instead (simple shapes, inferno palette, no text except meme captions are added later)."
            )
        if kind == "meme":
            meme_svg = await design(SvgMemeSpec, fallback_note)
            png, w, h = svg_to_png(meme_svg.svg, width=1024)
            png = add_meme_text(png, meme_svg.top_text, meme_svg.bottom_text)
            spec = _meme_spec_json(meme_svg.top_text, meme_svg.bottom_text)
            return self._result(image, png, w, h, "claude-svg", persona, spec=spec, alt=meme_svg.alt, caption=meme_svg.caption)
        svg = await design(SvgSpec, fallback_note)
        png, w, h = svg_to_png(svg.svg, width=1600)
        return self._result(image, png, w, h, "claude-svg", persona, spec=svg.svg, alt=svg.alt, caption=svg.caption)

    def _result(
        self,
        image: ProjectImage,
        png: bytes,
        width: int,
        height: int,
        provider: str,
        persona: Persona,
        **fields: Any,
    ) -> dict[str, Any]:
        return {
            "file_name": self._write(image.project_id, image.slot_id, png),
            "provider": provider,
            "width": width,
            "height": height,
            "credit": credit_line(persona, provider),
            "seed": fields.pop("seed", None),
            **fields,
        }

    def _write(self, project_id: int, slot_id: str, png: bytes) -> str:
        name = f"{slot_id}-{uuid4().hex[:8]}.png"
        (self.storage.image_dir(project_id) / name).write_bytes(png)
        return name

    def _save(self, image_id: int, updates: dict[str, Any], *, record: bool = True) -> ProjectImage:
        with Session(self.engine) as session:
            image = session.get(ProjectImage, image_id)
            if image is None:
                raise KeyError(image_id)
            for key, value in updates.items():
                setattr(image, key, value)
            if record and updates.get("file_name"):
                entry = {
                    k: getattr(image, k)
                    for k in ("file_name", "provider", "seed", "prompt", "spec", "alt", "caption", "credit", "width", "height")
                }
                entry["created_at"] = datetime.now(UTC).isoformat()
                image.history = [*image.history, entry]
            session.add(image)
            session.commit()
            session.refresh(image)
            return image


def _meme_spec_json(top: str, bottom: str) -> str:
    import json

    return json.dumps({"top": top, "bottom": bottom})


def _meme_captions(spec: str) -> dict[str, str]:
    import json

    try:
        data = json.loads(spec or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}
