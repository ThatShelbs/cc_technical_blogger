"""Idea Lab: the research base, its sources, brainstorms, and sending an idea to the writer."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func
from sqlmodel import Session, col, select

from inferno_ghostwriter.api.deps import ServicesDep, SessionDep, persona_or_404
from inferno_ghostwriter.api.projects import create_project
from inferno_ghostwriter.api.schemas import (
    IdeaCreate,
    IdeaLabOut,
    IdeaLink,
    IdeaOut,
    IdeaResearchIn,
    IdeaSearchOut,
    IdeaSessionCreated,
    IdeaSessionIn,
    IdeaSessionOut,
    IdeaSessionSummary,
    IdeaSourceOut,
    IdeaSourcesIn,
    IdeaSourcesOut,
    IdeaState,
    IdeaTrendOut,
    IdeaUpdate,
    IdeaWriteIn,
    JobOut,
    ProjectCreate,
    ProjectCreated,
)
from inferno_ghostwriter.db import Idea, IdeaSession, IdeaSignal, IdeaTrend, Persona, Project
from inferno_ghostwriter.idealab import BRAINSTORM_JOB, IDEA_JOBS, RESEARCH_JOB, idea_brief
from inferno_ghostwriter.idealab.lifecycle import BANK_STATES, stage_label, stage_of
from inferno_ghostwriter.idealab.research import current_trends, is_fresh, load_state, run_research
from inferno_ghostwriter.idealab.service import approach_label, run_brainstorm
from inferno_ghostwriter.idealab.sources import (
    GROUP_LABELS,
    CustomSource,
    SourceChanges,
    SourceConfig,
    build_config,
    load_changes,
    load_config,
    load_health,
    save_changes,
)
from inferno_ghostwriter.services import Services
from inferno_ghostwriter.writer import Dials
from inferno_ghostwriter.writer.formulas import ARTICLE_TYPES

router = APIRouter(prefix="/api")


def _links(rows: list[dict]) -> list[IdeaLink]:  # type: ignore[type-arg]
    return [IdeaLink(url=str(r.get("url") or ""), title=str(r.get("title") or r.get("url") or "")) for r in rows if r.get("url")]


def trend_out(trend: IdeaTrend) -> IdeaTrendOut:
    assert trend.id is not None
    return IdeaTrendOut(**trend.model_dump(exclude={"evidence", "id"}), id=trend.id, evidence=_links(trend.evidence))


def idea_out(idea: Idea, project: Project | None = None) -> IdeaOut:
    assert idea.id is not None
    stage = stage_of(idea, project)
    return IdeaOut(
        **idea.model_dump(exclude={"evidence", "id", "state"}),
        id=idea.id,
        state=idea.state,  # type: ignore[arg-type]
        stage=stage,  # type: ignore[arg-type]
        stage_label=stage_label(stage),
        project_title=project.title if project else None,
        approach_label=approach_label(idea.approach),
        evidence=_links(idea.evidence),
        prompt=idea_brief(idea),
    )


def ideas_out(session: Session, ideas: Sequence[Idea]) -> list[IdeaOut]:
    """Ideas with their stage, reading each linked post once."""
    ids = [i.project_id for i in ideas if i.project_id is not None]
    projects = {p.id: p for p in session.exec(select(Project).where(col(Project.id).in_(ids)))} if ids else {}
    return [idea_out(i, projects.get(i.project_id)) for i in ideas]


def _one_out(session: Session, idea: Idea) -> IdeaOut:
    return ideas_out(session, [idea])[0]


def _summary(session: Session, row: IdeaSession, names: dict[int | None, str]) -> dict:  # type: ignore[type-arg]
    count = session.exec(select(func.count()).select_from(Idea).where(Idea.session_id == row.id)).one()
    return {
        **row.model_dump(include={"id", "persona_id", "mode", "status", "error", "created_at"}),
        "persona_name": names.get(row.persona_id, ""),
        "ideas": count,
    }


def session_out(session: Session, row: IdeaSession) -> IdeaSessionOut:
    names = {p.id: p.name for p in session.exec(select(Persona))}
    ideas = session.exec(select(Idea).where(Idea.session_id == row.id).order_by(col(Idea.rank))).all()
    return IdeaSessionOut(
        **_summary(session, row, names),
        mix={k: int(v) for k, v in (row.mix or {}).items()},
        focus=row.focus,
        sparks=row.sparks,
        notes=list(row.notes or []),
        job_id=row.job_id,
        items=ideas_out(session, ideas),
    )


def _session_or_404(session: Session, session_id: int) -> IdeaSession:
    row = session.get(IdeaSession, session_id)
    if row is None:
        raise HTTPException(404, "Brainstorm not found.")
    return row


def _idea_or_404(session: Session, idea_id: int) -> Idea:
    idea = session.get(Idea, idea_id)
    if idea is None:
        raise HTTPException(404, "Idea not found.")
    return idea


def _research_job(services: Services) -> str | None:
    running = services.jobs.active_for(kinds=(RESEARCH_JOB,))
    return running[0].id if running else None


# -- research base ----------------------------------------------------------------------


@router.get("/idea-lab", response_model=IdeaLabOut)
def idea_lab(session: SessionDep, services: ServicesDep) -> IdeaLabOut:
    state = load_state(session)
    return IdeaLabOut(
        signals=session.exec(select(func.count()).select_from(IdeaSignal)).one(),
        trends=[trend_out(t) for t in current_trends(session)],
        last_refresh=state.get("last_refresh"),
        fresh=is_fresh(session),
        scouts_failed=list(state.get("scouts_failed") or []),
        searches=[IdeaSearchOut(**s) for s in state.get("searches") or []],
        active_job_id=_research_job(services),
    )


@router.post("/idea-lab/research", response_model=JobOut, status_code=202)
async def research(body: IdeaResearchIn, services: ServicesDep) -> JobOut:
    """Refresh the whole research base, or (with a query) add one more search to it."""
    if services.jobs.active_for(kinds=IDEA_JOBS):
        raise HTTPException(409, "Idea Lab is already researching or brainstorming. Wait for it to finish.")
    job = await services.jobs.start(
        RESEARCH_JOB,
        lambda ctx: run_research(
            engine=services.engine,
            llm=services.llm,
            settings=services.settings,
            collector=services.signals,
            ctx=ctx,
            query=body.query,
            depth=body.depth,
        ),
    )
    return JobOut(**job.model_dump())


@router.delete("/idea-lab/trends/{trend_id}", status_code=204)
def delete_trend(trend_id: int, session: SessionDep) -> None:
    trend = session.get(IdeaTrend, trend_id)
    if trend is not None:
        session.delete(trend)
        session.commit()


# -- sources ----------------------------------------------------------------------------


def sources_out(session: Session, config: SourceConfig) -> IdeaSourcesOut:
    health = load_health(session)
    return IdeaSourcesOut(
        sources=[
            IdeaSourceOut(
                **source.model_dump(include={"id", "name", "group", "url", "enabled", "builtin"}),
                group_label=GROUP_LABELS.get(source.group, source.group),
                **{k: v for k, v in health.get(source.id, {}).items() if k in ("ok", "count", "error", "checked_at")},
            )
            for source in config.sources
        ],
        search_only=config.search_only,
        voices=config.voices,
        industries=config.industries,
    )


@router.get("/idea-lab/sources", response_model=IdeaSourcesOut)
def get_sources(session: SessionDep) -> IdeaSourcesOut:
    return sources_out(session, load_config(session))


@router.put("/idea-lab/sources", response_model=IdeaSourcesOut)
def put_sources(body: IdeaSourcesIn, session: SessionDep) -> IdeaSourcesOut:
    if body.reset:
        return sources_out(session, save_changes(session, SourceChanges()))
    changes = load_changes(session)
    if body.disabled is not None:
        # A source that ships switched off is turned on by leaving it out of ``disabled``.
        changes.disabled = list(dict.fromkeys(body.disabled))
        changes.enabled = [s.id for s in build_config(SourceChanges()).sources if not s.enabled and s.id not in changes.disabled]
    if body.custom is not None:
        try:
            changes.custom = [CustomSource(name=c.name, url=c.url) for c in body.custom]
        except ValueError as exc:
            raise HTTPException(422, "A feed address starts with http:// or https://") from exc
    if body.voices is not None:
        changes.voices = body.voices
    if body.industries is not None:
        changes.industries = body.industries
    return sources_out(session, save_changes(session, changes))


# -- brainstorms ------------------------------------------------------------------------


@router.get("/idea-lab/sessions", response_model=list[IdeaSessionSummary])
def list_sessions(session: SessionDep) -> list[IdeaSessionSummary]:
    names = {p.id: p.name for p in session.exec(select(Persona))}
    rows = session.exec(select(IdeaSession).where(IdeaSession.status != "archived").order_by(col(IdeaSession.id).desc()).limit(30)).all()
    return [IdeaSessionSummary(**_summary(session, row, names)) for row in rows]


@router.post("/idea-lab/sessions", response_model=IdeaSessionCreated, status_code=201)
async def create_session(body: IdeaSessionIn, session: SessionDep, services: ServicesDep) -> IdeaSessionCreated:
    if body.persona_id is not None:
        persona = persona_or_404(session, body.persona_id)
    else:
        active = session.exec(select(Persona).where(Persona.is_active == True)).first()  # noqa: E712
        if active is None:
            raise HTTPException(422, "Create a persona and turn it on first.")
        persona = active
    assert persona.id is not None
    if services.jobs.active_for(kinds=IDEA_JOBS):
        raise HTTPException(409, "Idea Lab is already researching or brainstorming. Wait for it to finish.")
    row = IdeaSession(persona_id=persona.id, mode=body.mode, focus=body.focus.strip(), sparks=body.sparks.strip())
    session.add(row)
    session.commit()
    session.refresh(row)
    assert row.id is not None
    session_id = row.id
    extras = [*body.extras, *(["sparks"] if row.sparks else [])]
    job = await services.jobs.start(
        BRAINSTORM_JOB,
        lambda ctx: run_brainstorm(
            engine=services.engine,
            llm=services.llm,
            settings=services.settings,
            collector=services.signals,
            session_id=session_id,
            extras=extras,
            refresh=body.refresh_research,
            depth=body.depth,
            ctx=ctx,
        ),
        persona_id=persona.id,
    )
    session.expire_all()
    row = _session_or_404(session, session_id)
    row.job_id = job.id
    session.add(row)
    session.commit()
    session.refresh(row)
    return IdeaSessionCreated(session=session_out(session, row), job_id=job.id)


@router.get("/idea-lab/sessions/{session_id}", response_model=IdeaSessionOut)
def get_session(session_id: int, session: SessionDep) -> IdeaSessionOut:
    return session_out(session, _session_or_404(session, session_id))


@router.delete("/idea-lab/sessions/{session_id}", status_code=204)
def delete_session(session_id: int, session: SessionDep, services: ServicesDep) -> None:
    row = _session_or_404(session, session_id)
    if row.status == "running" and services.jobs.active_for(kinds=(BRAINSTORM_JOB,)):
        raise HTTPException(409, "This brainstorm is still running.")
    # The brainstorm leaves the list, but its ideas stay on file: saved ones in the bank, and every other one hidden
    # with its session so a later brainstorm does not propose it again.
    if session.exec(select(Idea).where(Idea.session_id == session_id)).first() is None:
        session.delete(row)
    else:
        row.status = "archived"
        session.add(row)
    session.commit()


# -- ideas ------------------------------------------------------------------------------


@router.get("/ideas", response_model=list[IdeaOut])
def list_ideas(
    session: SessionDep,
    persona_id: int | None = None,
    state: list[IdeaState] = Query(default=list(BANK_STATES)),
) -> list[IdeaOut]:
    """The idea bank: ideas across every brainstorm (saved and written by default), newest first."""
    query = select(Idea).where(col(Idea.state).in_(state))
    if persona_id is not None:
        query = query.where(Idea.persona_id == persona_id)
    return ideas_out(session, session.exec(query.order_by(col(Idea.id).desc()).limit(1000)).all())


def _bank_session(session: Session, persona_id: int) -> IdeaSession:
    """The hidden holder for ideas the author adds by hand (``Idea.session_id`` is required)."""
    row = session.exec(select(IdeaSession).where(IdeaSession.persona_id == persona_id, IdeaSession.mode == "manual")).first()
    if row is None:
        row = IdeaSession(persona_id=persona_id, mode="manual", status="archived")
        session.add(row)
        session.flush()
    return row


@router.post("/ideas", response_model=IdeaOut, status_code=201)
def create_idea(body: IdeaCreate, session: SessionDep) -> IdeaOut:
    """Add an idea of the author's own straight to the bank, as a serious idea."""
    if body.persona_id is not None:
        persona = persona_or_404(session, body.persona_id)
    else:
        active = session.exec(select(Persona).where(Persona.is_active == True)).first()  # noqa: E712
        if active is None:
            raise HTTPException(422, "Create a persona and turn it on first.")
        persona = active
    assert persona.id is not None
    holder = _bank_session(session, persona.id)
    assert holder.id is not None
    idea = Idea(
        session_id=holder.id,
        persona_id=persona.id,
        approach="own",
        title=" ".join(body.title.split()),
        brief=body.brief.strip(),
        angle=body.angle.strip(),
        outline=[" ".join(point.split()) for point in body.outline if point.strip()],
        note=body.note.strip(),
        state="saved",
    )
    session.add(idea)
    session.commit()
    session.refresh(idea)
    return idea_out(idea)


