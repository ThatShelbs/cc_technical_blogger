"""Projects (one per post), their images, and exports."""

from __future__ import annotations

import asyncio
import shutil
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from sqlmodel import Session, col, delete, select

from proseferno.api.deps import ServicesDep, SessionDep, image_or_404, persona_or_404, project_or_404
from proseferno.api.schemas import (
    CopyHtmlOut,
    GenerateIn,
    ImageEditIn,
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
    RevisionOut,
    RewriteIn,
    TweakIn,
)
from proseferno.authenticity import analyze, author_profile
from proseferno.db import Persona, Project, ProjectImage, Sample, utcnow
from proseferno.export import PLATFORMS, Platform, build_bundle, copy_html, linkedin_post
from proseferno.images import ImageProviderError, to_png
from proseferno.llm import LLMError
from proseferno.services import Services
from proseferno.voice import current_voice_profile
from proseferno.voice.lessons import extract_lessons, record_lessons
from proseferno.writer import (
    TEXT_JOBS,
    Dials,
    WriterError,
    finish_text,
    generate_article,
    merge_titles,
    push_revision,
    regenerate_titles,
    resolve,
    rewrite_passage,
    set_title,
    split_title,
    tweak_post,
    word_count,
)
from proseferno.writer.pipeline import measure
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
    # Only text jobs: an image redraw is followed by its own card, not the whole page.
    active = services.jobs.active_for(project_id=project.id, kinds=TEXT_JOBS)
    revisions = [
        RevisionOut(
            index=i,
            label=str(entry.get("label", "")),
            kind=str(entry.get("kind", "edit")),
            created_at=str(entry.get("created_at", "")),
            word_count=word_count(str(entry.get("markdown", ""))),
        )
        for i, entry in enumerate(project.revisions or [])
    ]
    return ProjectOut(
        **project.model_dump(exclude={"revisions"}),
        revisions=revisions,
        resolved_dials=resolved,
        images=[image_out(i) for i in project_images(session, project.id)],
        active_job_id=active[0].id if active else None,
        active_job_kind=active[0].kind if active else None,
    )


def _check_idle(services: Services, project_id: int) -> None:
    if services.jobs.active_for(project_id=project_id, kinds=TEXT_JOBS):
        raise HTTPException(409, "Claude is still working on this post. Wait for it to finish.")


def _writable_persona(session: Session, persona_id: int) -> Persona:
    persona = persona_or_404(session, persona_id)
    if current_voice_profile(session, persona_id) is None:
        raise HTTPException(422, f"Persona '{persona.name}' has no voice profile yet. Generate it first.")
    return persona


