"""Personas, writing samples, and voice profiles."""

from __future__ import annotations

import shutil
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from sqlmodel import Session, col, delete, func, select

from proseferno.api.deps import ServicesDep, SessionDep, persona_or_404, sample_or_404
from proseferno.api.schemas import (
    JobOut,
    PersonaCreate,
    PersonaDuplicateIn,
    PersonaOut,
    PersonaUpdate,
    SampleDetail,
    SampleKind,
    SampleOut,
    SampleUpdate,
    SeedSamplesOut,
    UploadResult,
    UrlImportIn,
    VoiceProfileEdit,
    VoiceProfileGenerateIn,
    VoiceProfileLabelIn,
    VoiceProfileOut,
    VoiceProfileVersion,
)
from proseferno.db import Persona, Project, ProjectImage, Sample, VoiceProfile, utcnow
from proseferno.ingest import SUPPORTED_EXTENSIONS, ParsedDocument, UnsupportedFormatError, fetch_url, parse_file
from proseferno.ingest.stylometrics import compute
from proseferno.services import Services
from proseferno.storage import safe_filename
from proseferno.voice import current_voice_profile, generate_voice_profile, latest_voice_profile, unpin, voice_profile_version

router = APIRouter(prefix="/api")

MAX_UPLOAD_BYTES = 25 * 1024 * 1024


# -- helpers ------------------------------------------------------------------------


def persona_out(session: Session, persona: Persona, services: Services) -> PersonaOut:
    assert persona.id is not None
    counts = dict(
        session.exec(
            select(Sample.kind, func.count()).where(Sample.persona_id == persona.id).group_by(Sample.kind)  # type: ignore[arg-type]
        ).all()
    )
    voice_profiles = session.exec(
        select(VoiceProfile).where(VoiceProfile.persona_id == persona.id).order_by(col(VoiceProfile.version).desc())
    ).all()
    current = current_voice_profile(session, persona.id)
    active = services.jobs.active_for(persona_id=persona.id)
    return PersonaOut(
        **persona.model_dump(exclude={"updated_at"}),
        own_samples=counts.get("own", 0),
        influence_samples=counts.get("influence", 0),
        voice_profile_version=current.version if current else None,
        voice_profile_label=current.label if current else "",
        latest_voice_profile_version=voice_profiles[0].version if voice_profiles else None,
        voice_profile_versions=[version_out(s) for s in voice_profiles],
        active_job_id=active[0].id if active else None,
    )


def version_out(voice_profile: VoiceProfile) -> VoiceProfileVersion:
    return VoiceProfileVersion(**voice_profile.model_dump(include={"id", "version", "label", "edited_by_user", "created_at"}))


def sample_out(sample: Sample) -> SampleOut:
    return SampleOut(
        **sample.model_dump(exclude={"markdown", "captions", "stylometrics", "analysis"}), analyzed=sample.analysis is not None
    )


def voice_profile_out(session: Session, voice_profile: VoiceProfile) -> VoiceProfileOut:
    current = current_voice_profile(session, voice_profile.persona_id)
    return VoiceProfileOut(
        **voice_profile.model_dump(exclude={"sample_ids"}),
        sample_count=len(voice_profile.sample_ids),
        in_use=current is not None and current.id == voice_profile.id,
    )


def add_sample(session: Session, persona_id: int, kind: str, source_name: str, doc: ParsedDocument) -> Sample:
    if doc.word_count < 50:
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


def set_active(session: Session, persona_id: int) -> None:
    for persona in session.exec(select(Persona)):
        persona.is_active = persona.id == persona_id
        session.add(persona)
    session.commit()


# -- personas -------------------------------------------------------------------------


@router.get("/personas", response_model=list[PersonaOut])
def list_personas(session: SessionDep, services: ServicesDep) -> list[PersonaOut]:
    personas = session.exec(select(Persona).order_by(col(Persona.created_at))).all()
    return [persona_out(session, p, services) for p in personas]


@router.post("/personas", response_model=PersonaOut, status_code=201)
def create_persona(body: PersonaCreate, session: SessionDep, services: ServicesDep) -> PersonaOut:
    first = session.exec(select(func.count()).select_from(Persona)).one() == 0
    persona = Persona(**body.model_dump(), is_active=first)
    if not persona.display_name:
        persona.display_name = persona.name
    session.add(persona)
    session.commit()
    session.refresh(persona)
    return persona_out(session, persona, services)


@router.get("/personas/{persona_id}", response_model=PersonaOut)
def get_persona(persona_id: int, session: SessionDep, services: ServicesDep) -> PersonaOut:
    return persona_out(session, persona_or_404(session, persona_id), services)


