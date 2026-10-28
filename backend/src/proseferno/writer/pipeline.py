"""Generate a full post: plan -> streamed draft -> critique/revise -> images."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import Engine
from sqlmodel import Session, col, delete, select

from proseferno.authenticity import analyze, author_profile, scan
from proseferno.config import Settings
from proseferno.db import Persona, Project, ProjectImage, Sample, VoiceProfile, utcnow
from proseferno.images import PLACEHOLDER_RE, ImageService
from proseferno.ingest import parse_markdown
from proseferno.ingest.stylometrics import compute, fidelity
from proseferno.jobs import JobContext
from proseferno.llm import LLM, LLMError, SystemBlock
from proseferno.prompts import raw, render
from proseferno.voice import current_voice_profile, format_exemplars, select_exemplars
from proseferno.writer.dials import Dials, ResolvedDials, resolve
from proseferno.writer.revisions import push_revision
from proseferno.writer.schemas import ArticlePlan, Critique, ImageSlot, TitleOptions

log = logging.getLogger(__name__)


class WriterError(ValueError):
    pass


def writer_system(voice_profile: str, exemplars: str) -> list[SystemBlock]:
    """Stable prefix shared by every call in a project, cached after the exemplars."""
    return [
        SystemBlock(raw("writer_system")),
        SystemBlock(f"# Voice profile\n\n{voice_profile}"),
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
    text = strip_image_captions(text)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


# A caption or credit line the writer copied from the author's habits ("Photo by X on Unsplash",
# "Visualization: Jane, made with Tableau"). Images carry their own caption and credit.
_CAPTION_RE = re.compile(
    r"^[*_\s>]*(?:photo|image|illustration|visuali[sz]ation|chart|diagram|graphic|figure|fig\.|source|credit|screenshot|meme)s?"
    r"\b\s*(?:by\b|from\b|:|-|–|—|\|)"
    r"|unsplash|made with|\[todo:\s*(?:photographer|image|credit|caption)",
    re.IGNORECASE,
)
_EMPHASIS_LINE_RE = re.compile(r"^\s*(\*[^*].*[^*]\*|_[^_].*[^_]_|\*\*.+\*\*)\s*$")


def _is_caption(line: str, *, allow_emphasis: bool) -> bool:
    if not line.strip() or len(line.split()) > 30 or line.lstrip().startswith(("#", "```", "{{")):
        return False
    return bool(_CAPTION_RE.search(line)) or (allow_emphasis and bool(_EMPHASIS_LINE_RE.match(line)))


def strip_image_captions(markdown: str) -> str:
    """Drop caption/credit lines written next to image placeholders."""
    lines = markdown.split("\n")
    drop: set[int] = set()
    for i, line in enumerate(lines):
        if not PLACEHOLDER_RE.fullmatch(line.strip()):
            continue
        after = next((j for j in range(i + 1, len(lines)) if lines[j].strip()), None)
        if after is not None and _is_caption(lines[after], allow_emphasis=True):
            drop.add(after)
        # Above the image only obvious credits: an italic line there is usually the subtitle.
        before = next((j for j in range(i - 1, -1, -1) if lines[j].strip()), None)
        if before is not None and _is_caption(lines[before], allow_emphasis=False):
            drop.add(before)
    return "\n".join(line for i, line in enumerate(lines) if i not in drop)


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
        voice_profile = current_voice_profile(session, project.persona_id)
        samples = list(session.exec(select(Sample).where(Sample.persona_id == project.persona_id)))
        project.status = "generating"
        project.error = None
        session.add(project)
        session.commit()
        session.refresh(project)
    if persona is None:
        raise WriterError("The project's persona no longer exists.")
    if voice_profile is None:
        raise WriterError("Generate a voice profile for this persona before writing a post.")

    try:
        return await _generate(engine, llm, settings, images, project, persona, voice_profile, samples, ctx)
    except Exception as exc:
        with Session(engine) as session:
            row = session.get(Project, project_id)
            if row is not None:
                row.status = "error"
                row.error = str(exc)[:2000]
                session.add(row)
                session.commit()
        images.fail_pending(project_id)
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
    authenticity: dict[str, Any]


async def write_post(
    *,
    llm: LLM,
    settings: Settings,
    voice_profile: VoiceProfile,
    samples: list[Sample],
    prompt: str,
    dials: ResolvedDials,
    reporter: Reporter,
    on_plan: Callable[[ArticlePlan], None] | None = None,
    on_draft: Callable[[str, dict[str, Any]], None] | None = None,
) -> WrittenPost:
    """Plan -> streamed draft -> critique/revise. Text only; images are a separate step."""
    exemplars = select_exemplars(prompt, samples)
    system = writer_system(voice_profile.markdown, format_exemplars(exemplars))
    settings_text = prompt_settings(dials)

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
    measured = measure(draft, voice_profile.baseline_stylometrics)
    if on_draft:
        on_draft(draft, measured)

    # 3. Critique and revise (the editor also sees the AI-writing tells the scan found)
    profile = author_profile(samples, voice_profile.baseline_stylometrics)
    critique: Critique | None = None
    try:
        for round_number in range(dials.revision_passes):
            await reporter.progress(0.45 + 0.1 * round_number, "Editor reviewing the draft for voice fidelity and AI tells")
            critique = await llm.structured(
                task="critique",
                system=system,
                prompt=render(
                    "critique",
                    draft=draft,
                    fidelity=json.dumps(measured, indent=1),
                    ai_tells=scan(draft, profile).tells_text(),
                    **settings_text,
                ),
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
            measured = measure(draft, voice_profile.baseline_stylometrics)
    except LLMError as exc:
        # The first draft is already good enough to keep; a failed editing pass should not lose it.
        log.warning("Editing pass failed; keeping the current draft: %s", exc)
        await reporter.emit("draft_reset", {})
        await reporter.emit("draft_delta", {"text": draft})

    # 4. AI-generation detection report
    await reporter.progress(0.66, "Checking how human the post reads")
    authenticity = await analyze(
        llm=llm,
        settings=settings,
        markdown=draft,
        voice_profile=voice_profile.markdown,
        profile=profile,
        use_judge=settings.ai_detection,
        usage=reporter.add_usage,
    )
    await reporter.emit("authenticity", authenticity)

    return WrittenPost(markdown=draft, plan=plan, critique=critique, fidelity=measured, authenticity=authenticity)


async def _generate(
    engine: Engine,
    llm: LLM,
    settings: Settings,
    images: ImageService,
    project: Project,
    persona: Persona,
    voice_profile: VoiceProfile,
    samples: list[Sample],
    ctx: JobContext,
) -> dict[str, Any]:
    assert project.id is not None
    project_id = project.id
    dials = resolve(Dials(**(project.dials or {})), persona, project.prompt, default_revisions=settings.revision_passes)
    post = await write_post(
        llm=llm,
        settings=settings,
        voice_profile=voice_profile,
        samples=samples,
        prompt=project.prompt,
        dials=dials,
        reporter=ctx,
        on_plan=lambda plan: _save(
            engine,
            project_id,
            # Pinned titles survive "Regenerate post" and lead the new options.
            plan={**plan.model_dump(), "title_options": merge_titles(project.pinned_titles or [], plan.title_options)},
            title=plan.chosen_title,
            subtitle=plan.subtitle,
            voice_profile_version=voice_profile.version,
        ),
        # The old text versions belong to the old images, so a regeneration starts a fresh history.
        on_draft=lambda draft, measured: _save(engine, project_id, markdown=draft, fidelity=measured, revisions=[]),
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
        authenticity=post.authenticity,
    )

    # 5. Images
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
                voice_profile=voice_profile.markdown,
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
        voice_profile = current_voice_profile(session, project.persona_id)
        samples = list(session.exec(select(Sample).where(Sample.persona_id == project.persona_id)))
    if voice_profile is None:
        raise WriterError("This persona has no voice profile yet.")
    if selection not in project.markdown:
        raise WriterError("The selected passage was not found in the post. It may have changed; select it again.")
    system = writer_system(voice_profile.markdown, format_exemplars(select_exemplars(project.prompt, samples)))
    replacement = await llm.text(
        task="passage rewrite",
        system=system,
        prompt=render("rewrite", instruction=instruction or "Make it sound more like me.", markdown=project.markdown, selection=selection),
        effort=settings.effort_critique,
        max_tokens=16000,
    )
    new_markdown = project.markdown.replace(selection, replacement.strip(), 1)
    with Session(engine) as session:
        row = session.get(Project, project_id)
        if row is None:
            raise WriterError("Project not found.")
        push_revision(row, f"Rewrite: {instruction or 'sound more like me'}", "rewrite")
        row.markdown = new_markdown
        row.updated_at = utcnow()
        session.add(row)
        session.commit()
    return new_markdown


TITLE_OPTION_COUNT = 5


def merge_titles(*groups: list[str]) -> list[str]:
    """Concatenate title lists, dropping blanks and case-insensitive duplicates (first wins)."""
    seen: set[str] = set()
    out: list[str] = []
    for title in (t.strip() for group in groups for t in group):
        if title and title.casefold() not in seen:
            seen.add(title.casefold())
            out.append(title)
    return out


async def regenerate_titles(*, llm: LLM, settings: Settings, engine: Engine, project_id: int) -> list[str]:
    """Replace the title options the author did not keep; the current and pinned titles stay."""
    with Session(engine) as session:
        project = session.get(Project, project_id)
        if project is None:
            raise WriterError("Project not found.")
        voice_profile = current_voice_profile(session, project.persona_id)
        samples = list(session.exec(select(Sample).where(Sample.persona_id == project.persona_id)))
    if voice_profile is None:
        raise WriterError("This persona has no voice profile yet.")
    plan = dict(project.plan or {})
    keep = merge_titles([project.title], project.pinned_titles or [])
    rejected = [t for t in plan.get("title_options", []) if t.casefold() not in {k.casefold() for k in keep}]
    count = max(1, TITLE_OPTION_COUNT - len(keep))

    system = writer_system(voice_profile.markdown, format_exemplars(select_exemplars(project.prompt, samples)))
    result = await llm.structured(
        task="title options",
        system=system,
        prompt=render(
            "titles",
            count=count,
            prompt=project.prompt,
            outline=_outline(project.markdown) or project.prompt,
            keep="\n".join(f"- {t}" for t in keep) or "(none)",
            rejected="\n".join(f"- {t}" for t in rejected) or "(none)",
        ),
        schema=TitleOptions,
        effort=settings.effort_plan,
        max_tokens=8000,
    )
    fresh = [t for t in merge_titles(result.title_options) if t.casefold() not in {r.casefold() for r in rejected}]
    options = merge_titles(keep, fresh)[: max(TITLE_OPTION_COUNT, len(keep))]
    plan["title_options"] = options
    _save(engine, project_id, plan=plan)
    return options


def _outline(markdown: str) -> str:
    """Title, subtitle, headings and the opening paragraph: enough to title the post without resending it."""
    lines = [line for line in markdown.splitlines() if line.strip() and not PLACEHOLDER_RE.fullmatch(line.strip())]
    head = lines[:2]
    body = [line for line in lines[2:] if not line.startswith(("#", "```"))]
    headings = [line for line in lines if line.startswith("## ")]
    return "\n".join([*head, *(body[:1]), "", *headings]).strip()


def prompt_settings(dials: ResolvedDials) -> dict[str, Any]:
    include_code = {
        "auto": "include where they genuinely help the reader",
        "yes": "include key code snippets and/or LLM prompts",
        "no": "do not include code",
    }[dials.include_code]
    return {
        "topic": dials.topic,
        "audience": dials.audience or "the author's usual readers",
        "target_words": dials.target_words,
        "humor": dials.humor,
        "humor_guide": dials.humor_guide,
        "education": dials.education,
        "education_guide": dials.education_guide,
        "style_guide": dials.style_guide,
        "include_code": include_code,
        "platform": dials.platform,
        "platform_guide": dials.platform_guide,
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
