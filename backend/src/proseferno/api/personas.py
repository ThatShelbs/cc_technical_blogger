"""Personas, writing samples, and voice souls."""

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
    VoiceSoulEdit,
    VoiceSoulGenerateIn,
    VoiceSoulLabelIn,
    VoiceSoulOut,
    VoiceSoulVersion,
)
from proseferno.db import Persona, Project, ProjectImage, Sample, VoiceSoul, utcnow
from proseferno.ingest import SUPPORTED_EXTENSIONS, ParsedDocument, UnsupportedFormatError, fetch_url, parse_file
from proseferno.ingest.stylometrics import compute
from proseferno.services import Services
from proseferno.storage import safe_filename
from proseferno.voice import current_voice_soul, generate_voice_soul, latest_voice_soul, unpin, voice_soul_version

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
    souls = session.exec(select(VoiceSoul).where(VoiceSoul.persona_id == persona.id).order_by(col(VoiceSoul.version).desc())).all()
    current = current_voice_soul(session, persona.id)
    active = services.jobs.active_for(persona_id=persona.id)
    return PersonaOut(
        **persona.model_dump(exclude={"updated_at"}),
        own_samples=counts.get("own", 0),
        influence_samples=counts.get("influence", 0),
        voice_soul_version=current.version if current else None,
        voice_soul_label=current.label if current else "",
        latest_voice_soul_version=souls[0].version if souls else None,
        voice_soul_versions=[version_out(s) for s in souls],
        active_job_id=active[0].id if active else None,
    )


def version_out(soul: VoiceSoul) -> VoiceSoulVersion:
    return VoiceSoulVersion(**soul.model_dump(include={"id", "version", "label", "edited_by_user", "created_at"}))


def sample_out(sample: Sample) -> SampleOut:
    return SampleOut(
        **sample.model_dump(exclude={"markdown", "captions", "stylometrics", "analysis"}), analyzed=sample.analysis is not None
    )


def soul_out(session: Session, soul: VoiceSoul) -> VoiceSoulOut:
    current = current_voice_soul(session, soul.persona_id)
    return VoiceSoulOut(
        **soul.model_dump(exclude={"sample_ids"}),
        sample_count=len(soul.sample_ids),
        in_use=current is not None and current.id == soul.id,
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
    pinned = changes.get("pinned_voice_soul_version")
    if pinned is not None and voice_soul_version(session, persona_id, pinned) is None:
        raise HTTPException(404, f"Voice soul v{pinned} does not exist.")
    if "default_image_count" in changes and not changes["default_image_count"]:
        changes["default_image_count"] = None  # 0 = automatic
    for key, value in changes.items():
        if value is None and key not in ("pinned_voice_soul_version", "default_image_count"):
            continue
        setattr(persona, key, value.strip() if isinstance(value, str) else value)
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
    """Start a new, separately named persona from this one (its settings, samples and, optionally, a voice soul version)."""
    source = persona_or_404(session, persona_id)
    soul = None
    if body.voice_soul_version is not None:
        soul = voice_soul_version(session, persona_id, body.voice_soul_version)
        if soul is None:
            raise HTTPException(404, f"Voice soul v{body.voice_soul_version} does not exist.")
    name = body.name.strip()
    copy = Persona(
        **source.model_dump(exclude={"id", "name", "display_name", "is_active", "pinned_voice_soul_version", "created_at", "updated_at"}),
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
    if soul is not None:
        markdown = soul.markdown.replace(f"# Voice Soul: {source.name}", f"# Voice Soul: {name}", 1)
        session.add(
            VoiceSoul(
                persona_id=copy.id,
                version=1,
                label=soul.label or f"From {source.name} v{soul.version}",
                markdown=markdown,
                best_practices=soul.best_practices,
                sample_ids=[id_map[i] for i in soul.sample_ids if i in id_map],
                baseline_stylometrics=soul.baseline_stylometrics,
                model=soul.model,
                edited_by_user=soul.edited_by_user,
            )
        )
        services.storage.voice_soul_path(copy.id, 1).write_text(markdown, encoding="utf-8")
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
    session.exec(delete(VoiceSoul).where(col(VoiceSoul.persona_id) == persona_id))  # type: ignore[call-overload]
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


# -- voice soul -----------------------------------------------------------------------


@router.post("/personas/{persona_id}/voice-soul", response_model=JobOut, status_code=202)
async def start_voice_soul(persona_id: int, session: SessionDep, services: ServicesDep, body: VoiceSoulGenerateIn | None = None) -> JobOut:
    persona_or_404(session, persona_id)
    if not session.exec(select(Sample).where(Sample.persona_id == persona_id, Sample.kind == "own")).first():
        raise HTTPException(422, "Add at least one sample of your own writing first.")
    active = services.jobs.active_for(persona_id=persona_id)
    if active:
        return JobOut(**active[0].model_dump())
    job = await services.jobs.start(
        "voice_soul",
        lambda ctx: generate_voice_soul(
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


@router.get("/personas/{persona_id}/voice-soul", response_model=VoiceSoulOut)
def get_voice_soul(persona_id: int, session: SessionDep, version: int | None = None) -> VoiceSoulOut:
    """The version in use (pinned, else latest), or a specific ``version``."""
    persona_or_404(session, persona_id)
    soul = current_voice_soul(session, persona_id) if version is None else voice_soul_version(session, persona_id, version)
    if soul is None:
        raise HTTPException(404, "No voice soul yet.")
    return soul_out(session, soul)


@router.get("/personas/{persona_id}/voice-soul/versions", response_model=list[VoiceSoulVersion])
def voice_soul_versions(persona_id: int, session: SessionDep) -> list[VoiceSoulVersion]:
    persona_or_404(session, persona_id)
    souls = session.exec(select(VoiceSoul).where(VoiceSoul.persona_id == persona_id).order_by(col(VoiceSoul.version).desc())).all()
    return [version_out(s) for s in souls]


@router.patch("/personas/{persona_id}/voice-soul/{version}", response_model=VoiceSoulOut)
def label_voice_soul(persona_id: int, version: int, body: VoiceSoulLabelIn, session: SessionDep) -> VoiceSoulOut:
    """Name a version, e.g. "Punchier, fewer jokes"."""
    persona_or_404(session, persona_id)
    soul = voice_soul_version(session, persona_id, version)
    if soul is None:
        raise HTTPException(404, f"Voice soul v{version} does not exist.")
    soul.label = body.label.strip()
    session.add(soul)
    session.commit()
    session.refresh(soul)
    return soul_out(session, soul)


@router.put("/personas/{persona_id}/voice-soul", response_model=VoiceSoulOut)
def edit_voice_soul(persona_id: int, body: VoiceSoulEdit, session: SessionDep, services: ServicesDep) -> VoiceSoulOut:
    """Save the user's edits as a new version (history is kept)."""
    persona_or_404(session, persona_id)
    latest = latest_voice_soul(session, persona_id)
    if latest is None:
        raise HTTPException(404, "Generate a voice soul before editing it.")
    soul = VoiceSoul(
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
    session.add(soul)
    unpin(session, persona_id)
    session.commit()
    session.refresh(soul)
    services.storage.voice_soul_path(persona_id, soul.version).write_text(soul.markdown, encoding="utf-8")
    return soul_out(session, soul)
