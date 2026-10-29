"""Tweak a finished post from the author's feedback: surgical edits, not a rewrite.

Claude returns only find/replace edits (and, when asked, new briefs for specific images),
so the untouched text and images stay byte-for-byte the same, output tokens stay small,
and the cached voice-profile + exemplar prefix is shared with generation.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from sqlalchemy import Engine
from sqlmodel import Session, col, select

from proseferno.authenticity import analyze, author_profile
from proseferno.config import Settings
from proseferno.db import Persona, Project, ProjectImage, Sample, utcnow
from proseferno.images import ImageService
from proseferno.jobs import JobContext
from proseferno.llm import LLM
from proseferno.prompts import render
from proseferno.voice import current_voice_profile, format_exemplars, select_exemplars
from proseferno.voice.lessons import format_lessons, record_feedback
from proseferno.writer.dials import Dials, resolve
from proseferno.writer.pipeline import (
    WriterError,
    ensure_placeholders,
    measure,
    prompt_settings,
    split_title,
    writer_system,
)
from proseferno.writer.revisions import push_revision
from proseferno.writer.schemas import ImageSlot, PostEdits, TextEdit

TEXT_JOBS = ("generate_post", "tweak_post")


def apply_edits(markdown: str, edits: list[TextEdit]) -> tuple[str, int, list[str]]:
    """Apply find/replace edits in order; returns (markdown, applied count, edits that could not be placed)."""
    applied = 0
    skipped: list[str] = []
    for edit in edits:
        if not edit.find.strip() or edit.find == edit.replace:
            continue
        start = markdown.find(edit.find)
        end = start + len(edit.find)
        if start < 0:
            # The model may reflow whitespace when copying a passage; match it word by word.
            pattern = r"\s+".join(re.escape(word) for word in edit.find.split())
            match = re.search(pattern, markdown)
            if match is None:
                skipped.append(edit.find[:120])
                continue
            start, end = match.span()
        markdown = markdown[:start] + edit.replace + markdown[end:]
        applied += 1
    return markdown, applied, skipped


def plan_slots(plan: dict[str, Any] | None) -> list[ImageSlot]:
    return [ImageSlot.model_validate(slot) for slot in (plan or {}).get("image_slots", [])]


def finish_text(markdown: str, plan: dict[str, Any] | None) -> str:
    """Put back any image placeholder an edit dropped, and drop captions next to them."""
    slots = plan_slots(plan)
    return ensure_placeholders(markdown, slots) if slots else markdown


def _image_list(images: list[ProjectImage]) -> str:
    lines = [
        f"- `{{{{image:{img.slot_id}}}}}` ({img.kind}): {img.purpose or img.prompt}"
        + (f" Current caption: {img.caption!r}." if img.caption else "")
        for img in images
    ]
    return "\n".join(lines) or "(none)"


async def tweak_post(
    *,
    engine: Engine,
    llm: LLM,
    settings: Settings,
    images: ImageService,
    project_id: int,
    feedback: str,
    ctx: JobContext,
) -> dict[str, Any]:
    with Session(engine, expire_on_commit=False) as session:
        project = session.get(Project, project_id)
        if project is None:
            raise WriterError("Project not found.")
        persona = session.get(Persona, project.persona_id)
        voice_profile = current_voice_profile(session, project.persona_id)
        samples = list(session.exec(select(Sample).where(Sample.persona_id == project.persona_id)))
        image_rows = list(
            session.exec(select(ProjectImage).where(ProjectImage.project_id == project_id).order_by(col(ProjectImage.position)))
        )
    if persona is None:
        raise WriterError("The project's persona no longer exists.")
    if voice_profile is None:
        raise WriterError("This persona has no voice profile yet.")
    if not project.markdown:
        raise WriterError("Generate the post before tweaking it.")

    dials = resolve(Dials(**(project.dials or {})), persona, project.prompt, default_revisions=settings.revision_passes)
    # Same system blocks as generation, so the voice profile and exemplars come from the prompt cache.
    system = writer_system(
        voice_profile.markdown, format_exemplars(select_exemplars(project.prompt, samples)), format_lessons(persona.edit_lessons)
    )

    await ctx.progress(0.1, "Working your feedback into the post")
    result = await llm.structured(
        task="post tweak",
        system=system,
        prompt=render(
            "tweak", feedback=feedback.strip(), markdown=project.markdown, images=_image_list(image_rows), **prompt_settings(dials)
        ),
        schema=PostEdits,
        effort=settings.effort_critique,
        max_tokens=32000,
        usage=ctx.add_usage,
    )

    markdown, applied, skipped = apply_edits(project.markdown, result.edits)
    by_slot = {img.slot_id: img for img in image_rows}
    changes = [c for c in result.image_changes if c.slot_id in by_slot and c.brief.strip()]
    if not applied and not changes:
        raise WriterError("Claude couldn't find where to make that change. Try quoting the sentence you mean, or naming the section.")

    title, subtitle = project.title, project.subtitle
    if applied:
        markdown = finish_text(markdown, project.plan)
        new_title, new_subtitle = split_title(markdown)
        title, subtitle = new_title or title, new_subtitle or subtitle
        await ctx.progress(0.5, "Checking how human the post reads")
        authenticity = await analyze(
            llm=llm,
            settings=settings,
            markdown=markdown,
            voice_profile=voice_profile.markdown,
            profile=author_profile(samples, voice_profile.baseline_stylometrics),
            use_judge=settings.ai_detection,
            usage=ctx.add_usage,
        )
        with Session(engine) as session:
            row = session.get(Project, project_id)
            if row is None:
                raise WriterError("Project not found.")
            push_revision(row, feedback, "tweak")
            row.markdown, row.title, row.subtitle = markdown, title, subtitle
            row.fidelity = measure(markdown, voice_profile.baseline_stylometrics)
            row.authenticity = authenticity
            row.updated_at = utcnow()
            session.add(row)
            # The author's feedback is a lesson for every later post, not just this one.
            persona_row = session.get(Persona, project.persona_id)
            if persona_row is not None:
                record_feedback(persona_row, feedback)
                session.add(persona_row)
            session.commit()

    if changes:
        await ctx.progress(0.7, f"Redrawing {len(changes)} image{'s' if len(changes) > 1 else ''}")
        with Session(engine) as session:
            for change in changes:
                image = session.get(ProjectImage, by_slot[change.slot_id].id)
                if image is not None:
                    image.prompt = change.brief.strip()
                    session.add(image)
            session.commit()
        semaphore = asyncio.Semaphore(3)

        async def redraw(image_id: int) -> None:
            async with semaphore:
                await images.create(
                    image_id,
                    persona=persona,
                    title=title,
                    markdown=markdown,
                    voice_profile=voice_profile.markdown,
                    redraw=True,
                    rethink=True,
                    brand_kit=project.brand_kit,
                    usage=ctx.add_usage,
                )
            await ctx.emit("image_ready", {"image_id": image_id})

        await asyncio.gather(*(redraw(image_id) for c in changes if (image_id := by_slot[c.slot_id].id) is not None))

    await ctx.progress(1.0, "Feedback applied")
    return {
        "project_id": project_id,
        "summary": result.summary,
        "applied": applied,
        "skipped": skipped,
        "images_redrawn": [c.slot_id for c in changes],
    }
