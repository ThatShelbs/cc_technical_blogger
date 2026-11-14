"""Request and response models for the HTTP API (the frontend's TypeScript types are generated from these)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from proseferno.config import Connection
from proseferno.writer.dials import Dials, IncludeCode, Platform, ReferenceKind
from proseferno.writer.formulas import ArticleType, FormulaOption, FormulaParts

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
    reference_max_searches: int
    check_reference_links: bool
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
    reference_max_searches: int | None = Field(None, ge=1, le=8)
    check_reference_links: bool | None = None


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
    # null = choose from the length (at least 5), 0 = no references.
    default_reference_count: int | None = Field(None, ge=0, le=12)
    default_storytelling: int | None = Field(None, ge=0, le=10)
    default_opinion: int | None = Field(None, ge=0, le=10)
    default_formality: int | None = Field(None, ge=0, le=10)
    default_technical_depth: int | None = Field(None, ge=0, le=10)
    default_skimmability: int | None = Field(None, ge=0, le=10)
    default_include_code: IncludeCode | None = None
    default_platform: Platform | None = None
    # The formula new posts start from; {} = everything automatic.
    default_formula: FormulaParts | None = None
    # How new posts open: an opening style id or "auto" (unknown ids are stored as "auto").
    default_opening_style: str | None = Field(None, max_length=40)


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


Stage = Literal["draft", "ready", "published"]
Outcome = Literal["too_early", "small", "good", "viral"]
EvolutionKind = Literal["edits", "secret_sauce"]


class PlaybookEntry(BaseModel):
    text: str
    project_id: int | None = None
    title: str = ""
    outcome: str | None = None
    added_at: str = ""


class EvolutionItemOut(BaseModel):
    id: str
    area: str
    change: str
    evidence: str
    # profile | playbook
    target: str
    applied: bool = False


class EvolutionOut(BaseModel):
    id: int
    persona_id: int
    project_id: int | None
    # edits | secret_sauce
    kind: str
    outcome: str | None
    project_title: str
    # analyzing | pending | applied | dismissed | error | clean
    state: str
    summary: str
    items: list[EvolutionItemOut]
    edit_rate: float | None
    voice_profile_version: int | None
    applied_version: int | None
    job_id: str | None
    error: str | None
    created_at: datetime
    applied_at: datetime | None


class EditRatePoint(BaseModel):
    project_id: int | None
    title: str
    edit_rate: float
    created_at: datetime


class PersonaEvolutionOut(BaseModel):
    evolutions: list[EvolutionOut]
    # Share of generated text changed in each published post, oldest first: falls as the persona learns.
    edit_rates: list[EditRatePoint]
    playbook: list[PlaybookEntry]


class EvolveIn(BaseModel):
    kind: EvolutionKind


class ApplyEvolutionIn(BaseModel):
    item_ids: list[str] = Field(min_length=1)


class DiffSegment(BaseModel):
    # equal | insert | delete
    op: str
    text: str


class BaselineDiffOut(BaseModel):
    edit_rate: float
    baseline_title: str
    segments: list[DiffSegment]


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
    is_example: bool
    research_enabled: bool
    default_humor: int
    default_education: str
    default_target_words: int
    default_image_count: int | None
    default_reference_count: int | None
    default_storytelling: int
    default_opinion: int
    default_formality: int
    default_technical_depth: int
    default_skimmability: int
    default_include_code: str
    default_platform: str
    default_formula: FormulaParts
    default_opening_style: str
    visual_style: str
    credit_template: str
    voice_profile_words: int
    voice_sample_max_words: int
    voice_sample_min_words: int
    voice_influence_weight: int
    edit_lessons: list[EditLesson]
    playbook: list[PlaybookEntry]
    # Proposals from published posts waiting for review.
    pending_evolutions: int
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


class SampleWritingOut(BaseModel):
    """The bundled sample posts a person can start from when they have none of their own."""

    files: list[str]
    author: str


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


# -- formulas -----------------------------------------------------------------------


class FormulaCatalogOut(BaseModel):
    article_types: list[ArticleType]
    openers: list[FormulaOption]
    bodies: list[FormulaOption]
    closers: list[FormulaOption]


class FormulaIn(FormulaParts):
    """A formula saved under a name. Parts left out are automatic (the author's usual way)."""

    name: str = Field(min_length=1, max_length=80)
    description: str = Field("", max_length=200)


class FormulaOut(BaseModel):
    id: int
    name: str
    description: str
    article_type: str
    opener: str
    body: str
    closer: str
    opener_note: str
    body_note: str
    closer_note: str
    # The parts by name, e.g. "Tutorial · Cold open · Step by step".
    label: str
    created_at: datetime


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
    # Where the post is: draft -> ready -> published. Publishing compares it with the generated text.
    stage: Stage | None = None
    # How a published post did; Good traction or Viral reads it for its secret sauce.
    outcome: Outcome | None = None


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
    # Memes only: the format and joke in use, and how many other pitched ideas "New idea" can still try.
    # An opening meme (a meme sandwich) has this too, alongside ``opening``.
    meme: MemeInfoOut | None = None
    # The opening image only: its style, the panel's pitches and verdicts, sources and the render review.
    opening: OpeningInfoOut | None = None


class OpeningPitchOut(BaseModel):
    """One concept the opening room pitched, with the panel's scores."""

    index: int
    style: str
    style_label: str
    template: str
    hook: str
    concept: str
    # Each judge's 1-10 score: scroller, art_director, fact_checker, author.
    scores: dict[str, int]
    note: str
    total: int
    # A fact checker or author score under 5 rules a concept out (it is still on the board).
    ruled_out: bool
    tried: bool
    current: bool


class OpeningSourceOut(BaseModel):
    title: str
    url: str


class OpeningReviewOut(BaseModel):
    # "passed", "redrawn" (sent back once and redrawn), "kept" (the redraw was not better) or "skipped".
    verdict: str
    clickability: int = 0
    craft: int = 0
    problems: list[str] = []
    note: str = ""


class OpeningInfoOut(BaseModel):
    style: str
    style_label: str
    template: str
    # "auto" when the panel chose across styles, else the one style the pitches were limited to.
    mode: str
    summary: str
    ideas_left: int
    # Label of the style that was tried first when this image is a stand-in for it ("" otherwise).
    fallback_from: str
    pitches: list[OpeningPitchOut]
    sources: list[OpeningSourceOut]
    review: OpeningReviewOut | None
    # Words the author can retype with no model call (code-drawn styles only; numbers are not among them).
    slots: list[MemeSlotOut]
    # How platform thumbnails are cut from it: "cover" (centre crop) or "contain" (padded).
    thumbnail_fit: str


class OpeningStyleOut(BaseModel):
    id: str
    label: str
    summary: str
    when_to_use: str
    needs_data: bool
    min_humor: int


class OpeningCatalogOut(BaseModel):
    styles: list[OpeningStyleOut]
    # Style ids that suit each article type best (key "auto" = no type), in the order the panel weighs them.
    suggested_by_type: dict[str, list[str]]


class OpeningWordsIn(BaseModel):
    # Slot name -> new text (see ``ImageOut.opening.slots``); slots left out keep their words.
    words: dict[str, str] = Field(min_length=1)


class MemePitchOut(BaseModel):
    """One joke the writers' room pitched for this meme."""

    index: int
    format: str
    format_name: str
    premise: str
    words: list[str]
    tried: bool
    current: bool


class MemeSlotOut(BaseModel):
    """One piece of text in the meme, as the author can retype it."""

    name: str
    hint: str
    text: str
    max_chars: int
    optional: bool


class MemeInfoOut(BaseModel):
    format: str
    format_name: str
    premise: str
    ideas_left: int
    # False for formats drawn entirely by the template (chat, terminal, charts): there is no art to redraw.
    has_art: bool
    # Name of the format Claude could not draw, when this meme is a stand-in for it ("" otherwise).
    fallback_from: str
    pitches: list[MemePitchOut]
    slots: list[MemeSlotOut]


class MemeWordsIn(BaseModel):
    # Slot name -> new text; slots left out keep their words.
    words: dict[str, str] = Field(min_length=1)


class MemeFormatOut(BaseModel):
    id: str
    name: str
    family: str
    family_label: str
    when_to_use: str


class ImageUpdate(BaseModel):
    caption: str | None = None
    alt: str | None = None
    credit: str | None = None
    prompt: str | None = None


class RedrawIn(BaseModel):
    rethink: bool = False
    # Memes only: make the meme in this catalog format (see GET /api/meme-formats).
    meme_format: str | None = None
    # Memes only: draw this stored pitch (an index from ``ImageOut.meme.pitches``).
    meme_concept: int | None = Field(default=None, ge=0)
    # The opening image only: pitch again in this style (see GET /api/opening-styles), or build this stored pitch
    # (an index from ``ImageOut.opening.pitches``) with no new pitching or judging.
    opening_style: str | None = None
    opening_concept: int | None = Field(default=None, ge=0)


class ImageEditIn(BaseModel):
    instruction: str = Field(min_length=3, max_length=1000)


class RevertIn(BaseModel):
    index: int = Field(ge=0)


class ReferenceHistoryOut(BaseModel):
    index: int
    kind: str
    url: str
    title: str
    created_at: str


class ReferenceOut(BaseModel):
    id: int
    slot_id: str
    position: int
    kind: str
    placement: str
    purpose: str
    url: str
    title: str
    speaker: str
    quote: str
    status: str
    error: str | None
    # False once the author edited the reference's text out of the post.
    in_post: bool
    history: list[ReferenceHistoryOut]


class ReferenceRedrawIn(BaseModel):
    # Switch to another kind (e.g. a quote instead of a source); left out = the same kind.
    kind: ReferenceKind | None = None


class EnrichIn(BaseModel):
    # How many references to add; left out = enough to reach the post's reference count.
    count: int | None = Field(None, ge=1, le=12)
    kinds: list[ReferenceKind] | None = None


class ProjectSummary(BaseModel):
    id: int
    persona_id: int
    persona_name: str
    title: str
    prompt: str
    status: str
    stage: str
    outcome: str | None
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
    references: list[ReferenceOut]
    active_job_id: str | None
    active_job_kind: str | None
    stage: str
    outcome: str | None
    published_at: datetime | None
    # True when the generated text is on record, so edits can be compared with it.
    has_baseline: bool
    # Share of the generated text the author changed so far (None without a baseline).
    edit_rate: float | None
    evolutions: list[EvolutionOut]
    created_at: datetime
    updated_at: datetime


class ProjectCreated(BaseModel):
    project: ProjectOut
    job_id: str | None


class RewriteIn(BaseModel):
    selection: str = Field(min_length=1)
    instruction: str = Field(default="", max_length=4000)
    action: Literal["custom", "rewrite", "compact", "expand", "add_source", "add_quote"] = "custom"


class CopyHtmlOut(BaseModel):
    html: str


class LinkedInPostOut(BaseModel):
    text: str
    characters: int
    written_by: Literal["claude", "template"]


# -- persona insights ---------------------------------------------------------------


class InsightsOverview(BaseModel):
    persona_name: str
    own_samples: int
    influence_samples: int
    own_words: int
    voice_profile_version: int | None
    updated_at: datetime | None


class VoiceMixSlice(BaseModel):
    name: str
    description: str
    count: int
    # Percent of the labeled sentences.
    share: float


class InsightsDigestOut(BaseModel):
    headline: str
    tone: list[str]
    signature_phrases: list[str]
    steer_clear: list[str]
    voice_mix: list[VoiceMixSlice]
    sentences_sampled: int
    sentences_labeled: int
    image_habits: list[str]
    caption_example: str
    generated_at: str
    # The voice profile version the digest was made from.
    version: int
    # True when it was made from another version than the one in use (refresh to update it).
    stale: bool


class FingerprintRow(BaseModel):
    key: str
    label: str
    you: float
    reference: float | None
    unit: str


class FingerprintOut(BaseModel):
    reference_label: str
    # "influences" = measured from the persona's influence samples; "typical" = rough built-in values.
    reference_kind: Literal["influences", "typical"]
    rows: list[FingerprintRow]


class CountItem(BaseModel):
    id: str
    label: str
    count: int


class FormulaNode(BaseModel):
    id: str
    stage: Literal["article_type", "opener", "body", "closer"]
    label: str


class FormulaLink(BaseModel):
    source: str
    target: str
    value: int


class FormulaFlowOut(BaseModel):
    posts: int
    nodes: list[FormulaNode]
    links: list[FormulaLink]


class PostPoint(BaseModel):
    project_id: int
    title: str
    created_at: datetime
    stage: str
    outcome: str | None
    words: int
    authenticity: float | None
    voice_match: float | None
    critique: float | None


class LessonItem(BaseModel):
    kind: str
    old: str
    new: str
    count: int


class TrackRecordOut(BaseModel):
    posts: int
    published: int
    words: int
    images: int
    references: int
    stages: list[CountItem]
    outcomes: list[CountItem]
    points: list[PostPoint]
    meme_formats: list[CountItem]
    lessons: list[LessonItem]
    playbook: int


class PersonaInsightsOut(BaseModel):
    overview: InsightsOverview
    digest: InsightsDigestOut | None
    fingerprint: FingerprintOut | None
    openers: list[CountItem]
    phrases: list[CountItem]
    formula: FormulaFlowOut
    track_record: TrackRecordOut
