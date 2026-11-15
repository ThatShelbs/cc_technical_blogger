"""Idea Lab jobs: run a brainstorm for a persona, and hand an idea to the writer as a brief."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import Engine
from sqlmodel import Session, col, select

from proseferno.config import Settings
from proseferno.db import Idea, IdeaSession, Persona
from proseferno.idealab.collect import SignalCollector
from proseferno.idealab.ideate import APPROACH_LABELS, IdeaContext, availability, brainstorm, plan_mix
from proseferno.idealab.portfolio import snapshot
from proseferno.idealab.research import Depth, current_trends, is_fresh, run_research
from proseferno.jobs import JobContext
from proseferno.llm import LLM
from proseferno.voice.pipeline import current_voice_profile
from proseferno.voice.playbook import format_playbook

log = logging.getLogger(__name__)

BRAINSTORM_JOB = "idea_brainstorm"
IDEA_JOBS: tuple[str, ...] = ("idea_research", BRAINSTORM_JOB)
PROFILE_CHARS = 5000
FEEDBACK_IDEAS = 40
# How many earlier ideas (newest first) a brainstorm checks its titles against.
KNOWN_IDEAS = 1000


class IdeaLabError(RuntimeError):
    pass


def author_context(session: Session, persona: Persona) -> str:
    """Who the ideas are for: the voice profile in use (clipped) and what has worked for the author."""
    assert persona.id is not None
    parts = [f"Name: {persona.display_name or persona.name}"]
    profile = current_voice_profile(session, persona.id)
    if profile is not None and profile.markdown.strip():
        text = profile.markdown.strip()
        if len(text) > PROFILE_CHARS:
            text = text[:PROFILE_CHARS].rstrip() + "\n\n[... the rest of the voice profile is omitted ...]"
        parts.append("## Voice profile\n\n" + text)
    if playbook := format_playbook(persona.playbook):
        parts.append("## What has worked in their posts that did well\n\n" + playbook)
    return "\n\n".join(parts)


def _feedback(session: Session, persona_id: int) -> tuple[list[str], list[str], list[str]]:
    """Saved or written, dismissed, and every other idea on file: none of them may come back in a new brainstorm."""
    rows = session.exec(
        select(Idea.title, Idea.state).where(Idea.persona_id == persona_id).order_by(col(Idea.id).desc()).limit(KNOWN_IDEAS)
    ).all()
    liked = [title for title, state in rows if state in ("saved", "used")]
    passed = [title for title, state in rows if state == "dismissed"]
    earlier = [title for title, state in rows if state == "new"]
    return liked[:FEEDBACK_IDEAS], passed[:FEEDBACK_IDEAS], earlier


async def run_brainstorm(
    *,
    engine: Engine,
    llm: LLM,
    settings: Settings,
    collector: SignalCollector,
    session_id: int,
    extras: list[str],
    refresh: bool | None,
    depth: Depth,
    ctx: JobContext,
) -> dict[str, Any]:
    """Refresh the research when it is stale (or when asked), then write, rank and store the ideas.

    ``refresh``: True = always research first, False = never, None = only when the base is older than a day.
    """
    try:
        with Session(engine) as session:
            row = session.get(IdeaSession, session_id)
            if row is None:
                raise IdeaLabError("That brainstorm no longer exists.")
            mode, persona_id = row.mode, row.persona_id
            needs_research = refresh if refresh is not None else not is_fresh(session)

        notes: list[str] = []
        ideas_from = 0.0
        if needs_research:
            ideas_from = 0.55
            try:
                await run_research(
                    engine=engine, llm=llm, settings=settings, collector=collector, ctx=ctx, depth=depth, span=(0.0, ideas_from)
                )
            except Exception as exc:
                log.warning("Research failed during a brainstorm", exc_info=True)
                notes.append(f"The live research could not run ({str(exc)[:160]}), so these ideas use what was already on file.")

        with Session(engine) as session:
            persona = session.get(Persona, persona_id)
            row = session.get(IdeaSession, session_id)
            if persona is None or row is None:
                raise IdeaLabError("That persona no longer exists.")
            trends = current_trends(session)
            for trend in trends:
                session.expunge(trend)
            portfolio = snapshot(session, persona_id)
            liked, passed, earlier = _feedback(session, persona_id)
            context = IdeaContext(
                author=author_context(session, persona),
                portfolio=portfolio,
                trends=trends,
                focus=row.focus,
                sparks=row.sparks,
                liked=liked,
                passed=passed,
                earlier=earlier,
            )
            mix, mix_notes = plan_mix(mode, extras, availability(trends, portfolio, row.sparks))
            notes += mix_notes
            row.mix = mix
            session.add(row)
            session.commit()

        chosen = await brainstorm(llm, settings, context, mix, ctx=ctx, span=(ideas_from, 1.0))
        if not chosen:
            raise IdeaLabError("Claude returned no usable ideas. Try again, or refresh the research first.")
        wanted = sum(mix.values())
        if len(chosen) < wanted:
            notes.append(f"Only {len(chosen)} of {wanted} ideas were distinct enough to keep.")

        with Session(engine) as session:
            for position, candidate in enumerate(chosen, start=1):
                draft = candidate.draft
                session.add(
                    Idea(
                        session_id=session_id,
                        persona_id=persona_id,
                        approach=candidate.approach,
                        theme=candidate.theme,
                        title=draft.title,
                        brief=draft.brief.strip(),
                        angle=draft.angle.strip(),
                        outline=draft.outline,
                        why_now=draft.why_now.strip(),
                        shelf_life=draft.shelf_life,
                        tags=draft.tags,
                        evidence=candidate.evidence,
                        article_type=draft.article_type,
                        builds_on=draft.builds_on,
                        scores=candidate.scores,
                        score=round(candidate.score, 2),
                        rank=position,
                    )
                )
            row = session.get(IdeaSession, session_id)
            assert row is not None
            row.status = "ready"
            row.notes = notes
            session.add(row)
            session.commit()
        return {"session_id": session_id, "ideas": len(chosen)}
    except Exception as exc:
        with Session(engine) as session:
            row = session.get(IdeaSession, session_id)
            if row is not None:
                row.status = "error"
                row.error = str(exc)[:500] or exc.__class__.__name__
                session.add(row)
                session.commit()
        raise


def fail_interrupted(engine: Engine) -> None:
    """Jobs live in memory, so a brainstorm still "running" at startup lost its job in a previous run."""
    with Session(engine) as session:
        for row in session.exec(select(IdeaSession).where(IdeaSession.status == "running")):
            row.status = "error"
            row.error = "Interrupted because Proseferno was restarted."
            session.add(row)
        session.commit()


def idea_brief(idea: Idea) -> str:
    """The idea as a brief for the writer: the title on the first line, then the angle, outline and sources."""
    lines = [idea.title.strip()]
    if idea.brief.strip():
        lines += ["", idea.brief.strip()]
    if idea.angle.strip():
        lines += ["", f"Angle: {idea.angle.strip()}"]
    if idea.builds_on.strip():
        lines += ["", f'This follows on from my earlier post "{idea.builds_on.strip()}".']
    if idea.outline:
        lines += ["", "Outline:", *(f"- {point}" for point in idea.outline)]
    if idea.why_now.strip():
        lines += ["", f"Why now: {idea.why_now.strip()}"]
    if idea.evidence:
        lines += [
            "",
            "Sources to draw on:",
            *(f"- {link.get('title') or link.get('url')}: {link.get('url')}" for link in idea.evidence[:6]),
        ]
    return "\n".join(lines)


def approach_label(approach: str) -> str:
    return APPROACH_LABELS.get(approach, approach)
