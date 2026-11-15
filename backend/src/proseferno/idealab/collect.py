"""Read the free feeds and open APIs in the source catalog. No model call, no keys.

Each request is a plain GET with a generic client name and nothing about the author in it. Only the title, link,
date, a short summary and an engagement number are kept. One source failing never fails the run: its error is
reported as that source's health.
"""

from __future__ import annotations

import asyncio
import html
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any, Protocol
from xml.etree import ElementTree

import httpx

from proseferno.idealab.sources import Source

log = logging.getLogger(__name__)

SUMMARY_CHARS = 300
MAX_BYTES = 3_000_000
PER_SOURCE = 30
USER_AGENT = "Mozilla/5.0 (compatible; Proseferno feed reader)"


@dataclass
class Signal:
    source_id: str
    source_name: str
    group: str
    url: str
    title: str
    summary: str = ""
    author: str = ""
    published_at: datetime | None = None
    engagement: int = 0
    query: str = ""


@dataclass
class SourceHealth:
    source_id: str
    ok: bool
    count: int = 0
    error: str = ""


class SignalCollector(Protocol):
    async def collect(self, sources: list[Source], *, since: datetime) -> tuple[list[Signal], list[SourceHealth]]: ...


class NoSignalCollector:
    """Never goes online (tests and demo mode): returns the signals it was given, as if every source answered."""

    def __init__(self, signals: list[Signal] | None = None) -> None:
        self.signals = signals

    async def collect(self, sources: list[Source], *, since: datetime) -> tuple[list[Signal], list[SourceHealth]]:
        if self.signals is None:
            from proseferno.idealab.demo_data import demo_signals

            signals = demo_signals()
        else:
            signals = list(self.signals)
        ids = {s.id for s in sources}
        counts = {source_id: sum(1 for s in signals if s.source_id == source_id) for source_id in ids}
        return signals, [SourceHealth(source_id=s.id, ok=True, count=counts.get(s.id, 0)) for s in sources]


