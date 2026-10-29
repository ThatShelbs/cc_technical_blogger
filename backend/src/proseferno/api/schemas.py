"""Request and response models for the HTTP API (the frontend's TypeScript types are generated from these)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from proseferno.config import Connection
from proseferno.writer.dials import Dials, IncludeCode, Platform

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
    connection: Connection
    claude_code_installed: bool
    claude_code_version: str | None
    claude_code_signed_in: bool
    claude_code_auth_method: str | None
    claude_code_email: str | None
    subscription_type: str | None


class ApiKeyIn(BaseModel):
    api_key: str = Field(min_length=10)


class AuthTestOut(BaseModel):
    ok: bool
    message: str


class SettingsOut(BaseModel):
    claude_connection: Connection
    model: str
    use_fallbacks: bool
    revision_passes: int
    ai_detection: bool
    image_tool_label: str
    data_dir: str
    seed_samples_dir: str
    version: str
    demo: bool


class SettingsIn(BaseModel):
    claude_connection: Connection | None = None
    model: str | None = None
    use_fallbacks: bool | None = None
    revision_passes: int | None = Field(None, ge=0, le=2)
    ai_detection: bool | None = None


# -- personas / samples / voice ----------------------------------------------------


class PersonaCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    display_name: str = ""
    research_enabled: bool = False
    default_humor: int = Field(5, ge=0, le=10)
    default_education: Education = "intermediate"


class PersonaDefaults(BaseModel):
    """Default dials for the persona's new posts (every field optional on update)."""

    default_humor: int | None = Field(None, ge=0, le=10)
    default_education: Education | None = None
    default_target_words: int | None = Field(None, ge=300, le=6000)
    # 0 = choose automatically from the length.
    default_image_count: int | None = Field(None, ge=0, le=15)
    default_storytelling: int | None = Field(None, ge=0, le=10)
    default_opinion: int | None = Field(None, ge=0, le=10)
    default_formality: int | None = Field(None, ge=0, le=10)
    default_technical_depth: int | None = Field(None, ge=0, le=10)
    default_skimmability: int | None = Field(None, ge=0, le=10)
    default_include_code: IncludeCode | None = None
    default_platform: Platform | None = None


class PersonaUpdate(PersonaDefaults):
    name: str | None = Field(None, min_length=1, max_length=80)
    display_name: str | None = None
    research_enabled: bool | None = None
    visual_style: str | None = None
    credit_template: str | None = None
    voice_profile_words: int | None = Field(None, ge=500, le=6000)
    voice_sample_max_words: int | None = Field(None, ge=0, le=50000)
    voice_sample_min_words: int | None = Field(None, ge=0, le=5000)
    voice_influence_weight: int | None = Field(None, ge=0, le=10)
    # Which voice profile version new posts use; null = always the latest.
    pinned_voice_profile_version: int | None = None


class VoiceProfileVersion(BaseModel):
    id: int
    version: int
    label: str
    edited_by_user: bool
    created_at: datetime


class EditLesson(BaseModel):
    # remove | replace | feedback
    kind: str
    old: str
    new: str = ""
    count: int = 1
    last_seen: str = ""


class PersonaOut(BaseModel):
    id: int
    name: str
    display_name: str
    is_active: bool
    research_enabled: bool
    default_humor: int
    default_education: str
    default_target_words: int
    default_image_count: int | None
    default_storytelling: int
    default_opinion: int
    default_formality: int
    default_technical_depth: int
    default_skimmability: int
    default_include_code: str
    default_platform: str
    visual_style: str
    credit_template: str
    voice_profile_words: int
    voice_sample_max_words: int
    voice_sample_min_words: int
    voice_influence_weight: int
    edit_lessons: list[EditLesson]
    own_samples: int
    influence_samples: int
    # The version new posts use (pinned, else latest).
    voice_profile_version: int | None
    voice_profile_label: str
    latest_voice_profile_version: int | None
    pinned_voice_profile_version: int | None
    voice_profile_versions: list[VoiceProfileVersion]
    active_job_id: str | None
    created_at: datetime


class PersonaDuplicateIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    display_name: str | None = None
    # Copy this voice profile version as the new persona's v1 (null = start without one).
    voice_profile_version: int | None = None
    copy_samples: bool = True


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


class VoiceProfileOut(BaseModel):
    id: int
    persona_id: int
    version: int
    label: str
    in_use: bool
    markdown: str
    best_practices: str | None
    baseline_stylometrics: dict[str, Any]
    sample_count: int
    model: str
    edited_by_user: bool
    created_at: datetime


class VoiceProfileEdit(BaseModel):
    markdown: str = Field(min_length=20)
    label: str = Field("", max_length=80)


class VoiceProfileGenerateIn(BaseModel):
    label: str = Field("", max_length=80)


class VoiceProfileLabelIn(BaseModel):
    label: str = Field(max_length=80)


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
    brand_kit: BrandKit | None = None
    generate: bool = True


class BrandKit(BaseModel):
    """How this post's images look; every field is optional and falls back to the persona's visual style."""

    style: str = Field("", max_length=300)
    # Hex colors, e.g. "#1b0c41"; empty = the inferno palette.
    palette: list[str] = Field(default_factory=list, max_length=8)
    font: str = Field("", max_length=80)
    motif: str = Field("", max_length=200)

    @field_validator("palette")
    @classmethod
    def _hex_colors(cls, value: list[str]) -> list[str]:
        colors = [c.strip().lower() for c in value if c.strip()]
        bad = [c for c in colors if not re.fullmatch(r"#[0-9a-f]{6}", c)]
        if bad:
            raise ValueError(f"Colors must look like #1b0c41: {', '.join(bad)}")
        return colors


class ProjectUpdate(BaseModel):
    title: str | None = None
    pinned_titles: list[str] | None = None
    markdown: str | None = None
    # Learn from this manual edit (what the author removes or replaces) for later posts.
    learn: bool = True
    brand_kit: BrandKit | None = None
    prompt: str | None = Field(None, min_length=3)
    dials: Dials | None = None
    persona_id: int | None = None


class GenerateIn(BaseModel):
    """Optional changes to apply before regenerating; anything left out keeps the post's current value."""

    prompt: str | None = Field(None, min_length=3)
    dials: Dials | None = None
    persona_id: int | None = None


class TweakIn(BaseModel):
    feedback: str = Field(min_length=3, max_length=4000)


class RevisionOut(BaseModel):
    index: int
    label: str
    kind: str
    created_at: str
    word_count: int


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


class ImageEditIn(BaseModel):
    instruction: str = Field(min_length=3, max_length=1000)


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
    authenticity: dict[str, Any] | None
    social: dict[str, Any] | None
    pinned_titles: list[str]
    brand_kit: BrandKit
    revisions: list[RevisionOut]
    voice_profile_version: int | None
    error: str | None
    images: list[ImageOut]
    active_job_id: str | None
    active_job_kind: str | None
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


class LinkedInPostOut(BaseModel):
    text: str
    characters: int
    written_by: Literal["claude", "template"]