@router.get("/ideas/{idea_id}", response_model=IdeaOut)
def get_idea(idea_id: int, session: SessionDep) -> IdeaOut:
    return _one_out(session, _idea_or_404(session, idea_id))


@router.patch("/ideas/{idea_id}", response_model=IdeaOut)
def update_idea(idea_id: int, body: IdeaUpdate, session: SessionDep) -> IdeaOut:
    idea = _idea_or_404(session, idea_id)
    if body.state is not None:
        if idea.state == "used":
            raise HTTPException(409, "This idea is already a post.")
        idea.state = body.state
    if body.title is not None:
        idea.title = " ".join(body.title.split())
    if body.brief is not None:
        idea.brief = body.brief.strip()
    if body.angle is not None:
        idea.angle = body.angle.strip()
    if body.outline is not None:
        idea.outline = [" ".join(point.split()) for point in body.outline if point.strip()]
    if body.note is not None:
        idea.note = body.note.strip()
    session.add(idea)
    session.commit()
    session.refresh(idea)
    return _one_out(session, idea)


@router.post("/ideas/{idea_id}/write", response_model=ProjectCreated, status_code=201)
async def write_idea(idea_id: int, body: IdeaWriteIn, session: SessionDep, services: ServicesDep) -> ProjectCreated:
    """Start a post (or an A/B test) from the idea, in the chosen persona's voice and with its defaults."""
    idea = _idea_or_404(session, idea_id)
    if idea.state == "used" and idea.project_id is not None:
        raise HTTPException(409, "This idea is already a post.")
    known = {kind.id for kind in ARTICLE_TYPES}
    dials = Dials(article_type=idea.article_type) if idea.article_type in known else Dials()
    return await create_project(
        ProjectCreate(prompt=idea_brief(idea), persona_id=body.persona_id or idea.persona_id, dials=dials, mode=body.mode, idea_id=idea.id),
        session,
        services,
    )
