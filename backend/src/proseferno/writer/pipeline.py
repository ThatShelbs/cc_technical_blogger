"""Generate a full post: plan -> streamed draft -> critique/revise -> images."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import Engine
from sqlmodel import Session, col, delete, select

from proseferno.config import Settings
from proseferno.db import Persona, Project, ProjectImage, Sample, VoiceSoul, utcnow
from proseferno.images import PLACEHOLDER_RE, ImageService
from proseferno.ingest import parse_markdown
from proseferno.ingest.stylometrics import compute, fidelity
from proseferno.jobs import JobContext
from proseferno.llm import LLM, SystemBlock
from proseferno.prompts import raw, render
from proseferno.voice import format_exemplars, latest_voice_soul, select_exemplars
from proseferno.writer.dials import Dials, ResolvedDials, resolve
from proseferno.writer.schemas import ArticlePlan, Critique, ImageSlot


class WriterError(ValueError):
    pass


def writer_system(voice_soul: str, exemplars: str) -> list[SystemBlock]:
    """Stable prefix shared by every call in a project, cached after the exemplars."""
    return [
        SystemBlock(raw("writer_system")),
        SystemBlock(f"# Voice soul\n\n{voice_soul}"),
        SystemBlock(exemplars, cache=True),
    ]


def normalize_slots(slots: list[ImageSlot], count: int, section_count: int) -> list[ImageSlot]:
    """Guarantee: hero first, meme last, exactly ``count`` slots, unique ids."""
    hero = next((s for s in slots if s.kind == "hero"), None) or ImageSlot(
        slot_id="hero", kind="hero", section_index=-1, purpose="Thumbnail and opening image", brief="The post's central idea"
    )
    meme = next((s for s in slots if s.kind == "meme"), None) or ImageSlot(
        slot_id="meme", kind="meme", section_index=max(0, section_count - 1), purpose="Closing laugh", brief="A joke about the post's topic"
    )
    middle = [s for s in slots if s is not hero and s is not meme and s.kind not in ("hero", "meme")]
    middle = middle[: max(0, count - 2)]
    hero = hero.model_copy(update={"slot_id": "hero", "section_index": -1})
    meme = meme.model_copy(update={"slot_id": "meme", "section_index": max(0, section_count - 1)})
    renamed = [s.model_copy(update={"slot_id": f"img{i + 2}"}) for i, s in enumerate(middle)]
    return [hero, *renamed, meme]


def ensure_placeholders(markdown: str, slots: list[ImageSlot]) -> str:
    """Insert any placeholder the draft forgot, in a sensible spot."""
    present = set(PLACEHOLDER_RE.findall(markdown))
    lines = markdown.rstrip().splitlines()
    for slot in slots:
        if slot.slot_id in present:
            continue
        tag = f"{{{{image:{slot.slot_id}}}}}"
        if slot.kind == "hero":
            insert_at = _after_title_block(lines)
        elif slot.kind == "meme":
            insert_at = len(lines)
        else:
            insert_at = _end_of_section(lines, slot.section_index)
        lines[insert_at:insert_at] = ["", tag, ""]
    # Drop placeholders that do not match a slot.
    valid = {s.slot_id for s in slots}
    text = "\n".join(lines)
    text = PLACEHOLDER_RE.sub(lambda m: m.group(0) if m.group(1) in valid else "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def _after_title_block(lines: list[str]) -> int:
    index = 0
    for i, line in enumerate(lines[:6]):
        if line.startswith("# ") or (line.startswith("*") and line.endswith("*") and len(line) > 2):
            index = i + 1
    return index


def _end_of_section(lines: list[str], section_index: int) -> int:
    headings = [i for i, line in enumerate(lines) if line.startswith("## ")]
    if not headings:
        return len(lines)
    target = min(max(section_index, 0), len(headings) - 1)
    return headings[target + 1] if target + 1 < len(headings) else len(lines)


def split_title(markdown: str) -> tuple[str, str]:
    title = subtitle = ""
    for line in markdown.splitlines()[:6]:
        stripped = line.strip()
        if stripped.startswith("# ") and not title:
            title = stripped[2:].strip()
        elif title and stripped.startswith("*") and stripped.endswith("*") and len(stripped) > 2:
            subtitle = stripped.strip("*_ ").strip()
            break
    return title, subtitle


def set_title(markdown: str, title: str) -> str:
    lines = markdown.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("# "):
            lines[i] = f"# {title}"
            return "\n".join(lines) + ("\n" if markdown.endswith("\n") else "")
    return f"# {title}\n\n{markdown}"


def measure(markdown: str, baseline: dict[str, Any]) -> dict[str, Any]:
    as_images = PLACEHOLDER_RE.sub(lambda m: f"![{m.group(1)}](image)", markdown)
    doc = parse_markdown(as_images)
    return {**fidelity(baseline, compute(doc)), "word_count": doc.word_count}


async def generate_article(
    *,
    engine: Engine,
    llm: LLM,
    settings: Settings,
    images: ImageService,
    project_id: int,
    ctx: JobContext,
) -> dict[str, Any]:
    # expire_on_commit=False: these rows are read for the rest of the (long) job after the session closes.
    with Session(engine, expire_on_commit=False) as session:
        project = session.get(Project, project_id)
        if project is None:
            raise WriterError("Project not found.")
        persona = session.get(Persona, project.persona_id)
        soul = latest_voice_soul(session, project.persona_id)
        samples = list(session.exec(select(Sample).where(Sample.persona_id == project.persona_id)))
        project.status = "generating"
        project.error = None
        session.add(project)
        session.commit()
        session.refresh(project)
    if persona is None:
        raise WriterError("The project's persona no longer exists.")
    if soul is None:
        raise WriterError("Generate a voice soul for this persona before writing a post.")

    try:
        return await _generate(engine, llm, settings, images, project, persona, soul, samples, ctx)
    except Exception as exc:
        with Session(engine) as session:
            row = session.get(Project, project_id)
            if row is not None:
                row.status = "error"
                row.error = str(exc)[:2000]
                session.add(row)
                session.commit()
        raise


class Reporter(Protocol):
    """Where pipeline progress goes: a JobContext in the app, a silent stub in evals."""

    async def progress(self, fraction: float, message: str) -> None: ...
    async def emit(self, event_type: str, data: Any) -> None: ...
    def add_usage(self, usage: dict[str, int]) -> None: ...


@dataclass
class WrittenPost:
    markdown: str
    plan: ArticlePlan
    critique: Critique | None
    fidelity: dict[str, Any]


async def write_post(
    *,
    llm: LLM,
    settings: Settings,
    soul: VoiceSoul,
    samples: list[Sample],
    prompt: str,
    dials: ResolvedDials,
    reporter: Reporter,
    on_plan: Callable[[ArticlePlan], None] | None = None,
    on_draft: Callable[[str, dict[str, Any]], None] | None = None,
) -> WrittenPost:
    """Plan -> streamed draft -> critique/revise. Text only; images are a separate step."""
    exemplars = select_exemplars(prompt, samples)
    system = writer_system(soul.markdown, format_exemplars(exemplars))
    settings_text = _settings_text(dials)

    # 1. Plan
    await reporter.progress(0.03, "Planning the post")
    plan = await llm.structured(
        task="post plan",
        system=system,
        prompt=render("plan", prompt=prompt, **settings_text),
        schema=ArticlePlan,
        effort=settings.effort_plan,
        usage=reporter.add_usage,
    )
    slots = normalize_slots(plan.image_slots, dials.image_count, len(plan.sections))
    plan = plan.model_copy(update={"image_slots": slots})
    await reporter.emit("plan", plan.model_dump())
    if on_plan:
        on_plan(plan)

    # 2. Draft (streamed)
    await reporter.progress(0.12, "Writing the first draft")

    async def stream_delta(text: str) -> None:
        await reporter.emit("draft_delta", {"text": text})

    placeholders = ", ".join(f"`{{{{image:{s.slot_id}}}}}` ({s.kind}: {s.purpose})" for s in slots)
    draft = await llm.text(
        task="draft",
        system=system,
        prompt=render(
            "draft",
            prompt=prompt,
            plan=json.dumps(plan.model_dump(exclude={"image_slots"}), indent=1),
            placeholders=placeholders,
            **settings_text,
        ),
        effort=settings.effort_draft,
        on_delta=stream_delta,
        usage=reporter.add_usage,
    )
    draft = ensure_placeholders(draft, slots)
    measured = measure(draft, soul.baseline_stylometrics)
    if on_draft:
        on_draft(draft, measured)

    # 3. Critique and revise
    critique: Critique | None = None
    for round_number in range(dials.revision_passes):
        await reporter.progress(0.45 + 0.1 * round_number, "Editor reviewing the draft for voice fidelity")
        critique = await llm.structured(
            task="critique",
            system=system,
            prompt=render("critique", draft=draft, fidelity=json.dumps(measured, indent=1), **settings_text),
            schema=Critique,
            effort=settings.effort_critique,
            usage=reporter.add_usage,
        )
        await reporter.emit("critique", critique.model_dump())
        if critique.overall >= 9 and not critique.revision_instructions:
            break
        await reporter.progress(0.5 + 0.1 * round_number, "Revising to sound more like you")
        await reporter.emit("draft_reset", {})
        draft = await llm.text(
            task="revision",
            system=system,
            prompt=render("revise", draft=draft, critique=json.dumps(critique.model_dump(), indent=1)),
            effort=settings.effort_draft,
            on_delta=stream_delta,
            usage=reporter.add_usage,
        )
        draft = ensure_placeholders(draft, slots)
        measured = measure(draft, soul.baseline_stylometrics)

    return WrittenPost(markdown=draft, plan=plan, critique=critique, fidelity=measured)


async def _generate(
    engine: Engine,
    llm: LLM,
    settings: Settings,
    images: ImageService,
    project: Project,
    persona: Persona,
    soul: VoiceSoul,
    samples: list[Sample],
    ctx: JobContext,
) -> dict[str, Any]:
    assert project.id is not None
    project_id = project.id
    dials = resolve(Dials(**(project.dials or {})), persona, project.prompt, default_revisions=settings.revision_passes)
    post = await write_post(
        llm=llm,
        settings=settings,
        soul=soul,
        samples=samples,
        prompt=project.prompt,
        dials=dials,
        reporter=ctx,
        on_plan=lambda plan: _save(
            engine, project_id, plan=plan.model_dump(), title=plan.chosen_title, subtitle=plan.subtitle, voice_soul_version=soul.version
        ),
        on_draft=lambda draft, measured: _save(engine, project_id, markdown=draft, fidelity=measured),
    )
    draft, plan, slots = post.markdown, post.plan, post.plan.image_slots

    title, subtitle = split_title(draft)
    _save(
        engine,
        project.id,
        markdown=draft,
        title=title or plan.chosen_title,
        subtitle=subtitle or plan.subtitle,
        critique=post.critique.model_dump() if post.critique else None,
        fidelity=post.fidelity,
    )

    # 4. Images
    await ctx.progress(0.7, f"Creating {len(slots)} images")
    image_ids = _create_image_rows(engine, project.id, slots)
    finished = 0
    semaphore = asyncio.Semaphore(3)

    async def make(image_id: int) -> None:
        nonlocal finished
        async with semaphore:
            await images.create(
                image_id,
                persona=persona,
                title=title or plan.chosen_title,
                markdown=draft,
                voice_soul=soul.markdown,
                usage=ctx.add_usage,
            )
        finished += 1
        await ctx.emit("image_ready", {"image_id": image_id})
        await ctx.progress(0.7 + 0.28 * finished / len(image_ids), f"Created {finished} of {len(image_ids)} images")

    await asyncio.gather(*(make(i) for i in image_ids))
    _save(engine, project.id, status="ready")
    await ctx.progress(1.0, "Your post is ready")
    return {"project_id": project.id}


async def rewrite_passage(
    *,
    llm: LLM,
    settings: Settings,
    engine: Engine,
    project_id: int,
    selection: str,
    instruction: str,
) -> str:
    with Session(engine) as session:
        project = session.get(Project, project_id)
        if project is None:
            raise WriterError("Project not found.")
        soul = latest_voice_soul(session, project.persona_id)
        samples = list(session.exec(select(Sample).where(Sample.persona_id == project.persona_id)))
    if soul is None:
        raise WriterError("This persona has no voice soul yet.")
    if selection not in project.markdown:
        raise WriterError("The selected passage was not found in the post. It may have changed; select it again.")
    system = writer_system(soul.markdown, format_exemplars(select_exemplars(project.prompt, samples)))
    replacement = await llm.text(
        task="passage rewrite",
        system=system,
        prompt=render("rewrite", instruction=instruction or "Make it sound more like me.", markdown=project.markdown, selection=selection),
        effort=settings.effort_critique,
        max_tokens=16000,
    )
    new_markdown = project.markdown.replace(selection, replacement.strip(), 1)
    _save(engine, project_id, markdown=new_markdown)
    return new_markdown


def _settings_text(dials: ResolvedDials) -> dict[str, Any]:
    include_code = {
        "auto": "include where they genuinely help the reader",
        "yes": "include key code snippets and/or LLM prompts",
        "no": "do not include code",
    }[dials.include_code]
    return {
        "topic": dials.topic,
        "target_words": dials.target_words,
        "humor": dials.humor,
        "humor_guide": dials.humor_guide,
        "education": dials.education,
        "education_guide": dials.education_guide,
        "include_code": include_code,
        "platform": dials.platform,
        "image_count": dials.image_count,
    }


def _save(engine: Engine, project_id: int, **fields: Any) -> None:
    with Session(engine) as session:
        project = session.get(Project, project_id)
        if project is None:
            return
        for key, value in fields.items():
            setattr(project, key, value)
        project.updated_at = utcnow()
        session.add(project)
        session.commit()


def _create_image_rows(engine: Engine, project_id: int, slots: list[ImageSlot]) -> list[int]:
    with Session(engine) as session:
        session.exec(delete(ProjectImage).where(col(ProjectImage.project_id) == project_id))  # type: ignore[call-overload]
        rows = [
            ProjectImage(
                project_id=project_id,
                slot_id=slot.slot_id,
                position=i,
                kind=slot.kind,
                purpose=slot.purpose,
                prompt=slot.brief,
            )
            for i, slot in enumerate(slots)
        ]
        session.add_all(rows)
        session.commit()
        return [row.id for row in rows if row.id is not None]