@router.patch("/personas/{persona_id}", response_model=PersonaOut)
def update_persona(persona_id: int, body: PersonaUpdate, session: SessionDep, services: ServicesDep) -> PersonaOut:
    persona = persona_or_404(session, persona_id)
    changes = body.model_dump(exclude_unset=True)
    pinned = changes.get("pinned_voice_profile_version")
    if pinned is not None and voice_profile_version(session, persona_id, pinned) is None:
        raise HTTPException(404, f"Voice profile v{pinned} does not exist.")
    if "default_image_count" in changes and not changes["default_image_count"]:
        changes["default_image_count"] = None  # 0 = automatic
    for key, value in changes.items():
        if value is None and key not in ("pinned_voice_profile_version", "default_image_count"):
            continue
        setattr(persona, key, value.strip() if isinstance(value, str) else value)
    persona.updated_at = utcnow()
    session.add(persona)
    session.commit()
    session.refresh(persona)
    return persona_out(session, persona, services)


@router.delete("/personas/{persona_id}/lessons", response_model=PersonaOut)
def forget_lessons(persona_id: int, session: SessionDep, services: ServicesDep, index: int | None = None) -> PersonaOut:
    """Forget one learned edit (by ``index``) or all of them."""
    persona = persona_or_404(session, persona_id)
    lessons = list(persona.edit_lessons or [])
    if index is not None and not 0 <= index < len(lessons):
        raise HTTPException(404, "No such lesson.")
    persona.edit_lessons = [] if index is None else [lesson for i, lesson in enumerate(lessons) if i != index]
    persona.updated_at = utcnow()
    session.add(persona)
    session.commit()
    session.refresh(persona)
    return persona_out(session, persona, services)


@router.post("/personas/{persona_id}/activate", response_model=list[PersonaOut])
def activate_persona(persona_id: int, session: SessionDep, services: ServicesDep) -> list[PersonaOut]:
    """Turn this persona on and every other persona off."""
    persona_or_404(session, persona_id)
    set_active(session, persona_id)
    return list_personas(session, services)


@router.post("/personas/{persona_id}/duplicate", response_model=PersonaOut, status_code=201)
def duplicate_persona(persona_id: int, body: PersonaDuplicateIn, session: SessionDep, services: ServicesDep) -> PersonaOut:
    """Start a new, separately named persona from this one (its settings, samples and, optionally, a voice profile version)."""
    source = persona_or_404(session, persona_id)
    voice_profile = None
    if body.voice_profile_version is not None:
        voice_profile = voice_profile_version(session, persona_id, body.voice_profile_version)
        if voice_profile is None:
            raise HTTPException(404, f"Voice profile v{body.voice_profile_version} does not exist.")
    name = body.name.strip()
    copy = Persona(
        **source.model_dump(
            exclude={"id", "name", "display_name", "is_active", "pinned_voice_profile_version", "created_at", "updated_at"}
        ),
        name=name,
        display_name=(body.display_name or "").strip() or source.display_name or name,
        is_active=False,
    )
    session.add(copy)
    session.commit()
    session.refresh(copy)
    assert copy.id is not None
    id_map: dict[int, int] = {}
    if body.copy_samples:
        for sample in session.exec(select(Sample).where(Sample.persona_id == persona_id).order_by(col(Sample.created_at))).all():
            clone = Sample(**sample.model_dump(exclude={"id", "persona_id", "created_at"}), persona_id=copy.id)
            session.add(clone)
            session.flush()
            if sample.id is not None and clone.id is not None:
                id_map[sample.id] = clone.id
    if voice_profile is not None:
        markdown = voice_profile.markdown.replace(f"# Voice Profile: {source.name}", f"# Voice Profile: {name}", 1)
        session.add(
            VoiceProfile(
                persona_id=copy.id,
                version=1,
                label=voice_profile.label or f"From {source.name} v{voice_profile.version}",
                markdown=markdown,
                best_practices=voice_profile.best_practices,
                sample_ids=[id_map[i] for i in voice_profile.sample_ids if i in id_map],
                baseline_stylometrics=voice_profile.baseline_stylometrics,
                model=voice_profile.model,
                edited_by_user=voice_profile.edited_by_user,
            )
        )
        services.storage.voice_profile_path(copy.id, 1).write_text(markdown, encoding="utf-8")
    session.commit()
    session.refresh(copy)
    return persona_out(session, copy, services)


