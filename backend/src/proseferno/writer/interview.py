"""The optional interview: before writing, Claude asks the author 3-5 questions about this post.

Off by default (a toggle per post, ``Persona.default_interview`` for a persona's posts). The questions go after what
only the author has: their stories, opinions, mistakes, numbers and examples for this brief. Answers are woven into the
post close to verbatim (``pipeline.format_author_material``); skipped ones are ignored, and the writer still fills
every gap the way the author would.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import Engine
from sqlmodel import Session

from proseferno.config import Settings
from proseferno.db import Project, utcnow
from proseferno.llm import LLM, SystemBlock
from proseferno.prompts import raw, render
from proseferno.voice import current_voice_profile
from proseferno.writer.pipeline import WriterError

MIN_QUESTIONS, MAX_QUESTIONS = 3, 5


class InterviewQuestions(BaseModel):
    questions: list[str] = Field(description="Three to five short questions for the author, most valuable first.")


def clean_questions(questions: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for question in (q.strip() for q in questions):
        if question and question.casefold() not in seen:
            seen.add(question.casefold())
            out.append(question[:500])
    return out[:MAX_QUESTIONS]


async def plan_interview(*, llm: LLM, settings: Settings, engine: Engine, project_id: int) -> list[dict[str, Any]]:
    """Write the questions for this post's brief and store them (unanswered) on the project."""
    with Session(engine) as session:
        project = session.get(Project, project_id)
        if project is None:
            raise WriterError("Project not found.")
        voice_profile = current_voice_profile(session, project.persona_id)
        brief = project.prompt
    result = await llm.structured(
        task="interview",
        system=[
            SystemBlock(raw("interview_system")),
            SystemBlock(f"# The author's voice profile\n\n{voice_profile.markdown if voice_profile else '_None yet._'}", cache=True),
        ],
        prompt=render("interview", brief=brief, min=MIN_QUESTIONS, max=MAX_QUESTIONS),
        schema=InterviewQuestions,
        effort="low",
        max_tokens=4000,
    )
    questions = clean_questions(result.questions)
    if len(questions) < MIN_QUESTIONS:
        raise WriterError("Claude did not come up with enough questions. Try again, or write the post without the interview.")
    interview = [{"question": q, "answer": ""} for q in questions]
    with Session(engine) as session:
        row = session.get(Project, project_id)
        if row is None:
            raise WriterError("Project not found.")
        row.interview = interview
        row.updated_at = utcnow()
        session.add(row)
        session.commit()
    return interview