class HttpSignalCollector:
    def __init__(self, *, timeout: float = 12.0, concurrency: int = 8, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.timeout = timeout
        self.concurrency = concurrency
        self.transport = transport

    async def collect(self, sources: list[Source], *, since: datetime) -> tuple[list[Signal], list[SourceHealth]]:
        gate = asyncio.Semaphore(self.concurrency)
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=self.timeout,
            transport=self.transport,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json, application/rss+xml, application/atom+xml, text/xml, */*"},
        ) as client:

            async def one(source: Source) -> tuple[list[Signal], SourceHealth]:
                async with gate:
                    try:
                        signals = await self._read(client, source, since)
                    except (httpx.HTTPError, ValueError, KeyError, TypeError, ElementTree.ParseError) as exc:
                        log.info("Idea source %s failed: %s", source.id, exc)
                        return [], SourceHealth(source_id=source.id, ok=False, error=_short_error(exc))
                    return signals, SourceHealth(source_id=source.id, ok=True, count=len(signals))

            results = await asyncio.gather(*(one(source) for source in sources))
        signals = [signal for found, _ in results for signal in found]
        return signals, [health for _, health in results]

    async def _read(self, client: httpx.AsyncClient, source: Source, since: datetime) -> list[Signal]:
        url = source.url.replace("{since_date}", since.date().isoformat()).replace("{since_ts}", str(int(since.timestamp())))
        response = await client.get(url)
        response.raise_for_status()
        if len(response.content) > MAX_BYTES:
            raise ValueError("The feed is too large.")
        signals = parse(source, response.text if source.kind == "rss" else response.json())
        fresh = [s for s in signals if s.published_at is None or s.published_at >= since]
        return fresh[:PER_SOURCE]


def parse(source: Source, payload: Any) -> list[Signal]:
    """Turn one source's response into signals; ``payload`` is feed text for ``rss`` and decoded JSON otherwise."""
    parser = _PARSERS[source.kind]
    out = []
    for row in parser(payload):
        url, title = str(row.get("url") or "").strip(), clean_text(str(row.get("title") or ""))
        if not url.startswith(("http://", "https://")) or not title:
            continue
        out.append(
            Signal(
                source_id=source.id,
                source_name=source.name,
                group=source.group,
                url=url,
                title=title[:300],
                summary=clean_text(str(row.get("summary") or ""))[:SUMMARY_CHARS],
                author=clean_text(str(row.get("author") or ""))[:120],
                published_at=row.get("published_at"),
                engagement=int(row.get("engagement") or 0),
            )
        )
    return out


# -- text and dates ------------------------------------------------------------------------


def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(html.unescape(text).split())


def parse_date(value: Any) -> datetime | None:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, UTC)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(text)
        except (TypeError, ValueError):
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _short_error(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"The source answered {exc.response.status_code}."
    if isinstance(exc, httpx.TimeoutException):
        return "The source did not answer in time."
    return (str(exc) or exc.__class__.__name__)[:200]


# -- parsers -------------------------------------------------------------------------------


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _child_text(node: ElementTree.Element, *names: str) -> str:
    for child in node:
        if _local(child.tag) in names and (child.text or "").strip():
            return (child.text or "").strip()
    return ""


def _rss(text: str) -> list[dict[str, Any]]:
    """RSS 2.0 and Atom. A feed that declares a DOCTYPE or entities is refused rather than expanded."""
    if re.search(r"<!(DOCTYPE|ENTITY)", text[:4000], re.IGNORECASE):
        raise ValueError("The feed declares a document type, which is not read.")
    root = ElementTree.fromstring(text.encode("utf-8"))
    rows = []
    for node in root.iter():
        if _local(node.tag) not in ("item", "entry"):
            continue
        link = _child_text(node, "link")
        if not link:
            # Atom: <link href="..." rel="alternate"/>
            links = [c for c in node if _local(c.tag) == "link" and c.get("href")]
            preferred = [c for c in links if c.get("rel") in (None, "alternate")]
            link = ((preferred or links)[0].get("href") or "") if links else ""
        author = _child_text(node, "creator", "author")
        if not author:
            for child in node:
                if _local(child.tag) == "author":
                    author = _child_text(child, "name")
        rows.append(
            {
                "url": link,
                "title": _child_text(node, "title"),
                "summary": _child_text(node, "description", "summary", "encoded", "content"),
                "author": author,
                "published_at": parse_date(_child_text(node, "pubdate", "published", "updated", "date")),
            }
        )
    return rows


def _hn(payload: Any) -> list[dict[str, Any]]:
    return [
        {
            # The discussion is the signal: what people argue about, not only what was linked.
            "url": f"https://news.ycombinator.com/item?id={hit['objectID']}",
            "title": hit.get("title") or "",
            "summary": f"{hit.get('num_comments') or 0} comments. Links to {hit.get('url')}" if hit.get("url") else "",
            "author": hit.get("author") or "",
            "published_at": parse_date(hit.get("created_at_i")),
            "engagement": hit.get("points") or 0,
        }
        for hit in payload.get("hits", [])
    ]


def _hf_papers(payload: Any) -> list[dict[str, Any]]:
    rows = []
    for item in payload:
        paper = item.get("paper") or {}
        if not paper.get("id"):
            continue
        rows.append(
            {
                "url": f"https://huggingface.co/papers/{paper['id']}",
                "title": paper.get("title") or item.get("title") or "",
                "summary": paper.get("ai_summary") or paper.get("summary") or "",
                "published_at": parse_date(item.get("publishedAt") or paper.get("publishedAt")),
                "engagement": paper.get("upvotes") or 0,
            }
        )
    return rows


def _hf_models(payload: Any) -> list[dict[str, Any]]:
    return [
        {
            "url": f"https://huggingface.co/{model['id']}",
            "title": f"Trending model: {model['id']}",
            "summary": " ".join(filter(None, [model.get("pipeline_tag"), f"{model.get('downloads') or 0} downloads"])),
            # Trending now, whenever it was first uploaded.
            "published_at": None,
            "engagement": model.get("likes") or 0,
        }
        for model in payload
        if model.get("id")
    ]


def _github(payload: Any) -> list[dict[str, Any]]:
    return [
        {
            "url": repo.get("html_url") or "",
            "title": f"{repo.get('full_name')}: {repo.get('description') or 'new repository'}",
            "summary": " ".join(filter(None, [repo.get("language"), ", ".join((repo.get("topics") or [])[:6])])),
            "author": (repo.get("owner") or {}).get("login") or "",
            "published_at": parse_date(repo.get("created_at")),
            "engagement": repo.get("stargazers_count") or 0,
        }
        for repo in payload.get("items", [])
    ]


def _stackexchange(payload: Any) -> list[dict[str, Any]]:
    return [
        {
            "url": question.get("link") or "",
            "title": question.get("title") or "",
            "summary": f"{question.get('answer_count') or 0} answers, {question.get('view_count') or 0} views. Tags: "
            + ", ".join((question.get("tags") or [])[:5]),
            # A hot question counts from when it was last active, not when it was first asked.
            "published_at": parse_date(question.get("last_activity_date")),
            "engagement": question.get("score") or 0,
        }
        for question in payload.get("items", [])
    ]


_PARSERS: dict[str, Any] = {
    "rss": _rss,
    "hn": _hn,
    "hf_papers": _hf_papers,
    "hf_models": _hf_models,
    "github": _github,
    "stackexchange": _stackexchange,
}


def default_since(days: int = 14) -> datetime:
    return datetime.now(UTC) - timedelta(days=days)
