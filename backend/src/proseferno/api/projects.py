"""Projects (one per post), their images, and exports."""

from __future__ import annotations

import shutil
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from sqlmodel import Session, col, delete, select

from proseferno.api.deps import ServicesDep, SessionDep, image_or_404, persona_or_404, project_or_404
from proseferno.api.schemas import (
    CopyHtmlOut,
    ImageHistoryOut,
    ImageOut,
    ImageUpdate,
    JobOut,
    LinkedInPostOut,
    ProjectCreate,
    ProjectCreated,
    ProjectOut,
    ProjectSummary,
    ProjectUpdate,
    RedrawIn,
    RevertIn,
    RewriteIn,
)
from proseferno.authenticity import analyze, author_profile
from proseferno.db import Persona, Project, ProjectImage, Sample, utcnow
from proseferno.export import PLATFORMS, Platform, build_bundle, copy_html, linkedin_post
from proseferno.images import ImageProviderError, to_png
from proseferno.llm import LLMError
from proseferno.services import Services
from proseferno.voice import current_voice_soul
from proseferno.writer import Dials, WriterError, generate_article, resolve, rewrite_passage, set_title
from proseferno.writer.social import write_linkedin_post

router = APIRouter(prefix="/api")

MAX_IMAGE_BYTES = 15 * 1024 * 1024


# -- helpers ---------------------------------------------------------------------------


def image_url(image: ProjectImage) -> str | None:
    if not image.file_name:
        return None
    return f"/api/images/{image.id}/file?v={image.file_name}"


def image_out(image: ProjectImage) -> ImageOut:
    history = [
        ImageHistoryOut(
            index=i,
            url=f"/api/images/{image.id}/history/{i}/file",
            provider=str(entry.get("provider", "")),
            caption=str(entry.get("caption", "")),
            created_at=str(entry.get("created_at", "")),
        )
        for i, entry in enumerate(image.history)
    ]
    return ImageOut(
        **image.model_dump(exclude={"history", "spec", "file_name", "project_id", "anchor"}), url=image_url(image), history=history
    )


def project_images(session: Session, project_id: int) -> list[ProjectImage]:
    return list(session.exec(select(ProjectImage).where(ProjectImage.project_id == project_id).order_by(col(ProjectImage.position))))


def project_out(session: Session, project: Project, services: Services) -> ProjectOut:
    assert project.id is not None
    persona = session.get(Persona, project.persona_id)
    resolved = (
        resolve(Dials(**(project.dials or {})), persona, project.prompt, default_revisions=services.settings.revision_passes).model_dump()
        if persona
        else {}
    )
    active = services.jobs.active_for(project_id=project.id)
    return ProjectOut(
        **project.model_dump(),
        resolved_dials=resolved,
        images=[image_out(i) for i in project_images(session, project.id)],
        active_job_id=active[0].id if active else None,
    )


async def start_generation(services: Services, project_id: int) -> str:
    active = services.jobs.active_for(project_id=project_id)
    if active:
        return active[0].id
    job = await services.jobs.start(
        "generate_post",
        lambda ctx: generate_article(
            engine=services.engine,
            llm=services.llm,
            settings=services.settings,
            images=services.images,
            project_id=project_id,
            ctx=ctx,
        ),
        project_id=project_id,
    )
    return job.id


# -- projects ---------------------------------------------------------------------------


@router.get("/projects", response_model=list[ProjectSummary])
def list_projects(session: SessionDep) -> list[ProjectSummary]:
    projects = session.exec(select(Project).order_by(col(Project.updated_at).desc())).all()
    names = {p.id: p.name for p in session.exec(select(Persona))}
    out = []
    for project in projects:
        assert project.id is not None
        hero = session.exec(select(ProjectImage).where(ProjectImage.project_id == project.id, ProjectImage.slot_id == "hero")).first()
        out.append(
            ProjectSummary(
                **project.model_dump(include={"id", "persona_id", "title", "prompt", "status", "created_at", "updated_at"}),
                persona_name=names.get(project.persona_id, ""),
                thumbnail_url=image_url(hero) if hero else None,
            )
        )
    return out


