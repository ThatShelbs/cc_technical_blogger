"""Design and render every image in a post, with credits and redraw history.

Every image is authored by Claude: illustrations, icons and diagrams as SVG, charts as
Vega-Lite specs, and memes as a format from the meme catalog (``images/memes``). All are
rendered locally; no model-generated code runs.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import Engine
from sqlmodel import Session, col, select

from proseferno.config import Settings
from proseferno.db import Persona, Project, ProjectImage
from proseferno.images.base import PLACEHOLDER_RE, ImageProviderError, draw_with_retry
from proseferno.images.memes import (
    ArtDirection,
    MemeContext,
    MemeMaker,
    MemeResult,
    get_format,
    load_state,
    plan_callbacks,
    voice_section,
)
from proseferno.images.render import add_meme_text, placeholder_png, svg_to_png, vega_to_png
from proseferno.images.specs import ChartSpec, SvgMemeSpec, SvgSpec
from proseferno.llm import LLM, LLMError, SystemBlock
from proseferno.llm.base import UsageSink
from proseferno.prompts import raw, render
from proseferno.storage import Storage

log = logging.getLogger(__name__)

# Pixel width each SVG kind is rasterized at (height follows the SVG's viewBox).
RENDER_WIDTH = {"hero": 1600, "illustration": 1600, "diagram": 1600, "icon": 768, "meme": 1080}
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
        "claude-meme": f"{claude} (meme)",
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


DEFAULT_VISUAL_STYLE = "warm flat-vector editorial illustration in inferno tones"


def brand_guidance(brand_kit: dict[str, Any] | None, persona: Persona) -> tuple[str, str]:
    """The post's brand kit as (visual style, extra art direction); empty fields fall back to the persona."""
    kit = brand_kit or {}
    style = str(kit.get("style") or "").strip() or persona.visual_style or DEFAULT_VISUAL_STYLE
    lines = []
    if palette := [str(c) for c in kit.get("palette") or []]:
        lines.append(f"Brand palette for this post (use these colors instead of the inferno palette): {' '.join(palette)}")
    if font := str(kit.get("font") or "").strip():
        lines.append(f"Brand font for any text in the image: {font} (fall back to Segoe UI, Helvetica, Arial, sans-serif)")
    if motif := str(kit.get("motif") or "").strip():
        lines.append(f"Recurring motif to weave into every image of this post: {motif}")
    return style, "\n".join(lines)


def image_guidance(voice_profile: str) -> str:
    return voice_section(voice_profile, "Images") or "Use clear, relevant images with short captions and a credit."


def brand_palette(brand_kit: dict[str, Any] | None) -> tuple[str, ...]:
    return tuple(str(c) for c in (brand_kit or {}).get("palette") or [])


def _formula_note(dials: dict[str, Any], persona: Persona, brief: str) -> str:
    """The post's formula as the meme's writers' room should read it: the same one the writer followed."""
    # Imported here because the writer package imports this one.
    from proseferno.writer.dials import Dials, resolve
    from proseferno.writer.formulas import NOTE_FIELDS, PART_FIELDS, ResolvedFormula, meme_note

    try:
        resolved = resolve(Dials(**dials), persona, brief, default_revisions=0)
    except ValueError:  # dials saved by an older version: the meme is pitched without the formula
        return ""
    return meme_note(ResolvedFormula(**{field: getattr(resolved, field) for field in (*PART_FIELDS, *NOTE_FIELDS)}))


