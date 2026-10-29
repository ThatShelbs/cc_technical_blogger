"""Persona helpers shared by the API routes and the example seeding."""

from __future__ import annotations

import shutil

from sqlmodel import Session, col, delete, select

from proseferno.db import Persona, Project, ProjectImage, Sample, VoiceProfile
from proseferno.ingest import ParsedDocument
from proseferno.ingest.stylometrics import compute
from proseferno.storage import Storage

MIN_SAMPLE_WORDS = 50


def add_sample(session: Session, persona_id: int, kind: str, source_name: str, doc: ParsedDocument) -> Sample:
    if doc.word_count < MIN_SAMPLE_WORDS:
        raise ValueError(f"{source_name}: not enough text to learn from ({doc.word_count} words).")
    sample = Sample(
        persona_id=persona_id,
        kind=kind,
        source_name=source_name,
        source_type=doc.source_type,
        title=doc.title or source_name.rsplit(".", 1)[0],
        subtitle=doc.subtitle,
        author=doc.author,
        markdown=doc.to_markdown(),
        word_count=doc.word_count,
        image_count=doc.image_count,
        captions=doc.captions,
        stylometrics=compute(doc),
    )
    session.add(sample)
    session.commit()
    session.refresh(sample)
    return sample


def delete_persona_data(session: Session, storage: Storage, persona: Persona) -> bool:
    """Delete a persona with its posts, images, samples, voice profiles and files. True if it was the active one."""
    assert persona.id is not None
    persona_id = persona.id
    project_ids = [pid for pid in session.exec(select(Project.id).where(Project.persona_id == persona_id)) if pid is not None]
    if project_ids:
        session.exec(delete(ProjectImage).where(col(ProjectImage.project_id).in_(project_ids)))  # type: ignore[call-overload]
        session.exec(delete(Project).where(col(Project.persona_id) == persona_id))  # type: ignore[call-overload]
    session.exec(delete(Sample).where(col(Sample.persona_id) == persona_id))  # type: ignore[call-overload]
    session.exec(delete(VoiceProfile).where(col(VoiceProfile.persona_id) == persona_id))  # type: ignore[call-overload]
    was_active = persona.is_active
    session.delete(persona)
    session.commit()
    shutil.rmtree(storage.persona_dir(persona_id), ignore_errors=True)
    for pid in project_ids:
        shutil.rmtree(storage.project_dir(pid), ignore_errors=True)
    return was_active