@router.post("/projects", response_model=ProjectCreated, status_code=201)
async def create_project(body: ProjectCreate, session: SessionDep, services: ServicesDep) -> ProjectCreated:
    if body.persona_id is not None:
        persona = persona_or_404(session, body.persona_id)
    else:
        active = session.exec(select(Persona).where(Persona.is_active == True)).first()  # noqa: E712
        if active is None:
            raise HTTPException(422, "Create a persona and turn it on first.")
        persona = active
    assert persona.id is not None
    if body.generate and current_voice_soul(session, persona.id) is None:
        raise HTTPException(422, f"Persona '{persona.name}' has no voice soul yet. Generate it first.")
    project = Project(
        persona_id=persona.id,
        prompt=body.prompt.strip(),
        dials=body.dials.model_dump(exclude_none=True),
        title=body.prompt.strip().splitlines()[0][:80],
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    assert project.id is not None
    job_id = await start_generation(services, project.id) if body.generate else None
    session.refresh(project)
    return ProjectCreated(project=project_out(session, project, services), job_id=job_id)


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, session: SessionDep, services: ServicesDep) -> ProjectOut:
    return project_out(session, project_or_404(session, project_id), services)


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def update_project(project_id: int, body: ProjectUpdate, session: SessionDep, services: ServicesDep) -> ProjectOut:
    project = project_or_404(session, project_id)
    if body.markdown is not None:
        project.markdown = body.markdown
    if body.title is not None and body.title.strip():
        project.title = body.title.strip()
        project.markdown = set_title(project.markdown, project.title) if project.markdown else project.markdown
    if body.prompt is not None:
        project.prompt = body.prompt
    if body.dials is not None:
        project.dials = body.dials.model_dump(exclude_none=True)
    project.updated_at = utcnow()
    session.add(project)
    session.commit()
    session.refresh(project)
    return project_out(session, project, services)


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: int, session: SessionDep, services: ServicesDep) -> None:
    project = project_or_404(session, project_id)
    session.exec(delete(ProjectImage).where(col(ProjectImage.project_id) == project_id))  # type: ignore[call-overload]
    session.delete(project)
    session.commit()
    shutil.rmtree(services.storage.project_dir(project_id), ignore_errors=True)


@router.post("/projects/{project_id}/generate", response_model=JobOut, status_code=202)
async def generate(project_id: int, session: SessionDep, services: ServicesDep) -> JobOut:
    project = project_or_404(session, project_id)
    if current_voice_soul(session, project.persona_id) is None:
        raise HTTPException(422, "This persona has no voice soul yet. Generate it first.")
    job_id = await start_generation(services, project_id)
    return JobOut(**services.jobs.get(job_id).model_dump())


@router.post("/projects/{project_id}/rewrite", response_model=ProjectOut)
async def rewrite(project_id: int, body: RewriteIn, session: SessionDep, services: ServicesDep) -> ProjectOut:
    project_or_404(session, project_id)
    try:
        await rewrite_passage(
            llm=services.llm,
            settings=services.settings,
            engine=services.engine,
            project_id=project_id,
            selection=body.selection,
            instruction=body.instruction,
        )
    except (WriterError, LLMError) as exc:
        raise HTTPException(422, str(exc)) from exc
    session.expire_all()
    return project_out(session, project_or_404(session, project_id), services)


@router.post("/projects/{project_id}/authenticity", response_model=ProjectOut)
async def check_authenticity(project_id: int, session: SessionDep, services: ServicesDep) -> ProjectOut:
    """Re-run the AI-generation detection report on the current text (e.g. after editing)."""
    project = project_or_404(session, project_id)
    if not project.markdown:
        raise HTTPException(409, "Generate the post first.")
    soul = current_voice_soul(session, project.persona_id)
    samples = list(session.exec(select(Sample).where(Sample.persona_id == project.persona_id)))
    project.authenticity = await analyze(
        llm=services.llm,
        settings=services.settings,
        markdown=project.markdown,
        voice_soul=soul.markdown if soul else "",
        profile=author_profile(samples, soul.baseline_stylometrics if soul else None),
        use_judge=services.settings.ai_detection,
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return project_out(session, project, services)


# -- images ------------------------------------------------------------------------------


def _image_file(services: Services, image: ProjectImage, file_name: str | None) -> FileResponse:
    if not file_name:
        raise HTTPException(404, "Image has no file yet.")
    path = services.storage.image_dir(image.project_id) / file_name
    if not path.is_file():
        raise HTTPException(404, "Image file is missing.")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "public, max-age=31536000, immutable"})


@router.get("/images/{image_id}/file")
def image_file(image_id: int, session: SessionDep, services: ServicesDep) -> FileResponse:
    image = image_or_404(session, image_id)
    return _image_file(services, image, image.file_name)


@router.get("/images/{image_id}/history/{index}/file")
def image_history_file(image_id: int, index: int, session: SessionDep, services: ServicesDep) -> FileResponse:
    image = image_or_404(session, image_id)
    if not 0 <= index < len(image.history):
        raise HTTPException(404, "No such version.")
    return _image_file(services, image, image.history[index].get("file_name"))


