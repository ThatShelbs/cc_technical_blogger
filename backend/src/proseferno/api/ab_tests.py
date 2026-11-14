"""A/B Test Mode: two blind versions of a post, the author's choice, and adopting what won."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from sqlmodel import Session

from proseferno.abtest.service import (
    ABTestError,
    adopt,
    discard,
    retry_ab_test,
    role_of,
    start_ab_test,
    start_decision,
    suggested_tweaks,
    variant_id,
)
from proseferno.api.deps import ServicesDep, SessionDep, project_or_404
from proseferno.api.projects import _writable_persona, image_out, project_images
from proseferno.api.schemas import ABAdoptIn, ABAdoptOut, ABDecideIn, ABTestOut, ABTweakOut, ABVariantOut, GenerateIn, JobOut
from proseferno.db import ABTest, Project, utcnow
from proseferno.writer import word_count

router = APIRouter(prefix="/api")


def _test_or_404(session: Session, test_id: int) -> ABTest:
    test = session.get(ABTest, test_id)
    if test is None:
        raise HTTPException(404, "A/B test not found.")
    return test


def _variant_out(session: Session, test: ABTest, side: Literal["left", "right"]) -> ABVariantOut | None:
    project = session.get(Project, variant_id(test, role_of(test, side)) or 0)
    if project is None or project.id is None:
        return None
    return ABVariantOut(
        side=side,
        title=project.title,
        subtitle=project.subtitle,
        markdown=project.markdown,
        word_count=word_count(project.markdown),
        status=project.status,
        error=project.error,
        images=[image_out(i) for i in project_images(session, project.id)],
    )


def ab_test_out(session: Session, test: ABTest) -> ABTestOut:
    """Before the decision this says nothing about which post is which: no roles, settings, scores or tweaks."""
    assert test.id is not None
    decided = test.status == "decided"
    suggested = set(suggested_tweaks(test)) if decided else set()
    winner_side: Literal["left", "right"] | None = None
    if decided and test.winner:
        winner_side = "left" if test.left_role == test.winner else "right"
    return ABTestOut(
        id=test.id,
        project_id=test.project_id,
        persona_id=test.persona_id,
        status=test.status,
        error=test.error,
        left=None if decided else _variant_out(session, test, "left"),
        right=None if decided else _variant_out(session, test, "right"),
        winner=test.winner if decided else None,
        winner_side=winner_side,
        taken=list(test.taken or []) if decided else [],
        tweaks=[
            ABTweakOut(id=t["id"], group=t["group"], label=t["label"], before=t["before"], after=t["after"], suggested=t["id"] in suggested)
            for t in (test.tweaks or [])
        ]
        if decided
        else [],
        adopted=test.adopted if decided else None,
        evolution_id=test.evolution_id,
        created_at=test.created_at,
        decided_at=test.decided_at,
    )


def _job_out(job: object) -> JobOut:
    return JobOut(**job.model_dump())  # type: ignore[attr-defined]


@router.post("/projects/{project_id}/ab-tests", response_model=JobOut, status_code=202)
async def create_ab_test(project_id: int, session: SessionDep, services: ServicesDep, body: GenerateIn | None = None) -> JobOut:
    """Write the post twice (as the persona is, and with every setting nudged); with a body, first apply a new brief, dials or persona."""
    project = project_or_404(session, project_id)
    body = body or GenerateIn()
    persona_id = body.persona_id if body.persona_id is not None else project.persona_id
    _writable_persona(session, persona_id)
    if body.persona_id is not None or body.prompt is not None or body.dials is not None:
        project.persona_id = persona_id
        if body.prompt is not None:
            project.prompt = body.prompt.strip()
        if body.dials is not None:
            project.dials = body.dials.model_dump(exclude_none=True)
        project.updated_at = utcnow()
        session.add(project)
        session.commit()
    try:
        return _job_out(await start_ab_test(services, project_id))
    except ABTestError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/ab-tests/{test_id}", response_model=ABTestOut)
def get_ab_test(test_id: int, session: SessionDep) -> ABTestOut:
    return ab_test_out(session, _test_or_404(session, test_id))


@router.post("/ab-tests/{test_id}/decide", response_model=JobOut, status_code=202)
async def decide_ab_test(test_id: int, body: ABDecideIn, session: SessionDep, services: ServicesDep) -> JobOut:
    """Pick the winner (Post 1 = left, Post 2 = right) and, optionally, parts of the other post to keep."""
    _test_or_404(session, test_id)
    try:
        return _job_out(await start_decision(services, test_id, winner=body.winner, take=list(body.take), notes=body.notes))
    except ABTestError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/ab-tests/{test_id}/adopt", response_model=ABAdoptOut)
async def adopt_ab_test(test_id: int, body: ABAdoptIn, session: SessionDep, services: ServicesDep) -> ABAdoptOut:
    """Make the chosen tweaks part of the persona; an empty list keeps the persona as it is."""
    _test_or_404(session, test_id)
    try:
        job = await adopt(services, test_id, body.tweak_ids)
    except ABTestError as exc:
        raise HTTPException(409, str(exc)) from exc
    session.expire_all()
    return ABAdoptOut(ab_test=ab_test_out(session, _test_or_404(session, test_id)), job=_job_out(job) if job else None)


@router.post("/ab-tests/{test_id}/retry", response_model=JobOut, status_code=202)
async def retry(test_id: int, session: SessionDep, services: ServicesDep) -> JobOut:
    _test_or_404(session, test_id)
    try:
        return _job_out(await retry_ab_test(services, test_id))
    except ABTestError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.delete("/ab-tests/{test_id}", status_code=204)
def discard_ab_test(test_id: int, session: SessionDep, services: ServicesDep) -> None:
    """Drop an open test and both its posts; the project keeps whatever it had."""
    try:
        discard(session, services, _test_or_404(session, test_id))
    except ABTestError as exc:
        raise HTTPException(409, str(exc)) from exc
