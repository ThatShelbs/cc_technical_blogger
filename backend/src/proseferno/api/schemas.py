"""Request and response models for the HTTP API (the frontend's TypeScript types are generated from these)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from proseferno.writer.dials import Dials

Education = Literal["beginner", "intermediate", "expert"]
SampleKind = Literal["own", "influence"]


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    version: str
    demo: bool = False


# -- auth / settings -------------------------------------------------------------


class AuthStatusOut(BaseModel):
    signed_in: bool
    source: str
    detail: str
    ant_installed: bool
    profile: str | None
    login_in_progress: bool
    login_output: str
    warnings: list[str]


class ApiKeyIn(BaseModel):
    api_key: str = Field(min_length=10)


class AuthTestOut(BaseModel):
    ok: bool
    message: str


class SettingsOut(BaseModel):
    model: str
    use_fallbacks: bool
    revision_passes: int
    cloudflare_account_id: str | None
    cloudflare_configured: bool
    image_provider_label: str
    data_dir: str
    seed_samples_dir: str
    version: str
    demo: bool


class SettingsIn(BaseModel):
    model: str | None = None
    use_fallbacks: bool | None = None
    revision_passes: int | None = Field(None, ge=0, le=2)
    cloudflare_account_id: str | None = None
    cloudflare_api_token: str | None = None


# -- personas / samples / voice ----------------------------------------------------


class PersonaCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    display_name: str = ""
    research_enabled: bool = False
    default_humor: int = Field(5, ge=0, le=10)
    default_education: Education = "intermediate"


class PersonaUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    display_name: str | None = None
    research_enabled: bool | None = None
    default_humor: int | None = Field(None, ge=0, le=10)
    default_education: Education | None = None
    visual_style: str | None = None
    credit_template: str | None = None


class PersonaOut(BaseModel):
    id: int
    name: str
    display_name: str
    is_active: bool
    research_enabled: bool
    default_humor: int
    default_education: str
    visual_style: str
    credit_template: str
    own_samples: int
    influence_samples: int
    voice_soul_version: int | None
    active_job_id: str | None
    created_at: datetime


class SampleOut(BaseModel):
    id: int
    persona_id: int
    kind: str
    source_name: str
    source_type: str
    title: str
    subtitle: str
    author: str
    word_count: int
    image_count: int
    analyzed: bool
    created_at: datetime


class SampleDetail(SampleOut):
    markdown: str
    captions: list[str]
    stylometrics: dict[str, Any]
    analysis: dict[str, Any] | None


class SampleUpdate(BaseModel):
    kind: SampleKind


class UrlImportIn(BaseModel):
    url: str
    kind: SampleKind = "influence"


class UploadResult(BaseModel):
    added: list[SampleOut]
    errors: list[str]


class SeedSamplesOut(BaseModel):
    available: bool
    directory: str
    files: list[str]


class VoiceSoulOut(BaseModel):
    id: int
    persona_id: int
    version: int
    markdown: str
    best_practices: str | None
    baseline_stylometrics: dict[str, Any]
    sample_count: int
    model: str
    edited_by_user: bool
    created_at: datetime


class VoiceSoulVersion(BaseModel):
    id: int
    version: int
    edited_by_user: bool
    created_at: datetime


class VoiceSoulEdit(BaseModel):
    markdown: str = Field(min_length=20)


# -- jobs -------------------------------------------------------------------------


class JobOut(BaseModel):
    id: str
    kind: str
    status: str
    progress: float
    message: str
    persona_id: int | None
    project_id: int | None
    result: dict[str, Any] | None
    error: str | None
    usage: dict[str, Any]
    created_at: datetime


# -- projects / images ------------------------------------------------------------------


class ProjectCreate(BaseModel):
    prompt: str = Field(min_length=3)
    persona_id: int | None = None
    dials: Dials = Field(default_factory=lambda: Dials())
    generate: bool = True


class ProjectUpdate(BaseModel):
    title: str | None = None
    markdown: str | None = None
    prompt: str | None = None
    dials: Dials | None = None


class ImageHistoryOut(BaseModel):
    index: int
    url: str
    provider: str
    caption: str
    created_at: str


class ImageOut(BaseModel):
    id: int
    slot_id: str
    position: int
    kind: str
    purpose: str
    prompt: str
    alt: str
    caption: str
    credit: str
    provider: str
    seed: int | None
    width: int
    height: int
    url: str | None
    status: str
    error: str | None
    history: list[ImageHistoryOut]


class ImageUpdate(BaseModel):
    caption: str | None = None
    alt: str | None = None
    credit: str | None = None
    prompt: str | None = None


class RedrawIn(BaseModel):
    rethink: bool = False


class RevertIn(BaseModel):
    index: int = Field(ge=0)


class ProjectSummary(BaseModel):
    id: int
    persona_id: int
    persona_name: str
    title: str
    prompt: str
    status: str
    thumbnail_url: str | None
    created_at: datetime
    updated_at: datetime


class ProjectOut(BaseModel):
    id: int
    persona_id: int
    title: str
    subtitle: str
    prompt: str
    dials: dict[str, Any]
    resolved_dials: dict[str, Any]
    status: str
    plan: dict[str, Any] | None
    markdown: str
    critique: dict[str, Any] | None
    fidelity: dict[str, Any] | None
    voice_soul_version: int | None
    error: str | None
    images: list[ImageOut]
    active_job_id: str | None
    created_at: datetime
    updated_at: datetime


class ProjectCreated(BaseModel):
    project: ProjectOut
    job_id: str | None


class RewriteIn(BaseModel):
    selection: str = Field(min_length=1)
    instruction: str = ""


class CopyHtmlOut(BaseModel):
    html: str
