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
    research_enabled: bool = False
    default_humor: int = 5
    default_education: str = "intermediate"
    # One line that keeps a post's generated images looking like a set.
    visual_style: str = ""
    # How image credits read; {name} = display name, {tool} = what made the image.
    credit_template: str = "Author: {name}; Made with {tool}"
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
    created_at: datetime = Field(default_factory=utcnow)


class VoiceSoul(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    persona_id: int = Field(foreign_key="persona.id", index=True)
    version: int
    markdown: str = Field(sa_column=Column(Text))
    best_practices: str | None = Field(default=None, sa_column=Column(Text))
    sample_ids: list[int] = Field(default_factory=list, sa_column=Column(JSON))
    baseline_stylometrics: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
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
    voice_soul_version: int | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class ProjectImage(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    slot_id: str
    position: int = 0
    # hero | diagram | chart | illustration | meme | screenshot
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
