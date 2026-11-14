"""References in a post: add more, redraw one, swap back an earlier version, or remove one."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from proseferno.api.deps import ServicesDep, SessionDep, project_or_404, reference_or_404
from proseferno.api.projects import _check_idle, _writable_persona, project_out
from proseferno.api.schemas import EnrichIn, JobOut, ProjectOut, ReferenceRedrawIn, RevertIn
from proseferno.voice import current_voice_profile
from proseferno.writer import WriterError
from proseferno.writer.examples import fill_missing_examples
from proseferno.writer.references import enrich_post, redraw_reference, remove_reference, revert_reference

router = APIRouter(prefix="/api")


@router.post("/projects/{project_id}/references", response_model=JobOut, status_code=202)
async def add_references(project_id: int, session: SessionDep, services: ServicesDep, body: EnrichIn | None = None) -> JobOut:
    """Find and weave in more references (all of them, for a post written with references off)."""
    project = project_or_404(session, project_id)
    if not project.markdown:
        raise HTTPException(409, "Generate the post before adding references.")
    _writable_persona(session, project.persona_id)
    _check_idle(services, project_id)
    body = body or EnrichIn()
    job = await services.jobs.start(
        "enrich_post",
        lambda ctx: enrich_post(
            engine=services.engine,
            llm=services.llm,
            settings=services.settings,
            links=services.links,
            project_id=project_id,
            count=body.count,
            kinds=list(body.kinds) if body.kinds else None,
            ctx=ctx,
        ),
        project_id=project_id,
    )
    return JobOut(**job.model_dump())


@router.post("/projects/{project_id}/examples", response_model=JobOut, status_code=202)
async def add_missing_examples(project_id: int, session: SessionDep, services: ServicesDep) -> JobOut:
    """Draw an image after every lead-in ("Here is the file:") that has nothing after it, for posts written before that was checked."""
    project = project_or_404(session, project_id)
    if not project.markdown:
        raise HTTPException(409, "Generate the post first.")
    _writable_persona(session, project.persona_id)
    _check_idle(services, project_id)
    job = await services.jobs.start(
        "fill_examples",
        lambda ctx: fill_missing_examples(engine=services.engine, images=services.images, project_id=project_id, ctx=ctx),
        project_id=project_id,
    )
    return JobOut(**job.model_dump())


@router.post("/references/{reference_id}/redraw", response_model=JobOut, status_code=202)
async def redraw(reference_id: int, session: SessionDep, services: ServicesDep, body: ReferenceRedrawIn | None = None) -> JobOut:
    """Find a different reference for the same spot (of another ``kind`` if given) and swap it into the text."""
    reference = reference_or_404(session, reference_id)
    project = project_or_404(session, reference.project_id)
    _writable_persona(session, project.persona_id)
    _check_idle(services, project.id or 0)
    kind = body.kind if body else None
    job = await services.jobs.start(
        "redraw_reference",
        lambda ctx: redraw_reference(
            engine=services.engine,
            llm=services.llm,
            settings=services.settings,
            links=services.links,
            reference_id=reference_id,
            kind=kind,
            ctx=ctx,
        ),
        project_id=project.id,
    )
    return JobOut(**job.model_dump())


@router.post("/references/{reference_id}/revert", response_model=ProjectOut)
def revert(reference_id: int, body: RevertIn, session: SessionDep, services: ServicesDep) -> ProjectOut:
    """Put an earlier version of this reference back into the post (undoable from the post's history)."""
    reference = reference_or_404(session, reference_id)
    project = project_or_404(session, reference.project_id)
    _check_idle(services, reference.project_id)
    voice_profile = current_voice_profile(session, project.persona_id)
    try:
        revert_reference(session, reference, project, body.index, voice_profile.baseline_stylometrics if voice_profile else None)
    except IndexError as exc:
        raise HTTPException(404, "No such version.") from exc
    except WriterError as exc:
        raise HTTPException(409, str(exc)) from exc
    session.commit()
    session.refresh(project)
    return project_out(session, project, services)


@router.delete("/references/{reference_id}", response_model=ProjectOut)
def remove(reference_id: int, session: SessionDep, services: ServicesDep) -> ProjectOut:
    """Take the reference out of the post; the sentence it was in reads as it did before."""
    reference = reference_or_404(session, reference_id)
    project = project_or_404(session, reference.project_id)
    _check_idle(services, reference.project_id)
    voice_profile = current_voice_profile(session, project.persona_id)
    remove_reference(session, reference, project, voice_profile.baseline_stylometrics if voice_profile else None)
    session.commit()
    session.refresh(project)
    return project_out(session, project, services)