async def start_generation(services: Services, project_id: int) -> str:
    active = services.jobs.active_for(project_id=project_id, kinds=TEXT_JOBS)
    if active and active[0].kind == "generate_post":
        return active[0].id
    if active:
        raise HTTPException(409, "Claude is still applying your feedback. Wait for it to finish.")
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
    if body.generate and current_voice_profile(session, persona.id) is None:
        raise HTTPException(422, f"Persona '{persona.name}' has no voice profile yet. Generate it first.")
    project = Project(
        persona_id=persona.id,
        prompt=body.prompt.strip(),
        dials=body.dials.model_dump(exclude_none=True),
        title=body.prompt.strip().splitlines()[0][:80],
        brand_kit=body.brand_kit.model_dump() if body.brand_kit else {},
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
    if body.markdown is not None and body.markdown != project.markdown:
        push_revision(project, "Before your edit", "edit")
        persona = session.get(Persona, project.persona_id)
        if persona is not None and body.learn:
            record_lessons(persona, extract_lessons(project.markdown, body.markdown))
            session.add(persona)
        project.markdown = body.markdown
    if body.title is not None and body.title.strip():
        project.title = body.title.strip()
        project.markdown = set_title(project.markdown, project.title) if project.markdown else project.markdown
    if body.pinned_titles is not None:
        project.pinned_titles = merge_titles(body.pinned_titles)
    if body.brand_kit is not None:
        project.brand_kit = body.brand_kit.model_dump()
    if body.prompt is not None:
        project.prompt = body.prompt.strip()
    if body.dials is not None:
        project.dials = body.dials.model_dump(exclude_none=True)
    if body.persona_id is not None and body.persona_id != project.persona_id:
        _writable_persona(session, body.persona_id)
        project.persona_id = body.persona_id
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
async def generate(project_id: int, session: SessionDep, services: ServicesDep, body: GenerateIn | None = None) -> JobOut:
    """Write the whole post again; with a body, first apply a new brief, dials or persona."""
    project = project_or_404(session, project_id)
    body = body or GenerateIn()
    persona_id = body.persona_id if body.persona_id is not None else project.persona_id
    _writable_persona(session, persona_id)
    if body.persona_id is not None or body.prompt is not None or body.dials is not None:
        _check_idle(services, project_id)
        project.persona_id = persona_id
        if body.prompt is not None:
            project.prompt = body.prompt.strip()
        if body.dials is not None:
            project.dials = body.dials.model_dump(exclude_none=True)
        project.updated_at = utcnow()
        session.add(project)
        session.commit()
    job_id = await start_generation(services, project_id)
    return JobOut(**services.jobs.get(job_id).model_dump())


@router.post("/projects/{project_id}/tweak", response_model=JobOut, status_code=202)
async def tweak(project_id: int, body: TweakIn, session: SessionDep, services: ServicesDep) -> JobOut:
    """Apply the author's feedback with surgical edits, keeping the rest of the text and the images."""
    project = project_or_404(session, project_id)
    if not project.markdown:
        raise HTTPException(409, "Generate the post before tweaking it.")
    _writable_persona(session, project.persona_id)
    _check_idle(services, project_id)
    job = await services.jobs.start(
        "tweak_post",
        lambda ctx: tweak_post(
            engine=services.engine,
            llm=services.llm,
            settings=services.settings,
            images=services.images,
            project_id=project_id,
            feedback=body.feedback,
            ctx=ctx,
        ),
        project_id=project_id,
    )
    return JobOut(**job.model_dump())


@router.post("/projects/{project_id}/revisions/{index}/restore", response_model=ProjectOut)
def restore_revision(project_id: int, index: int, session: SessionDep, services: ServicesDep) -> ProjectOut:
    """Bring back an earlier text version; the current text becomes a version too, so this can be undone."""
    project = project_or_404(session, project_id)
    revisions = list(project.revisions or [])
    if not 0 <= index < len(revisions):
        raise HTTPException(404, "No such version.")
    _check_idle(services, project_id)
    entry = revisions.pop(index)
    project.revisions = revisions
    push_revision(project, f"Before restoring: {entry.get('label', '')}", "restore")
    project.markdown = finish_text(str(entry.get("markdown", "")), project.plan)
    title, subtitle = split_title(project.markdown)
    project.title = title or str(entry.get("title", "")) or project.title
    project.subtitle = subtitle or str(entry.get("subtitle", "")) or project.subtitle
    voice_profile = current_voice_profile(session, project.persona_id)
    if voice_profile is not None:
        project.fidelity = measure(project.markdown, voice_profile.baseline_stylometrics)
    project.updated_at = utcnow()
    session.add(project)
    session.commit()
    session.refresh(project)
    return project_out(session, project, services)


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


@router.post("/projects/{project_id}/titles", response_model=ProjectOut)
async def new_title_options(project_id: int, session: SessionDep, services: ServicesDep) -> ProjectOut:
    """Have Claude replace the title options; the current and pinned titles are kept."""
    project_or_404(session, project_id)
    try:
        await regenerate_titles(llm=services.llm, settings=services.settings, engine=services.engine, project_id=project_id)
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
    voice_profile = current_voice_profile(session, project.persona_id)
    samples = list(session.exec(select(Sample).where(Sample.persona_id == project.persona_id)))
    project.authenticity = await analyze(
        llm=services.llm,
        settings=services.settings,
        markdown=project.markdown,
        voice_profile=voice_profile.markdown if voice_profile else "",
        profile=author_profile(samples, voice_profile.baseline_stylometrics if voice_profile else None),
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


async def _image_job(services: Services, session: Session, image_id: int, *, rethink: bool = False, instruction: str = "") -> JobOut:
    image = image_or_404(session, image_id)
    project = project_or_404(session, image.project_id)
    # Detached copies: the job outlives this request's database session.
    persona = Persona.model_validate(persona_or_404(session, project.persona_id).model_dump())
    brand_kit = dict(project.brand_kit or {})
    voice_profile = current_voice_profile(session, project.persona_id)
    markdown, title, voice = project.markdown, project.title, voice_profile.markdown if voice_profile else ""

    async def run(ctx):  # type: ignore[no-untyped-def]
        await ctx.progress(0.1, "Editing image" if instruction else "Redrawing image")
        result = await services.images.create(
            image_id,
            persona=persona,
            title=title,
            markdown=markdown,
            voice_profile=voice,
            redraw=True,
            rethink=rethink,
            brand_kit=brand_kit,
            instruction=instruction,
            usage=ctx.add_usage,
        )
        if result.status == "error":
            raise ImageProviderError(result.error or "Image generation failed.")
        return {"image_id": image_id}

    job = await services.jobs.start("edit_image" if instruction else "redraw_image", run, project_id=project.id)
    return JobOut(**job.model_dump())


@router.post("/images/{image_id}/redraw", response_model=JobOut, status_code=202)
async def redraw_image(image_id: int, body: RedrawIn, session: SessionDep, services: ServicesDep) -> JobOut:
    """Make a new version of one image (new random seed; or redesign it with ``rethink``)."""
    return await _image_job(services, session, image_id, rethink=body.rethink)


@router.post("/projects/{project_id}/images/redraw", response_model=JobOut, status_code=202)
async def redraw_all_images(project_id: int, session: SessionDep, services: ServicesDep) -> JobOut:
    """Redraw every image Claude drew (e.g. after changing the brand kit); uploads and screenshots stay."""
    project = project_or_404(session, project_id)
    persona = Persona.model_validate(persona_or_404(session, project.persona_id).model_dump())
    brand_kit = dict(project.brand_kit or {})
    voice_profile = current_voice_profile(session, project.persona_id)
    markdown, title, voice = project.markdown, project.title, voice_profile.markdown if voice_profile else ""
    image_ids = [
        i.id for i in project_images(session, project_id) if i.id is not None and i.kind != "screenshot" and i.provider != "upload"
    ]
    if not image_ids:
        raise HTTPException(409, "This post has no drawn images to redraw.")

    async def run(ctx):  # type: ignore[no-untyped-def]
        done = 0
        semaphore = asyncio.Semaphore(3)

        async def one(image_id: int) -> None:
            nonlocal done
            async with semaphore:
                await services.images.create(
                    image_id,
                    persona=persona,
                    title=title,
                    markdown=markdown,
                    voice_profile=voice,
                    redraw=True,
                    brand_kit=brand_kit,
                    usage=ctx.add_usage,
                )
            done += 1
            await ctx.emit("image_ready", {"image_id": image_id})
            await ctx.progress(done / len(image_ids), f"Redrew {done} of {len(image_ids)} images")

        await ctx.progress(0.05, f"Redrawing {len(image_ids)} images")
        await asyncio.gather(*(one(i) for i in image_ids))
        return {"image_ids": image_ids}

    job = await services.jobs.start("redraw_images", run, project_id=project_id)
    return JobOut(**job.model_dump())


@router.post("/images/{image_id}/edit", response_model=JobOut, status_code=202)
async def edit_image(image_id: int, body: ImageEditIn, session: SessionDep, services: ServicesDep) -> JobOut:
    """Change one image as the author describes ("make the arrows orange"), keeping the rest of it."""
    image = image_or_404(session, image_id)
    if image.kind == "screenshot" or image.provider in ("upload", "placeholder") or not image.spec:
        raise HTTPException(422, "Only images Claude drew can be edited by instruction. Redraw or upload this one instead.")
    return await _image_job(services, session, image_id, instruction=body.instruction)


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