@router.delete("/personas/{persona_id}", status_code=204)
def delete_persona(persona_id: int, session: SessionDep, services: ServicesDep) -> None:
    persona = persona_or_404(session, persona_id)
    project_ids = list(session.exec(select(Project.id).where(Project.persona_id == persona_id)))
    if project_ids:
        session.exec(delete(ProjectImage).where(col(ProjectImage.project_id).in_(project_ids)))  # type: ignore[call-overload]
        session.exec(delete(Project).where(col(Project.persona_id) == persona_id))  # type: ignore[call-overload]
    session.exec(delete(Sample).where(col(Sample.persona_id) == persona_id))  # type: ignore[call-overload]
    session.exec(delete(VoiceProfile).where(col(VoiceProfile.persona_id) == persona_id))  # type: ignore[call-overload]
    was_active = persona.is_active
    session.delete(persona)
    session.commit()
    shutil.rmtree(services.storage.persona_dir(persona_id), ignore_errors=True)
    for pid in project_ids:
        if pid is not None:
            shutil.rmtree(services.storage.project_dir(pid), ignore_errors=True)
    if was_active:
        remaining = session.exec(select(Persona).order_by(col(Persona.created_at))).first()
        if remaining is not None and remaining.id is not None:
            set_active(session, remaining.id)


# -- samples ---------------------------------------------------------------------------


@router.get("/personas/{persona_id}/samples", response_model=list[SampleOut])
def list_samples(persona_id: int, session: SessionDep) -> list[SampleOut]:
    persona_or_404(session, persona_id)
    samples = session.exec(select(Sample).where(Sample.persona_id == persona_id).order_by(col(Sample.created_at))).all()
    return [sample_out(s) for s in samples]


@router.post("/personas/{persona_id}/samples", response_model=UploadResult)
async def upload_samples(
    persona_id: int,
    session: SessionDep,
    services: ServicesDep,
    files: Annotated[list[UploadFile], File()],
    kind: Annotated[SampleKind, Form()] = "own",
) -> UploadResult:
    persona_or_404(session, persona_id)
    added: list[SampleOut] = []
    errors: list[str] = []
    for upload in files:
        name = safe_filename(upload.filename or "sample")
        data = await upload.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            errors.append(f"{name}: larger than 25 MB.")
            continue
        try:
            doc = parse_file(name, data)
            sample = add_sample(session, persona_id, kind, name, doc)
        except (UnsupportedFormatError, ValueError) as exc:
            errors.append(str(exc))
            continue
        except Exception as exc:  # noqa: BLE001 - a corrupt file should not fail the whole batch
            errors.append(f"{name}: could not read this file ({exc.__class__.__name__}).")
            continue
        (services.storage.sample_dir(persona_id) / f"{sample.id}-{name}").write_bytes(data)
        added.append(sample_out(sample))
    return UploadResult(added=added, errors=errors)


@router.post("/personas/{persona_id}/samples/url", response_model=SampleOut)
def import_url(persona_id: int, body: UrlImportIn, session: SessionDep) -> SampleOut:
    persona_or_404(session, persona_id)
    try:
        doc = fetch_url(body.url)
        sample = add_sample(session, persona_id, body.kind, body.url, doc)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return sample_out(sample)


@router.get("/seed-samples", response_model=SeedSamplesOut)
def seed_samples(services: ServicesDep) -> SeedSamplesOut:
    directory = services.settings.seed_samples_dir
    files = sorted(p.name for p in directory.iterdir() if p.suffix.lower() in SUPPORTED_EXTENSIONS) if directory.is_dir() else []
    return SeedSamplesOut(available=bool(files), directory=str(directory), files=files)


@router.post("/personas/{persona_id}/samples/import-seed", response_model=UploadResult)
def import_seed_samples(persona_id: int, session: SessionDep, services: ServicesDep) -> UploadResult:
    """Import the files in the seed folder (my_writing_examples/) as the persona's own writing."""
    persona_or_404(session, persona_id)
    directory = services.settings.seed_samples_dir
    if not directory.is_dir():
        raise HTTPException(404, f"Folder not found: {directory}")
    existing = set(session.exec(select(Sample.source_name).where(Sample.persona_id == persona_id)))
    added: list[SampleOut] = []
    errors: list[str] = []
    for path in sorted(directory.iterdir()):
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS or path.name in existing:
            continue
        try:
            sample = add_sample(session, persona_id, "own", path.name, parse_file(path.name, path.read_bytes()))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path.name}: {exc}")
            continue
        added.append(sample_out(sample))
    return UploadResult(added=added, errors=errors)


@router.get("/samples/{sample_id}", response_model=SampleDetail)
def get_sample(sample_id: int, session: SessionDep) -> SampleDetail:
    sample = sample_or_404(session, sample_id)
    return SampleDetail(**sample.model_dump(), analyzed=sample.analysis is not None)


