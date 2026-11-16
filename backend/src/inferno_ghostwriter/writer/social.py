"""Companion posts for social platforms, written in the author's voice."""

from __future__ import annotations

from pydantic import BaseModel, Field
from sqlalchemy import Engine
from sqlmodel import Session, select

from inferno_ghostwriter.config import Settings
from inferno_ghostwriter.db import Persona, Project, Sample, utcnow
from inferno_ghostwriter.export import fit_post
from inferno_ghostwriter.export.linkedin import hashtags
from inferno_ghostwriter.llm import LLM
from inferno_ghostwriter.prompts import render
from inferno_ghostwriter.voice import current_voice_profile, format_exemplars, select_exemplars
from inferno_ghostwriter.voice.lessons import format_lessons
from inferno_ghostwriter.voice.playbook import format_playbook
from inferno_ghostwriter.writer.pipeline import WriterError, writer_system


class LinkedInPost(BaseModel):
    hook: str = Field(description="The first one or two lines, under 200 characters: what makes a practitioner stop scrolling.")
    body: str = Field(description="The rest of the post in plain text: short lines, blank lines between ideas, no Markdown.")
    hashtags: list[str] = Field(description="Three to five relevant hashtags, without the # sign.")


async def write_linkedin_post(*, llm: LLM, settings: Settings, engine: Engine, project_id: int) -> str:
    with Session(engine) as session:
        project = session.get(Project, project_id)
        if project is None:
            raise WriterError("Project not found.")
        if not project.markdown:
            raise WriterError("Generate the post before writing its LinkedIn post.")
        voice_profile = current_voice_profile(session, project.persona_id)
        samples = list(session.exec(select(Sample).where(Sample.persona_id == project.persona_id)))
        persona = session.get(Persona, project.persona_id)
    if voice_profile is None:
        raise WriterError("This persona has no voice profile yet.")
    lessons = format_lessons(persona.edit_lessons if persona else None)
    playbook = format_playbook(persona.playbook if persona else None)
    system = writer_system(voice_profile.markdown, format_exemplars(select_exemplars(project.prompt, samples)), lessons, playbook)
    post = await llm.structured(
        task="linkedin post",
        system=system,
        prompt=render("linkedin_post", markdown=project.markdown, tags=", ".join((project.plan or {}).get("tags", []))),
        schema=LinkedInPost,
        effort=settings.effort_critique,
    )
    tags = " ".join(hashtags(post.hashtags))
    text = fit_post(f"{post.hook.strip()}\n\n{post.body.strip()}" + (f"\n\n{tags}" if tags else ""))
    with Session(engine) as session:
        row = session.get(Project, project_id)
        if row is not None:
            row.social = {**(row.social or {}), "linkedin_post": text}
            row.updated_at = utcnow()
            session.add(row)
            session.commit()
    return text
