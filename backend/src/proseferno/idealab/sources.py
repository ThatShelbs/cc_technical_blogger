"""Where Idea Lab looks: the bundled catalog of free sources, plus what the author changed.

``catalog.json`` is the only place a source, person or industry is named; prompts receive names from here or from
what the research found. The author's changes (sources turned off, their own feeds, the watchlist, industries) are
stored whole under one ``AppSetting`` key.
"""

from __future__ import annotations

import json
import re
from functools import cache
from importlib import resources
from typing import Any, Literal
from urllib.parse import quote_plus

from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session

from proseferno.db import AppSetting, utcnow

SOURCES_KEY = "idea_sources"
HEALTH_KEY = "idea_source_health"

Group = Literal["vendor", "research", "code", "community", "creator", "industry", "search"]
Kind = Literal["rss", "hn", "hf_papers", "hf_models", "github", "stackexchange"]

GROUP_LABELS: dict[str, str] = {
    "vendor": "Vendors and platforms",
    "research": "Research",
    "code": "Code",
    "community": "Communities",
    "creator": "Creators and publications",
    "industry": "Industries",
    "search": "Web search",
}

MAX_CUSTOM = 40
MAX_NAMES = 40


class Source(BaseModel):
    id: str
    name: str
    group: Group
    kind: Kind = "rss"
    url: str
    enabled: bool = True
    # False for a feed the author added.
    builtin: bool = True


class CustomSource(BaseModel):
    """A feed the author added: any RSS or Atom address."""

    name: str = Field(min_length=1, max_length=80)
    url: str = Field(min_length=8, max_length=500)
    group: Group = "creator"

    @field_validator("url")
    @classmethod
    def _http(cls, value: str) -> str:
        value = value.strip()
        if not re.match(r"https?://[^\s/]+\.[^\s/]+", value):
            raise ValueError("A feed address starts with http:// or https://")
        return value


class SourceChanges(BaseModel):
    """What the author changed; ``None`` for the watchlist or industries means "as shipped"."""

    disabled: list[str] = Field(default_factory=list)
    enabled: list[str] = Field(default_factory=list)
    custom: list[CustomSource] = Field(default_factory=list, max_length=MAX_CUSTOM)
    voices: list[str] | None = Field(None, max_length=MAX_NAMES)
    industries: list[str] | None = Field(None, max_length=MAX_NAMES)


class SourceConfig(BaseModel):
    sources: list[Source]
    # Places with no open feed, covered by the web search scouts.
    search_only: list[str]
    voices: list[str]
    industries: list[str]

    def active(self) -> list[Source]:
        return [s for s in self.sources if s.enabled]


@cache
def _catalog() -> dict[str, Any]:
    text = resources.files(__package__).joinpath("catalog.json").read_text(encoding="utf-8")
    return json.loads(text)  # type: ignore[no-any-return]


def _clean_names(names: list[str]) -> list[str]:
    seen: dict[str, str] = {}
    for name in names:
        name = " ".join(str(name).split())[:80]
        if name and name.lower() not in seen:
            seen[name.lower()] = name
    return list(seen.values())[:MAX_NAMES]


def custom_id(url: str) -> str:
    return "custom_" + re.sub(r"[^a-z0-9]+", "_", url.lower().split("://", 1)[-1]).strip("_")[:60]


def news_source(query: str, *, source_id: str, name: str, group: Group = "industry") -> Source:
    """A Google News search feed for ``query`` over the last week (an open RSS feed, no key)."""
    url = f"https://news.google.com/rss/search?q={quote_plus(query + ' when:7d')}&hl=en-US&gl=US&ceid=US:en"
    return Source(id=source_id, name=name, group=group, kind="rss", url=url)


def industry_source(industry: str) -> Source:
    slug = re.sub(r"[^a-z0-9]+", "_", industry.lower()).strip("_")
    return news_source(
        f'"{industry}" (AI OR "machine learning" OR "data science")', source_id=f"news_{slug}", name=f"News: AI in {industry}"
    )


def build_config(changes: SourceChanges) -> SourceConfig:
    catalog = _catalog()
    disabled, enabled = set(changes.disabled), set(changes.enabled)
    sources = []
    for row in catalog["sources"]:
        source = Source(**row)
        if source.id in disabled:
            source.enabled = False
        elif source.id in enabled:
            source.enabled = True
        sources.append(source)
    for custom in changes.custom:
        source_id = custom_id(custom.url)
        if any(s.id == source_id for s in sources):
            continue
        sources.append(
            Source(
                id=source_id,
                name=custom.name,
                group=custom.group,
                kind="rss",
                url=custom.url,
                enabled=source_id not in disabled,
                builtin=False,
            )
        )
    voices = _clean_names(changes.voices if changes.voices is not None else catalog["voices"])
    industries = _clean_names(changes.industries if changes.industries is not None else catalog["industries"])
    for industry in industries:
        source = industry_source(industry)
        source.enabled = source.id not in disabled
        sources.append(source)
    return SourceConfig(sources=sources, search_only=list(catalog["search_only"]), voices=voices, industries=industries)


def load_changes(session: Session) -> SourceChanges:
    row = session.get(AppSetting, SOURCES_KEY)
    if row is None or not isinstance(row.value, dict):
        return SourceChanges()
    try:
        return SourceChanges.model_validate(row.value)
    except ValueError:
        return SourceChanges()


def load_config(session: Session) -> SourceConfig:
    return build_config(load_changes(session))


def save_changes(session: Session, changes: SourceChanges) -> SourceConfig:
    row = session.get(AppSetting, SOURCES_KEY) or AppSetting(key=SOURCES_KEY)
    row.value = changes.model_dump()
    session.add(row)
    session.commit()
    return build_config(changes)


def load_health(session: Session) -> dict[str, dict[str, Any]]:
    row = session.get(AppSetting, HEALTH_KEY)
    return dict(row.value) if row is not None and isinstance(row.value, dict) else {}


def save_health(session: Session, results: list[Any]) -> None:
    """Record how each source answered (``collect.SourceHealth`` rows); sources not read this time keep their last result."""
    health = load_health(session)
    now = utcnow().isoformat()
    for result in results:
        health[result.source_id] = {"ok": result.ok, "count": result.count, "error": result.error, "checked_at": now}
    row = session.get(AppSetting, HEALTH_KEY) or AppSetting(key=HEALTH_KEY)
    row.value = health
    session.add(row)
    session.commit()
