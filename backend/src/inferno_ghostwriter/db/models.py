"""Database tables. JSON columns hold structured data that is always read and
written whole (reassign the attribute after changing it so SQLAlchemy notices)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, Column, Text
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class Persona(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    # Name used in bylines and image credits.
    display_name: str = ""
    is_active: bool = False
    # The bundled "Sample Author": built offline, deletable in one click.
    is_example: bool = False
    research_enabled: bool = False
    # Default dials for new posts. The 0-10 style dials are relative to the author: 5 = as in their writing.
    default_humor: int = 5
    default_education: str = "intermediate"
    default_target_words: int = 1500
    # None = choose the number of images from the length.
    default_image_count: int | None = None
    # None = choose the number of references (sources, quotes, posts, resources) from the length; 0 = none.
    default_reference_count: int | None = None
    default_storytelling: int = 5
    default_opinion: int = 5
    default_formality: int = 5
    default_technical_depth: int = 5
    default_skimmability: int = 5
    default_include_code: str = "auto"
    default_platform: str = "medium"
    # The formula new posts start from (see writer.formulas): article_type, opener, body, closer and notes; {} = all automatic.
    default_formula: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, default={}))
    # How new posts open (see images.opening.styles): a style id, or "auto" = the panel picks from the styles that suit the post.
    default_opening_style: str = "auto"
    # Interview the author (3-5 questions for the brief) before writing each new post; off = write straight away.
    default_interview: bool = False
    # Voice profile version used for new posts; None = always the latest.
    pinned_voice_profile_version: int | None = None
    # One line that keeps a post's generated images looking like a set.
    visual_style: str = ""
    # How image credits read; {name} = display name, {tool} = what made the image.
    credit_template: str = "Author: {name}; Made with {tool}"
    # Voice profile settings: target length of voice_profile.md, the sample budget, and how much
    # influence samples shape it (0 = ignore them, 5 = borrow fitting techniques, 10 = lean on them).
    voice_profile_words: int = 2000
    # Words of each sample the analysis reads (0 = the whole sample); shorter samples are skipped.
    voice_sample_max_words: int = 0
    voice_sample_min_words: int = 0
    voice_influence_weight: int = 5
    # Where the voice comes from: "samples" (the author's own posts), or, for authors with none,
    # "archetype" | "blend" | "interview" | "random" (see voice.sources). source_spec holds the choice.
    source: str = "samples"
    source_spec: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, default={}))
    # What the author keeps changing in generated posts (see voice.lessons), most frequent first.
    edit_lessons: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, default=[]))
    # What made the author's well-received posts work (see voice.playbook): {text, project_id, title, outcome, added_at}.
    playbook: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, default=[]))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Sample(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    persona_id: int = Field(foreign_key="persona.id", index=True)
    # "own" = the persona's writing (defines identity); "influence" = others' (borrow techniques).
    kind: str = "own"
    source_name: str
    source_type: str
    title: str = ""
    subtitle: str = ""
    author: str = ""
    markdown: str = Field(default="", sa_column=Column(Text))
    word_count: int = 0
    image_count: int = 0
    captions: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    stylometrics: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    analysis: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    # How strongly this post is favored when choosing the examples the writer sees (1 = neutral; raised by A/B wins).
    weight: float = 1.0
    created_at: datetime = Field(default_factory=utcnow)


class VoiceProfile(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    persona_id: int = Field(foreign_key="persona.id", index=True)
    version: int
    # Optional user-given name for this version, e.g. "Punchier, fewer jokes".
    label: str = ""
    markdown: str = Field(sa_column=Column(Text))
    best_practices: str | None = Field(default=None, sa_column=Column(Text))
    sample_ids: list[int] = Field(default_factory=list, sa_column=Column(JSON))
    baseline_stylometrics: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    # The Insights page digest (see voice.insights); None for edited, evolved and older versions.
    insights: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    model: str = ""
    edited_by_user: bool = False
    created_at: datetime = Field(default_factory=utcnow)


class Project(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    persona_id: int = Field(foreign_key="persona.id", index=True)
    prompt: str = Field(sa_column=Column(Text))
    title: str = ""
    subtitle: str = ""
    dials: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    # new -> generating -> ready | error
    status: str = "new"
    plan: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    markdown: str = Field(default="", sa_column=Column(Text))
    critique: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    fidelity: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    # AI-writing detection report: 100 = reads as authentic human prose, 0 = almost certainly flagged as AI.
    authenticity: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    # Platform companions, e.g. {"linkedin_post": "..."}.
    social: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    # Title options the author pinned: kept when new options are generated and across regenerations.
    # The SQL default lets add_missing_columns backfill existing rows with [].
    pinned_titles: list[str] = Field(default_factory=list, sa_column=Column(JSON, default=[]))
    # Earlier text versions, newest first (see writer.revisions): what "Undo" restores. Cleared by a full regeneration.
    revisions: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, default=[]))
    # This post's image look (see images.brand): palette, font, motif, style; empty = the persona's visual style.
    brand_kit: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, default={}))
    voice_profile_version: int | None = None
    error: str | None = None
    # Where the author is with the post: draft -> ready -> published (separate from the generation ``status``).
    stage: str = "draft"
    # How a published post did: too_early | small | good | viral; None until published.
    outcome: str | None = None
    published_at: datetime | None = None
    # The text exactly as the app last generated it (reset by each full generation), to compare with what was published.
    baseline_markdown: str = Field(default="", sa_column=Column(Text, default=""))
    baseline_title: str = ""
    # Set only on the two hidden posts of an A/B test (see abtest.service): which test, and control | challenger.
    ab_test_id: int | None = Field(default=None, index=True)
    variant: str | None = None
    # The Idea Lab idea this post was written from (see idealab), if any.
    idea_id: int | None = None
    # The optional interview (see writer.interview): [{question, answer}]; answered ones are woven into the post.
    interview: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, default=[]))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class IdeaSignal(SQLModel, table=True):
    """One item the Idea Lab research found: a feed entry, a discussion, a paper, or a page a web search cited.

    Shared by every persona. Only the title, link, date and a short summary are kept, never the full text.
    """

    id: int | None = Field(default=None, primary_key=True)
    source_id: str = Field(index=True)
    source_name: str = ""
    # vendor | research | code | community | creator | industry | search
    group: str = ""
    url: str = Field(index=True, unique=True)
    title: str = ""
    summary: str = Field(default="", sa_column=Column(Text, default=""))
    author: str = ""
    published_at: datetime | None = None
    # Points, stars, upvotes or reactions where the source reports them; 0 otherwise.
    engagement: int = 0
    # The author's own search that found it ("send another search"); empty for the standing sources.
    query: str = ""
    fetched_at: datetime = Field(default_factory=utcnow)


class IdeaTrend(SQLModel, table=True):
    """Something happening in the field, grouped from signals by the research digest (see idealab.research)."""

    id: int | None = Field(default=None, primary_key=True)
    # launch | claim | industry_pattern | creator_wave | question
    kind: str = "launch"
    label: str = Field(index=True)
    summary: str = Field(default="", sa_column=Column(Text, default=""))
    # 1-10: how much attention it is getting right now.
    heat: int = 5
    industries: list[str] = Field(default_factory=list, sa_column=Column(JSON, default=[]))
    # [{url, title}]: every link is a collected signal or a search citation.
    evidence: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, default=[]))
    first_seen: datetime = Field(default_factory=utcnow)
    last_seen: datetime = Field(default_factory=utcnow)


class IdeaSession(SQLModel, table=True):
    """One brainstorm: a set of ideas made for a persona in one run."""

    id: int | None = Field(default=None, primary_key=True)
    persona_id: int = Field(foreign_key="persona.id", index=True)
    # light (10 ideas) | medium (25) | heavy (50)
    mode: str = "light"
    # How many ideas each source approach was asked for: {approach: count}.
    mix: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, default={}))
    # What the author wants more of this time, and their own half-ideas to develop.
    focus: str = Field(default="", sa_column=Column(Text, default=""))
    sparks: str = Field(default="", sa_column=Column(Text, default=""))
    # running | ready | error
    status: str = "running"
    # Things the author should know about the run, e.g. a source approach that had nothing to work from.
    notes: list[str] = Field(default_factory=list, sa_column=Column(JSON, default=[]))
    job_id: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


class Idea(SQLModel, table=True):
    """A post the author could write next: title, brief and outline, with where it came from and how it ranks."""

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="ideasession.id", index=True)
    persona_id: int = Field(index=True)
    # emerging | builder | expander | reader_questions | counter_take | sparks
    approach: str
    theme: str = ""
    title: str
    brief: str = Field(default="", sa_column=Column(Text, default=""))
    # What makes this the author's post and not everyone's.
    angle: str = Field(default="", sa_column=Column(Text, default=""))
    outline: list[str] = Field(default_factory=list, sa_column=Column(JSON, default=[]))
    why_now: str = Field(default="", sa_column=Column(Text, default=""))
    # this_week | this_month | evergreen
    shelf_life: str = "evergreen"
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON, default=[]))
    # [{url, title}] taken from the trends the idea rests on.
    evidence: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, default=[]))
    # A formula catalog id, or "auto".
    article_type: str = "auto"
    # The existing post a builder idea follows on from.
    builds_on: str = ""
    # {timeliness, demand, fit, differentiation, effort}, each 1-10, plus the ranker's one-line note.
    scores: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, default={}))
    score: float = 0.0
    # 1 = the best idea of its session.
    rank: int = 0
    # new | saved | dismissed | used (the lifecycle stage shown to the author is derived: see idealab.lifecycle)
    state: str = "new"
    project_id: int | None = None
    # The author's own note on the idea (what they would add, who to ask, ...).
    note: str = Field(default="", sa_column=Column(Text, default=""))
    created_at: datetime = Field(default_factory=utcnow)


class ABTest(SQLModel, table=True):
    """Two full generations of one post, compared blind (see abtest.service).

    ``control`` is written with the persona and settings as they are; ``challenger`` with every setting nudged
    at random. Both are hidden ``Project`` rows until the author picks a winner, which is then moved into the
    host project (``project_id``) and both variants are deleted.
    """

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(index=True)
    persona_id: int = Field(index=True)
    # generating | voting | deciding | decided | discarded | error
    status: str = "generating"
    seed: int = 0
    # Which variant is shown as "Post 1" (left): control | challenger.
    left_role: str = "control"
    control_project_id: int | None = None
    challenger_project_id: int | None = None
    # What the challenger changed: [{id, group, label, before, after, target, field, value}].
    tweaks: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, default=[]))
    # The challenger's extra writer-system block and the example posts it was shown.
    emphasis: str = Field(default="", sa_column=Column(Text, default=""))
    exemplar_ids: list[int] = Field(default_factory=list, sa_column=Column(JSON, default=[]))
    # control | challenger, once decided.
    winner: str | None = None
    # Parts taken from the other post: title | opener | closer | hero | meme | image_style.
    taken: list[str] = Field(default_factory=list, sa_column=Column(JSON, default=[]))
    # Tweak ids the author adopted into the persona; None = not answered yet.
    adopted: list[str] | None = Field(default=None, sa_column=Column(JSON))
    evolution_id: int | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    decided_at: datetime | None = None


class PersonaEvolution(SQLModel, table=True):
    """A proposed change to a persona, learned from one post (see evolution.service).

    ``edits`` compares the generated baseline with the published text; ``secret_sauce`` reads a post that did
    well. Items are reviewed and applied by the author: profile items become a new voice profile version,
    playbook items join ``Persona.playbook``.
    """

    id: int | None = Field(default=None, primary_key=True)
    persona_id: int = Field(foreign_key="persona.id", index=True)
    project_id: int | None = Field(default=None, index=True)
    # edits | secret_sauce | ab_test
    kind: str
    # The post's outcome when this was made.
    outcome: str | None = None
    project_title: str = ""
    # analyzing | pending | applied | dismissed | error
    state: str = "analyzing"
    summary: str = Field(default="", sa_column=Column(Text, default=""))
    # [{id, area, change, evidence, target: profile|playbook, applied}]
    items: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, default=[]))
    # Share of the generated text the author changed (edits only), 0-1.
    edit_rate: float | None = None
    # The baseline this was computed from, so a re-publish of the same text does not analyze twice.
    baseline_hash: str = ""
    voice_profile_version: int | None = None
    applied_version: int | None = None
    job_id: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    applied_at: datetime | None = None


class ProjectImage(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    slot_id: str
    position: int = 0
    # hero | illustration | icon | diagram | chart | meme | screenshot
    kind: str
    purpose: str = ""
    anchor: str = ""
    prompt: str = Field(default="", sa_column=Column(Text))
    # Kind-specific render source: SVG markup, Vega-Lite JSON, or meme caption JSON.
    spec: str = Field(default="", sa_column=Column(Text))
    alt: str = ""
    caption: str = ""
    credit: str = ""
    provider: str = ""
    seed: int | None = None
    width: int = 0
    height: int = 0
    file_name: str | None = None
    # pending | ready | error | placeholder
    status: str = "pending"
    error: str | None = None
    history: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    # The slot id of an earlier image this one extends (a chart then the same chart split by group): it is drawn
    # from that image's source so both share data, colors and shapes. Empty = stands alone.
    builds_on: str = ""
    # What the last redraw tried (see images/remix.py): the critique, the improvements and the twist, newest tweaks first.
    remix: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    # The author's "Edit" instructions since this image's idea was last picked (newest last). While there are any,
    # a redraw or remix builds on the edited picture instead of going back to the original brief or pitch.
    edits: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    # The author's thumbs on an opening image or closing meme: 1 liked, -1 passed, 0 none (feeds images/taste.py).
    rating: int = 0


class ProjectReference(SQLModel, table=True):
    """One external reference woven into a post: a source, quote, social post, resource or related article.

    The post stays plain Markdown; ``inserted`` is the exact text this reference put there and ``original``
    the text it replaced, so a redraw can swap it and a removal can put the original back.
    """

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    slot_id: str
    position: int = 0
    # source | quote | social_post | resource | related_article
    kind: str
    # inline | blockquote | go_deeper
    placement: str = "inline"
    # The sentence it backs up (inline and blockquote), or the "Go deeper" heading (go_deeper).
    anchor: str = Field(default="", sa_column=Column(Text))
    purpose: str = ""
    query: str = ""
    url: str = ""
    title: str = ""
    # Who said or wrote it (quotes and social posts).
    speaker: str = ""
    quote: str = Field(default="", sa_column=Column(Text))
    original: str = Field(default="", sa_column=Column(Text))
    inserted: str = Field(default="", sa_column=Column(Text))
    # pending | ready | error
    status: str = "pending"
    error: str | None = None
    tried_urls: list[str] = Field(default_factory=list, sa_column=Column(JSON, default=[]))
    # True when the author pasted this link themselves; Redraw then re-reads that page instead of searching.
    user_supplied: bool = False
    # Every version placed in the post, oldest first (the current one included).
    history: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, default=[]))
    created_at: datetime = Field(default_factory=utcnow)


class Formula(SQLModel, table=True):
    """A formula the author built and named, to reuse across posts and personas (see writer.formulas)."""

    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str = ""
    # Catalog ids; "auto" = the author's usual way.
    article_type: str = "auto"
    opener: str = "auto"
    body: str = "auto"
    closer: str = "auto"
    # The author's own instructions for each part.
    opener_note: str = ""
    body_note: str = ""
    closer_note: str = ""
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Job(SQLModel, table=True):
    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    kind: str
    # queued | running | succeeded | failed
    status: str = "queued"
    progress: float = 0.0
    message: str = ""
    persona_id: int | None = None
    project_id: int | None = None
    result: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    error: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class AppSetting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: Any = Field(default=None, sa_column=Column(JSON))