class ImageService:
    def __init__(self, *, engine: Engine, llm: LLM, settings: Settings, storage: Storage) -> None:
        self.engine = engine
        self.llm = llm
        self.settings = settings
        self.storage = storage
        self.memes = MemeMaker(llm, settings)

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
        brand_kit: dict[str, Any] | None = None,
        instruction: str = "",
        meme_format: str | None = None,
        meme_concept: int | None = None,
        usage: UsageSink | None = None,
    ) -> ProjectImage:
        """Design and render one image, then persist the result.

        With an ``instruction`` the current image is edited ("make the arrows orange") instead of redrawn.
        ``meme_format`` makes a meme in that catalog format; ``meme_concept`` draws that stored pitch.
        """
        with Session(self.engine) as session:
            image = session.get(ProjectImage, image_id)
            if image is None:
                raise KeyError(image_id)
        try:
            if instruction.strip():
                updates = await self._edit(image, persona=persona, instruction=instruction, brand_kit=brand_kit, usage=usage)
            else:
                updates = await self._produce(
                    image,
                    persona=persona,
                    title=title,
                    markdown=markdown,
                    voice_profile=voice_profile,
                    redraw=redraw,
                    rethink=rethink,
                    brand_kit=brand_kit,
                    meme_format=meme_format,
                    meme_concept=meme_concept,
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

    def set_meme_words(
        self, image_id: int, words: dict[str, str], *, persona: Persona, brand_kit: dict[str, Any] | None = None
    ) -> ProjectImage:
        """Retype a meme's words and draw it again without asking Claude; raises ImageProviderError if it cannot be drawn."""
        with Session(self.engine) as session:
            image = session.get(ProjectImage, image_id)
            if image is None:
                raise KeyError(image_id)
        if image.kind != "meme":
            raise ImageProviderError("Only memes have words to edit.")
        meme = self.memes.reword(image.spec, words, self._art_direction(brand_kit, persona, ""))
        updates = self._result(image, meme.png, meme.width, meme.height, meme.provider, persona, spec=meme.spec, alt=meme.alt)
        return self._save(image_id, {**updates, "status": "ready", "error": None})

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
        brand_kit: dict[str, Any] | None,
        meme_format: str | None,
        meme_concept: int | None,
        usage: UsageSink | None,
    ) -> dict[str, Any]:
        kind = image.kind
        if kind == "screenshot":
            png, w, h = placeholder_png(image.purpose or image.prompt)
            return self._result(image, png, w, h, "placeholder", persona, alt=image.purpose, caption=image.caption or image.purpose)
        if kind == "meme":
            with Session(self.engine) as session:
                project = session.get(Project, image.project_id)
                plan = dict(project.plan or {}) if project else {}
                dials = dict(project.dials or {}) if project else {}
                brief = project.prompt if project else ""
            humor = dials.get("humor")
            post = MemeContext(
                title=title,
                markdown=markdown,
                voice_profile=voice_profile,
                brief=image.prompt or image.purpose,
                joke=str(plan.get("joke") or ""),
                callbacks=plan_callbacks(plan),
                humor=int(humor) if humor is not None else persona.default_humor,
                recent_formats=self._recent_meme_formats(persona, image.project_id),
                formula=_formula_note(dials, persona, brief),
            )
            meme = await self.memes.make(
                image.spec,
                post,
                self._art_direction(brand_kit, persona, voice_profile),
                redraw=redraw,
                rethink=rethink,
                meme_format=meme_format,
                concept_index=meme_concept,
                usage=usage,
            )
            return self._meme_result(image, persona, meme)

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
        visual_style, brand = brand_guidance(brand_kit, persona)
        prompt = render(
            "image_spec",
            kind=kind,
            slot_id=image.slot_id,
            title=title,
            purpose=image.purpose,
            brief=image.prompt or image.purpose,
            visual_style=visual_style,
            brand=brand,
            variation=variation,
            image_guidance=image_guidance(voice_profile),
            siblings=self._siblings(image),
            context=image_context(markdown, image.slot_id),
        )
        return await self._render_design(image, persona, prompt, task=f"{kind} image design", palette=brand_palette(brand_kit), usage=usage)

    async def _edit(
        self,
        image: ProjectImage,
        *,
        persona: Persona,
        instruction: str,
        brand_kit: dict[str, Any] | None,
        usage: UsageSink | None,
    ) -> dict[str, Any]:
        """Change the current design as the author asks, keeping everything else about it."""
        if image.kind == "screenshot" or image.provider in ("upload", "placeholder") or not image.spec:
            raise ImageProviderError("Only images Claude drew can be edited by instruction. Redraw or upload this one instead.")
        if image.kind == "meme" and load_state(image.spec):
            meme = await self.memes.edit(image.spec, instruction, self._art_direction(brand_kit, persona, ""), usage=usage)
            return self._meme_result(image, persona, meme)
        _, brand = brand_guidance(brand_kit, persona)
        prompt = render(
            "image_edit",
            kind=image.kind,
            slot_id=image.slot_id,
            instruction=instruction.strip(),
            caption=image.caption,
            alt=image.alt,
            spec=image.spec,
            brand=brand,
        )
        return await self._render_design(
            image, persona, prompt, task=f"{image.kind} image edit", palette=brand_palette(brand_kit), usage=usage
        )

    async def _render_design(
        self, image: ProjectImage, persona: Persona, prompt: str, *, task: str, palette: tuple[str, ...] = (), usage: UsageSink | None
    ) -> dict[str, Any]:
        """Ask Claude for the design and draw it; a design that cannot be drawn gets one more try with the error quoted back."""
        kind = image.kind
        system = [SystemBlock(raw("image_system"), cache=True)]

        async def design[S: BaseModel](schema: type[S], draw: Callable[[S], tuple[bytes, int, int]]) -> tuple[S, tuple[bytes, int, int]]:
            async def ask(note: str) -> S:
                return await self.llm.structured(
                    task=task,
                    system=system,
                    prompt=prompt + note,
                    schema=schema,
                    effort=self.settings.effort_images,
                    max_tokens=24000,
                    usage=usage,
                )

            return await draw_with_retry(ask, lambda made, _last: draw(made))

        if kind == "chart":
            chart, (png, w, h) = await design(
                ChartSpec, lambda c: vega_to_png(c.vega_lite_json, palette=palette, illustrative=c.data_is_illustrative)
            )
            caption = chart.caption
            if chart.data_is_illustrative and "illustrative" not in caption.lower():
                caption = f"{caption} (illustrative data)"
            return self._result(image, png, w, h, "vega-lite", persona, spec=chart.vega_lite_json, alt=chart.alt, caption=caption)

        if kind == "meme":
            meme, (png, w, h) = await design(SvgMemeSpec, lambda m: svg_to_png(m.svg, width=RENDER_WIDTH["meme"]))
            png = add_meme_text(png, meme.top_text, meme.bottom_text)
            spec = json.dumps({"svg": meme.svg, "top": meme.top_text, "bottom": meme.bottom_text})
            return self._result(image, png, w, h, "claude-svg", persona, spec=spec, alt=meme.alt, caption=meme.caption)

        svg, (png, w, h) = await design(SvgSpec, lambda d: svg_to_png(d.svg, width=RENDER_WIDTH.get(kind, 1600)))
        return self._result(image, png, w, h, "claude-svg", persona, spec=svg.svg, alt=svg.alt, caption=svg.caption)

    def _meme_result(self, image: ProjectImage, persona: Persona, meme: MemeResult) -> dict[str, Any]:
        return self._result(
            image, meme.png, meme.width, meme.height, meme.provider, persona, spec=meme.spec, alt=meme.alt, caption=meme.caption
        )

    @staticmethod
    def _art_direction(brand_kit: dict[str, Any] | None, persona: Persona, voice_profile: str) -> ArtDirection:
        visual_style, brand = brand_guidance(brand_kit, persona)
        return ArtDirection(
            visual_style=visual_style, brand=brand, image_guidance=image_guidance(voice_profile), palette=brand_palette(brand_kit)
        )

    def _siblings(self, image: ProjectImage) -> str:
        """The post's other images, one per line, so each drawing knows what the rest of the set shows."""
        with Session(self.engine) as session:
            rows = session.exec(
                select(ProjectImage).where(ProjectImage.project_id == image.project_id).order_by(col(ProjectImage.position))
            ).all()
        lines = [f"- {row.kind} `{row.slot_id}`: {row.purpose or row.prompt}" for row in rows if row.id != image.id]
        return "\n".join(lines) or "(none)"

    def _recent_meme_formats(self, persona: Persona, project_id: int, limit: int = 3) -> tuple[str, ...]:
        """The formats of this author's latest memes in other posts, newest first."""
        with Session(self.engine) as session:
            specs = session.exec(
                select(ProjectImage.spec)
                .join(Project, col(Project.id) == col(ProjectImage.project_id))
                .where(col(Project.persona_id) == persona.id, col(ProjectImage.kind) == "meme", col(Project.id) != project_id)
                .order_by(col(Project.updated_at).desc())
                .limit(limit * 2)
            ).all()
        names: list[str] = []
        for spec in specs:
            fmt = get_format(str((load_state(spec) or {}).get("format", "")))
            if fmt and fmt.name not in names:
                names.append(fmt.name)
        return tuple(names[:limit])

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