@router.patch("/images/{image_id}", response_model=ImageOut)
def update_image(image_id: int, body: ImageUpdate, session: SessionDep) -> ImageOut:
    image = image_or_404(session, image_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(image, key, value)
    session.add(image)
    session.commit()
    session.refresh(image)
    return image_out(image)


@router.post("/images/{image_id}/redraw", response_model=JobOut, status_code=202)
async def redraw_image(image_id: int, body: RedrawIn, session: SessionDep, services: ServicesDep) -> JobOut:
    """Make a new version of one image (new random seed; or redesign it with ``rethink``)."""
    image = image_or_404(session, image_id)
    project = project_or_404(session, image.project_id)
    # Detached copy: the job outlives this request's database session.
    persona = Persona.model_validate(persona_or_404(session, project.persona_id).model_dump())
    soul = current_voice_soul(session, project.persona_id)
    markdown, title, voice = project.markdown, project.title, soul.markdown if soul else ""

    async def run(ctx):  # type: ignore[no-untyped-def]
        await ctx.progress(0.1, "Redrawing image")
        result = await services.images.create(
            image_id,
            persona=persona,
            title=title,
            markdown=markdown,
            voice_soul=voice,
            redraw=True,
            rethink=body.rethink,
            usage=ctx.add_usage,
        )
        if result.status == "error":
            raise ImageProviderError(result.error or "Image generation failed.")
        return {"image_id": image_id}

    job = await services.jobs.start("redraw_image", run, project_id=project.id)
    return JobOut(**job.model_dump())


@router.post("/images/{image_id}/upload", response_model=ImageOut)
async def upload_image(
    image_id: int,
    session: SessionDep,
    services: ServicesDep,
    file: Annotated[UploadFile, File()],
) -> ImageOut:
    """Replace an image with the user's own (e.g. a real platform screenshot)."""
    image = image_or_404(session, image_id)
    project = project_or_404(session, image.project_id)
    persona = persona_or_404(session, project.persona_id)
    data = await file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Images must be 15 MB or smaller.")
    try:
        png, width, height = to_png(data)
    except Exception as exc:
        raise HTTPException(422, "That file is not an image Proseferno can read.") from exc
    return image_out(services.images.save_upload(image_id, png, width, height, persona))


@router.post("/images/{image_id}/revert", response_model=ImageOut)
def revert_image(image_id: int, body: RevertIn, session: SessionDep, services: ServicesDep) -> ImageOut:
    image_or_404(session, image_id)
    try:
        return image_out(services.images.revert(image_id, body.index))
    except IndexError as exc:
        raise HTTPException(404, "No such version.") from exc


# -- export -------------------------------------------------------------------------------


def _check_platform(platform: str) -> Platform:
    if platform not in PLATFORMS:
        raise HTTPException(404, f"Unknown platform. Use one of: {', '.join(PLATFORMS)}.")
    return platform  # type: ignore[return-value]


@router.get("/projects/{project_id}/export/{platform}")
def export_bundle(project_id: int, platform: str, session: SessionDep, services: ServicesDep) -> Response:
    project = project_or_404(session, project_id)
    if not project.markdown:
        raise HTTPException(409, "Generate the post before exporting it.")
    persona = session.get(Persona, project.persona_id)
    name, data = build_bundle(
        project,
        project_images(session, project_id),
        services.storage.image_dir(project_id),
        _check_platform(platform),
        author=(persona.display_name or persona.name) if persona else "",
    )
    return Response(data, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/projects/{project_id}/copy/{platform}", response_model=CopyHtmlOut)
def export_copy_html(project_id: int, platform: str, session: SessionDep, services: ServicesDep) -> CopyHtmlOut:
    project = project_or_404(session, project_id)
    html = copy_html(project, project_images(session, project_id), services.storage.image_dir(project_id), _check_platform(platform))
    return CopyHtmlOut(html=html)


@router.get("/projects/{project_id}/linkedin-post", response_model=LinkedInPostOut)
def get_linkedin_post(project_id: int, session: SessionDep) -> LinkedInPostOut:
    """The saved Claude-written feed post, or a template built from the article."""
    project = project_or_404(session, project_id)
    if not project.markdown:
        raise HTTPException(409, "Generate the post first.")
    text, by_claude = linkedin_post(project)
    return LinkedInPostOut(text=text, characters=len(text), written_by="claude" if by_claude else "template")


@router.post("/projects/{project_id}/linkedin-post", response_model=LinkedInPostOut)
async def create_linkedin_post(project_id: int, session: SessionDep, services: ServicesDep) -> LinkedInPostOut:
    """Have Claude write the LinkedIn feed post in the persona's voice (replaces any saved one)."""
    project_or_404(session, project_id)
    try:
        text = await write_linkedin_post(llm=services.llm, settings=services.settings, engine=services.engine, project_id=project_id)
    except (WriterError, LLMError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return LinkedInPostOut(text=text, characters=len(text), written_by="claude")
