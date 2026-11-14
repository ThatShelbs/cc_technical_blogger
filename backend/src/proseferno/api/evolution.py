"""Persona evolution: proposals learned from published posts, the playbook, and baseline comparisons."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlmodel import col, select

from proseferno.api.deps import ServicesDep, SessionDep, persona_or_404, project_or_404
from proseferno.api.personas import persona_out
from proseferno.api.schemas import (
    ApplyEvolutionIn,
    BaselineDiffOut,
    DiffSegment,
    EditRatePoint,
    EvolutionItemOut,
    EvolutionOut,
    EvolveIn,
    JobOut,
    PersonaEvolutionOut,
    PersonaOut,
    PlaybookEntry,
)
from proseferno.db import PersonaEvolution, utcnow
from proseferno.evolution import EvolutionError, diff_segments, dismiss, edit_rate, start_analysis, start_apply
from proseferno.voice.playbook import forget_playbook

router = APIRouter(prefix="/api")


def evolution_out(row: PersonaEvolution) -> EvolutionOut:
    return EvolutionOut(
        **row.model_dump(exclude={"items", "baseline_hash"}),
        items=[EvolutionItemOut(**item) for item in row.items or []],
    )


def _evolution_or_404(session: SessionDep, evolution_id: int) -> PersonaEvolution:
    row = session.get(PersonaEvolution, evolution_id)
    if row is None:
        raise HTTPException(404, "Proposal not found.")
    return row


@router.get("/personas/{persona_id}/evolution", response_model=PersonaEvolutionOut)
def persona_evolution(persona_id: int, session: SessionDep) -> PersonaEvolutionOut:
    """Every proposal for this persona (newest first), the edit-rate trend, and the playbook."""
    persona = persona_or_404(session, persona_id)
    rows = session.exec(
        select(PersonaEvolution).where(PersonaEvolution.persona_id == persona_id).order_by(col(PersonaEvolution.created_at).desc())
    ).all()
    rates = [
        EditRatePoint(project_id=r.project_id, title=r.project_title, edit_rate=r.edit_rate, created_at=r.created_at)
        for r in reversed(rows)
        if r.kind == "edits" and r.edit_rate is not None
    ]
    return PersonaEvolutionOut(
        evolutions=[evolution_out(r) for r in rows],
        edit_rates=rates,
        playbook=[PlaybookEntry(**entry) for entry in persona.playbook or []],
    )


@router.post("/projects/{project_id}/evolutions", response_model=EvolutionOut)
async def evolve_project(project_id: int, body: EvolveIn, session: SessionDep, services: ServicesDep) -> EvolutionOut:
    """Analyze a post (again): its edits against the generated text, or its secret sauce."""
    project_or_404(session, project_id)
    try:
        return evolution_out(await start_analysis(services, project_id, body.kind))
    except EvolutionError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/projects/{project_id}/baseline-diff", response_model=BaselineDiffOut)
def baseline_diff(project_id: int, session: SessionDep) -> BaselineDiffOut:
    """The generated text against the current text, word by word."""
    project = project_or_404(session, project_id)
    if not project.baseline_markdown:
        raise HTTPException(404, "This post has no generated text on record. Regenerate it to start tracking edits.")
    return BaselineDiffOut(
        edit_rate=edit_rate(project.baseline_markdown, project.markdown),
        baseline_title=project.baseline_title,
        segments=[DiffSegment(**s) for s in diff_segments(project.baseline_markdown, project.markdown)],
    )


@router.post("/evolutions/{evolution_id}/apply", response_model=JobOut)
async def apply_proposal(evolution_id: int, body: ApplyEvolutionIn, session: SessionDep, services: ServicesDep) -> JobOut:
    """Apply the chosen changes: playbook entries, and a new voice profile version for profile changes."""
    _evolution_or_404(session, evolution_id)
    try:
        job = await start_apply(services, evolution_id, body.item_ids)
    except EvolutionError as exc:
        raise HTTPException(422, str(exc)) from exc
    return JobOut(**job.model_dump())


@router.post("/evolutions/{evolution_id}/dismiss", response_model=EvolutionOut)
def dismiss_proposal(evolution_id: int, session: SessionDep) -> EvolutionOut:
    row = _evolution_or_404(session, evolution_id)
    try:
        dismiss(session, row)
    except EvolutionError as exc:
        raise HTTPException(422, str(exc)) from exc
    session.refresh(row)
    return evolution_out(row)


@router.delete("/personas/{persona_id}/playbook", response_model=PersonaOut)
def forget_playbook_entries(persona_id: int, session: SessionDep, services: ServicesDep, index: int | None = None) -> PersonaOut:
    """Forget one playbook entry (by ``index``) or all of them."""
    persona = persona_or_404(session, persona_id)
    if index is not None and not 0 <= index < len(persona.playbook or []):
        raise HTTPException(404, "No such playbook entry.")
    forget_playbook(persona, index)
    persona.updated_at = utcnow()
    session.add(persona)
    session.commit()
    session.refresh(persona)
    return persona_out(session, persona, services)
