from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session

from proseferno.db import Persona, Project, ProjectImage, Sample
from proseferno.services import Services


def get_services(request: Request) -> Services:
    return request.app.state.services  # type: ignore[no-any-return]


ServicesDep = Annotated[Services, Depends(get_services)]


def get_session(services: ServicesDep) -> Iterator[Session]:
    with Session(services.engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


def persona_or_404(session: Session, persona_id: int) -> Persona:
    persona = session.get(Persona, persona_id)
    if persona is None:
        raise HTTPException(404, "Persona not found.")
    return persona


def sample_or_404(session: Session, sample_id: int) -> Sample:
    sample = session.get(Sample, sample_id)
    if sample is None:
        raise HTTPException(404, "Sample not found.")
    return sample


def project_or_404(session: Session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found.")
    return project


def image_or_404(session: Session, image_id: int) -> ProjectImage:
    image = session.get(ProjectImage, image_id)
    if image is None:
        raise HTTPException(404, "Image not found.")
    return image
