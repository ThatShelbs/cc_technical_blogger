"""Keep a post's text in step with its images.

When an image is redrawn the sentences that described the old one (a meme's format, a diagram's labels) can go
stale, so ``sync_text_to_images`` asks Claude for small find/replace edits, the same kind a feedback tweak makes.
``save_text_change`` is the shared way to store a text change: an undo point, fresh measures, the new text.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy import Engine
from sqlmodel import Session, select

from proseferno.authenticity import analyze, author_profile
from proseferno.config import Settings
from proseferno.db import Persona, Project, ProjectImage, Sample, utcnow
from proseferno.images import PLACEHOLDER_RE
from proseferno.images.memes import get_format
from proseferno.images.memes import load_state as load_meme_state
from proseferno.images.opening.room import load_state as load_opening_state
from proseferno.images.opening.styles import get_style
from proseferno.images.service import meme_spec
from proseferno.llm import LLM
from proseferno.llm.base import UsageSink
from proseferno.prompts import render
from proseferno.voice import current_voice_profile, format_exemplars, select_exemplars
from proseferno.voice.lessons import format_lessons
from proseferno.voice.playbook import format_playbook
from proseferno.writer.pipeline import WriterError, measure, split_title, writer_system
from proseferno.writer.revisions import RevisionKind, push_revision
from proseferno.writer.schemas import ImageTextEdits
from proseferno.writer.tweak import apply_edits, finish_text

log = logging.getLogger(__name__)


def describe_image(image: ProjectImage) -> str:
    """What an image is and shows, in words, so a change to it can be told to the editor. Empty for uploads and failures."""
    if image.provider in ("upload", "placeholder") or image.status == "error":
        return ""
    lines = [f"{image.kind} image `{image.slot_id}`"]
    if image.purpose:
        lines.append(f"Purpose: {image.purpose}")
    opening = load_opening_state(image.spec) if image.kind == "hero" else None
    if opening:
        style = get_style(str(opening.get("style", "")))
        if style:
            lines.append(f"Style: {style.label}")
        chosen = opening.get("chosen")
        concepts = opening.get("concepts") or []
        if isinstance(chosen, int) and 0 <= chosen < len(concepts):
            lines.append(f"Idea: {concepts[chosen].get('concept', '')}")
    meme = load_meme_state(meme_spec(image))
    if meme:
        fmt = get_format(str(meme.get("format", "")))
        if fmt:
            lines.append(f"Format: {fmt.name}")
        chosen = meme.get("chosen")
        pitches = meme.get("concepts") or []
        if isinstance(chosen, int) and 0 <= chosen < len(pitches):
            pitch = pitches[chosen]
            lines.append(f"Joke: {pitch.get('premise', '')}")
            words = " / ".join(str(t.get("text", "")) for t in pitch.get("texts") or [] if t.get("text"))
            if words:
                lines.append(f"Words: {words}")
    if image.alt:
        lines.append(f"Alt text: {image.alt}")
    if image.caption:
        lines.append(f"Caption: {image.caption}")
    return "\n".join(lines)


def _describe_changes(changes: list[tuple[str, str, str]]) -> str:
    return "\n\n".join(f"### `{slot}`\nWas:\n{before}\n\nNow:\n{after}" for slot, before, after in changes)


async def save_text_change(
    *,
    engine: Engine,
    llm: LLM,
    settings: Settings,
    project_id: int,
    markdown: str,
    label: str,
    kind: RevisionKind,
    usage: UsageSink | None = None,
    also: Callable[[Session, Project], None] | None = None,
) -> None:
    """Store a new text for the post with an undo point and fresh measures. ``also`` can change other rows in the same commit."""
    with Session(engine, expire_on_commit=False) as session:
        project = session.get(Project, project_id)
        persona = session.get(Persona, project.persona_id) if project else None
        voice_profile = current_voice_profile(session, project.persona_id) if project else None
        samples = list(session.exec(select(Sample).where(Sample.persona_id == project.persona_id))) if project else []
    if project is None or persona is None or voice_profile is None:
        raise WriterError("The post, its persona or its voice profile no longer exists.")
    title, subtitle = split_title(markdown)
    authenticity = await analyze(
        llm=llm,
        settings=settings,
        markdown=markdown,
        voice_profile=voice_profile.markdown,
        profile=author_profile(samples, voice_profile.baseline_stylometrics),
        use_judge=settings.ai_detection,
        usage=usage,
    )
    with Session(engine) as session:
        row = session.get(Project, project_id)
        if row is None:
            raise WriterError("Project not found.")
        push_revision(row, label, kind)
        row.markdown, row.title, row.subtitle = markdown, title or row.title, subtitle or row.subtitle
        row.fidelity = measure(markdown, voice_profile.baseline_stylometrics)
        row.authenticity = authenticity
        row.updated_at = utcnow()
        session.add(row)
        if also is not None:
            also(session, row)
        session.commit()


async def sync_text_to_images(
    *,
    engine: Engine,
    llm: LLM,
    settings: Settings,
    project_id: int,
    changes: list[tuple[str, str, str]],
    usage: UsageSink | None = None,
) -> dict[str, Any]:
    """Edit the text that described images that have since changed; ``changes`` are (slot id, before, after) descriptions.

    Returns ``text_edits`` (how many edits were applied) and ``text_summary``. Makes no call when nothing really changed.
    """
    none: dict[str, Any] = {"text_edits": 0, "text_summary": ""}
    with Session(engine, expire_on_commit=False) as session:
        project = session.get(Project, project_id)
        if project is None or not project.markdown:
            return none
        persona = session.get(Persona, project.persona_id)
        voice_profile = current_voice_profile(session, project.persona_id)
        samples = list(session.exec(select(Sample).where(Sample.persona_id == project.persona_id)))
    if persona is None or voice_profile is None:
        return none
    present = set(PLACEHOLDER_RE.findall(project.markdown))
    changes = [(slot, before, after) for slot, before, after in changes if before and after and before != after and slot in present]
    if not changes:
        return none

    result = await llm.structured(
        task="image text sync",
        system=writer_system(
            voice_profile.markdown,
            format_exemplars(select_exemplars(project.prompt, samples)),
            format_lessons(persona.edit_lessons),
            format_playbook(persona.playbook),
        ),
        prompt=render("image_text_sync", changes=_describe_changes(changes), markdown=project.markdown),
        schema=ImageTextEdits,
        effort=settings.effort_critique,
        max_tokens=16000,
        usage=usage,
    )
    markdown, applied, _skipped = apply_edits(project.markdown, result.edits)
    if not applied:
        return none
    slots = sorted({slot for slot, _, _ in changes})
    await save_text_change(
        engine=engine,
        llm=llm,
        settings=settings,
        project_id=project_id,
        markdown=finish_text(markdown, project.plan),
        label=f"Before matching the text to the redrawn image ({', '.join(slots)})",
        kind="image",
        usage=usage,
    )
    return {"text_edits": applied, "text_summary": result.summary.strip()}


def failed_sync_result(error: Exception) -> dict[str, Any]:
    """What a job reports when the text could not be matched to the image: the redraw itself still succeeded."""
    log.warning("Could not match the text to the redrawn image: %s", error)
    return {"text_edits": 0, "text_summary": "", "text_error": "The image was redrawn, but the text around it could not be checked."}
