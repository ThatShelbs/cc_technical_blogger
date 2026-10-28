"""Design and render every image in a post, with credits and redraw history.

Every image is authored by Claude: illustrations, icons, diagrams and memes as SVG,
charts as Vega-Lite specs. Both are rendered locally; no model-generated code runs.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Engine
from sqlmodel import Session, col, select

from proseferno.config import Settings
from proseferno.db import Persona, ProjectImage
from proseferno.images.base import ImageProviderError
from proseferno.images.render import add_meme_text, placeholder_png, svg_to_png, vega_to_png
from proseferno.images.specs import ChartSpec, SvgMemeSpec, SvgSpec
from proseferno.llm import LLM, LLMError, SystemBlock
from proseferno.llm.base import UsageSink
from proseferno.prompts import raw, render
from proseferno.storage import Storage

log = logging.getLogger(__name__)

# Pixel width each SVG kind is rasterized at (height follows the SVG's viewBox).
RENDER_WIDTH = {"hero": 1600, "illustration": 1600, "diagram": 1600, "icon": 768, "meme": 1080}
PLACEHOLDER_RE = re.compile(r"\{\{image:([A-Za-z0-9_\-]+)\}\}")
STALE_PENDING = "Generation stopped before this image was made. Click Redraw to create it."


def model_label(model: str) -> str:
    """'claude-opus-5-5' -> 'Claude Opus 5.5' (unknown ids are returned unchanged)."""
    match = re.fullmatch(r"claude-([a-z]+)-(\d+)-(\d+)(?:-\d{8})?", model)
    if not match:
        return model
    family, major, minor = match.groups()
    return f"Claude {family.capitalize()} {major}.{minor}"


def tool_label(provider: str, model: str) -> str:
    claude = model_label(model)
    return {
        "claude-svg": f"{claude} (SVG)",
        "vega-lite": f"{claude} + Vega-Lite",
        "placeholder": "Proseferno",
    }.get(provider, provider)


def credit_line(persona: Persona, provider: str, model: str = "claude-opus-5-5") -> str:
    name = persona.display_name or persona.name
    if provider == "upload":
        return f"Image by {name}"
    tool = tool_label(provider, model)
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


def image_guidance(voice_profile: str) -> str:
    match = re.search(r"^##\s+Images.*?$(.*?)(?=^##\s|\Z)", voice_profile, flags=re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else "Use clear, relevant images with short captions and a credit."


class ImageService:
    def __init__(self, *, engine: Engine, llm: LLM, settings: Settings, storage: Storage) -> None:
        self.engine = engine
        self.llm = llm
        self.settings = settings
        self.storage = storage

    async def create(
        self,
        image_id: int,
        *,
        persona: Persona,
        title: str,
        markdown: str,
        voice_profile: str,
        redraw: bool = False,
        rethink: bool = False,
        usage: UsageSink | None = None,
    ) -> ProjectImage:
        """Design and render one image, then persist the result."""
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
                voice_profile=voice_profile,
                redraw=redraw,
                rethink=rethink,
                usage=usage,
            )
            updates["status"] = "placeholder" if image.kind == "screenshot" else "ready"
            updates["error"] = None
        except (ImageProviderError, LLMError) as exc:
            updates = {"status": "error", "error": str(exc)}
        except Exception as exc:
            # One broken image must never take down the post (or leave a spinner running forever).
            log.exception("Image %s failed", image_id)
            updates = {"status": "error", "error": f"Could not create this image ({type(exc).__name__}). Click Redraw to try again."}
        return self._save(image_id, updates)

    def fail_pending(self, project_id: int | None = None, reason: str = STALE_PENDING) -> int:
        """Mark images still waiting to be drawn as errors (their job is gone); returns how many."""
        with Session(self.engine) as session:
            query = select(ProjectImage).where(ProjectImage.status == "pending")
            if project_id is not None:
                query = query.where(col(ProjectImage.project_id) == project_id)
            rows = list(session.exec(query))
            for row in rows:
                row.status = "error"
                row.error = reason
                session.add(row)
            session.commit()
            return len(rows)

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
        voice_profile: str,
        redraw: bool,
        rethink: bool,
        usage: UsageSink | None,
    ) -> dict[str, Any]:
        kind = image.kind
        if kind == "screenshot":
            png, w, h = placeholder_png(image.purpose or image.prompt)
            return self._result(image, png, w, h, "placeholder", persona, alt=image.purpose, caption=image.caption or image.purpose)

        variation = ""
        if rethink:
            variation = (
                "This is a rethink: throw out the previous concept and design a completely different idea that serves the same purpose "
                f"(previous caption: {image.caption!r})."
            )
        elif redraw:
            variation = (
                "This is a redraw: keep the same idea but give it a clearly different composition, metaphor or visual treatment "
                f"(previous caption: {image.caption!r})."
            )
        prompt = render(
            "image_spec",
            kind=kind,
            slot_id=image.slot_id,
            title=title,
            purpose=image.purpose,
            brief=image.prompt or image.purpose,
            visual_style=persona.visual_style or "warm flat-vector editorial illustration in inferno tones",
            variation=variation,
            image_guidance=image_guidance(voice_profile),
            context=image_context(markdown, image.slot_id),
        )
        system = [SystemBlock(raw("image_system"), cache=True)]

        async def design(schema: type[Any]) -> Any:
            return await self.llm.structured(
                task=f"{kind} image design",
                system=system,
                prompt=prompt,
                schema=schema,
                effort=self.settings.effort_images,
                max_tokens=24000,
                usage=usage,
            )

        if kind == "chart":
            chart = await design(ChartSpec)
            png, w, h = vega_to_png(chart.vega_lite_json)
            caption = chart.caption
            if chart.data_is_illustrative and "illustrative" not in caption.lower():
                caption = f"{caption} (illustrative data)"
            return self._result(image, png, w, h, "vega-lite", persona, spec=chart.vega_lite_json, alt=chart.alt, caption=caption)

        if kind == "meme":
            meme = await design(SvgMemeSpec)
            png, w, h = svg_to_png(meme.svg, width=RENDER_WIDTH["meme"])
            png = add_meme_text(png, meme.top_text, meme.bottom_text)
            spec = json.dumps({"svg": meme.svg, "top": meme.top_text, "bottom": meme.bottom_text})
            return self._result(image, png, w, h, "claude-svg", persona, spec=spec, alt=meme.alt, caption=meme.caption)

        svg = await design(SvgSpec)
        png, w, h = svg_to_png(svg.svg, width=RENDER_WIDTH.get(kind, 1600))
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
            "credit": credit_line(persona, provider, self.settings.model),
            "seed": None,
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