@router.patch("/samples/{sample_id}", response_model=SampleOut)
def update_sample(sample_id: int, body: SampleUpdate, session: SessionDep) -> SampleOut:
    sample = sample_or_404(session, sample_id)
    if sample.kind != body.kind:
        sample.kind = body.kind
        sample.analysis = None  # the analysis prompt differs for own vs influence writing
        session.add(sample)
        session.commit()
        session.refresh(sample)
    return sample_out(sample)


@router.delete("/samples/{sample_id}", status_code=204)
def delete_sample(sample_id: int, session: SessionDep) -> None:
    session.delete(sample_or_404(session, sample_id))
    session.commit()


# -- voice profile -----------------------------------------------------------------------


@router.post("/personas/{persona_id}/voice-profile", response_model=JobOut, status_code=202)
async def start_voice_profile(
    persona_id: int, session: SessionDep, services: ServicesDep, body: VoiceProfileGenerateIn | None = None
) -> JobOut:
    persona_or_404(session, persona_id)
    if not session.exec(select(Sample).where(Sample.persona_id == persona_id, Sample.kind == "own")).first():
        raise HTTPException(422, "Add at least one sample of your own writing first.")
    active = services.jobs.active_for(persona_id=persona_id)
    if active:
        return JobOut(**active[0].model_dump())
    job = await services.jobs.start(
        "voice_profile",
        lambda ctx: generate_voice_profile(
            engine=services.engine,
            llm=services.llm,
            settings=services.settings,
            storage=services.storage,
            persona_id=persona_id,
            ctx=ctx,
            label=body.label if body else "",
        ),
        persona_id=persona_id,
    )
    return JobOut(**job.model_dump())


@router.get("/personas/{persona_id}/voice-profile", response_model=VoiceProfileOut)
def get_voice_profile(persona_id: int, session: SessionDep, version: int | None = None) -> VoiceProfileOut:
    """The version in use (pinned, else latest), or a specific ``version``."""
    persona_or_404(session, persona_id)
    voice_profile = current_voice_profile(session, persona_id) if version is None else voice_profile_version(session, persona_id, version)
    if voice_profile is None:
        raise HTTPException(404, "No voice profile yet.")
    return voice_profile_out(session, voice_profile)


@router.get("/personas/{persona_id}/voice-profile/versions", response_model=list[VoiceProfileVersion])
def voice_profile_versions(persona_id: int, session: SessionDep) -> list[VoiceProfileVersion]:
    persona_or_404(session, persona_id)
    voice_profiles = session.exec(
        select(VoiceProfile).where(VoiceProfile.persona_id == persona_id).order_by(col(VoiceProfile.version).desc())
    ).all()
    return [version_out(s) for s in voice_profiles]


@router.patch("/personas/{persona_id}/voice-profile/{version}", response_model=VoiceProfileOut)
def label_voice_profile(persona_id: int, version: int, body: VoiceProfileLabelIn, session: SessionDep) -> VoiceProfileOut:
    """Name a version, e.g. "Punchier, fewer jokes"."""
    persona_or_404(session, persona_id)
    voice_profile = voice_profile_version(session, persona_id, version)
    if voice_profile is None:
        raise HTTPException(404, f"Voice profile v{version} does not exist.")
    voice_profile.label = body.label.strip()
    session.add(voice_profile)
    session.commit()
    session.refresh(voice_profile)
    return voice_profile_out(session, voice_profile)


@router.put("/personas/{persona_id}/voice-profile", response_model=VoiceProfileOut)
def edit_voice_profile(persona_id: int, body: VoiceProfileEdit, session: SessionDep, services: ServicesDep) -> VoiceProfileOut:
    """Save the user's edits as a new version (history is kept)."""
    persona_or_404(session, persona_id)
    latest = latest_voice_profile(session, persona_id)
    if latest is None:
        raise HTTPException(404, "Generate a voice profile before editing it.")
    voice_profile = VoiceProfile(
        persona_id=persona_id,
        version=latest.version + 1,
        label=body.label.strip(),
        markdown=body.markdown.strip() + "\n",
        best_practices=latest.best_practices,
        sample_ids=latest.sample_ids,
        baseline_stylometrics=latest.baseline_stylometrics,
        model=latest.model,
        edited_by_user=True,
    )
    session.add(voice_profile)
    unpin(session, persona_id)
    session.commit()
    session.refresh(voice_profile)
    services.storage.voice_profile_path(persona_id, voice_profile.version).write_text(voice_profile.markdown, encoding="utf-8")
    return voice_profile_out(session, voice_profile)
