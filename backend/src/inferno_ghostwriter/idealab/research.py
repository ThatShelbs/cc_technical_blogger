"""The research base: what is happening in the field, kept between brainstorms and added to on request.

Two layers. Collectors (``collect.py``) read free feeds with no model call. Scouts are Claude web searches, one per
beat, each given the collected items for its beat as leads. A digest call then groups everything into trends, and
code keeps only the trends whose links are collected items or search citations.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import Engine
from sqlmodel import Session, col, select

from inferno_ghostwriter.config import Settings
from inferno_ghostwriter.db import AppSetting, IdeaSignal, IdeaTrend, utcnow
from inferno_ghostwriter.idealab.collect import Signal, SignalCollector
from inferno_ghostwriter.idealab.schemas import Trend, TrendDigest
from inferno_ghostwriter.idealab.sources import SourceConfig, load_config, news_source, save_health
from inferno_ghostwriter.jobs import JobContext
from inferno_ghostwriter.llm import LLM, Citation, SystemBlock
from inferno_ghostwriter.prompts import raw, render
from inferno_ghostwriter.writer.references import norm_url

log = logging.getLogger(__name__)

RESEARCH_JOB = "idea_research"
STATE_KEY = "idea_research_state"

Depth = Literal["quick", "standard", "deep"]
DEPTH_FACTOR: dict[str, float] = {"quick": 0.5, "standard": 1.0, "deep": 1.75}

# The base is reused by a brainstorm while it is this fresh.
FRESH_HOURS = 24
SIGNAL_KEEP_DAYS = 45
TREND_KEEP_DAYS = 30
MAX_TRENDS = 40
MAX_DIGEST_SIGNALS = 160
MAX_LEADS = 30
MAX_INDUSTRY_SCOUTS = 6
SCOUTS_AT_ONCE = 3
MAX_SEARCH_HISTORY = 20


class ResearchError(RuntimeError):
    pass


@dataclass
class Beat:
    id: str
    title: str
    instructions: str
    # Signal groups (or source ids) whose items are handed to the scout as leads.
    groups: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()


@dataclass
class ScoutReport:
    beat: Beat
    text: str = ""
    citations: list[Citation] = field(default_factory=list)
    error: str = ""


def _names(names: list[str]) -> str:
    return ", ".join(names) if names else "(none listed)"


def standing_beats(config: SourceConfig) -> list[Beat]:
    """The scouts of a full refresh. Names come from the source catalog, never from here."""
    search_only = "; ".join(config.search_only)
    beats = [
        Beat(
            "launches",
            "Launches and announcements",
            "Find the product launches, model releases, major feature announcements and pricing or policy changes from AI labs, "
            "cloud and data platforms, and the open source tools practitioners use. For each, say what is new and what it "
            "changes for people who build with it. Check these places that have no feed: " + search_only + ".",
            groups=("vendor", "research", "code"),
        ),
        Beat(
            "voices",
            "What notable practitioners are saying",
            "Find the claims, strong opinions and arguments that well-known practitioners are making right now, and who is "
            "disagreeing with them. Start with these people, then look for anyone else whose post is being widely shared: "
            + _names(config.voices)
            + ". Quote the claim briefly and link to where it was made.",
            groups=("creator",),
        ),
        Beat(
            "creators",
            "What leading writers are publishing",
            "Find what the leading technical bloggers, newsletters and publications in this field have published lately. "
            "The key finding is overlap: a subject that several independent writers have each covered in the last few weeks. "
            "Name the subject, list who wrote about it, and say which angle nobody has taken yet.",
            groups=("creator", "community"),
        ),
        Beat(
            "community",
            "What practitioners are asking and arguing about",
            "Find the questions, complaints and debates with the most discussion in practitioner communities: forums, Q&A "
            "sites and discussion boards, including " + search_only + ". Report the recurring question or the disagreement "
            "itself, how many people are engaging, and what a good answer would need to cover.",
            groups=("community",),
        ),
    ]
    for industry in config.industries[:MAX_INDUSTRY_SCOUTS]:
        slug = re.sub(r"[^a-z0-9]+", "_", industry.lower()).strip("_")
        beats.append(
            Beat(
                f"industry_{slug}",
                f"AI and analytics in {industry}",
                f"Find what organisations in {industry} are building, buying, piloting or being regulated on in AI, machine "
                "learning and analytics. The key finding is a pattern: the same kind of project showing up at several "
                "organisations. Name the organisations and the project.",
                source_ids=(f"news_{slug}",),
            )
        )
    return beats


def query_beat(query: str) -> Beat:
    return Beat(
        "search",
        f"The writer's own search: {query}",
        f"The writer asked you to look into this: {query}\n\nFind what is new and what is being said about it: releases, "
        "claims, discussions, who is writing about it, and what is still unanswered.",
        source_ids=("search_news",),
    )


def _lead_lines(signals: list[Signal], beat: Beat) -> str:
    picked = [s for s in signals if s.group in beat.groups or s.source_id in beat.source_ids]
    picked.sort(key=lambda s: (s.engagement, s.published_at or datetime.min.replace(tzinfo=UTC)), reverse=True)
    # No one source crowds out the rest.
    per_source: dict[str, int] = {}
    lines = []
    for signal in picked:
        per_source[signal.source_id] = per_source.get(signal.source_id, 0) + 1
        if per_source[signal.source_id] > 6:
            continue
        date = f" ({signal.published_at.date().isoformat()})" if signal.published_at else ""
        lines.append(f"- {signal.title}{date} [{signal.source_name}] {signal.url}")
        if len(lines) >= MAX_LEADS:
            break
    return "\n".join(lines) or "_Nothing was collected for this beat; rely on search._"


async def run_scouts(
    llm: LLM,
    settings: Settings,
    beats: list[Beat],
    signals: list[Signal],
    *,
    depth: Depth,
    ctx: JobContext | None = None,
    span: tuple[float, float] = (0.15, 0.75),
) -> list[ScoutReport]:
    """Run every scout, a few at a time. A scout that fails is reported, and the others carry on."""
    searches = max(2, round(settings.idea_max_searches * DEPTH_FACTOR[depth]))
    gate = asyncio.Semaphore(SCOUTS_AT_ONCE)
    done = 0

    async def one(beat: Beat) -> ScoutReport:
        nonlocal done
        async with gate:
            try:
                result = await llm.research(
                    system=[SystemBlock(raw("idea_scout_system"))],
                    prompt=render(
                        "idea_scout",
                        today=datetime.now(UTC).date().isoformat(),
                        window_days=settings.idea_window_days,
                        beat=beat.title,
                        instructions=beat.instructions,
                        leads=_lead_lines(signals, beat),
                        max_findings=12,
                    ),
                    effort=settings.effort_idea_research,
                    max_searches=searches,
                    usage=ctx.add_usage if ctx else None,
                )
                report = ScoutReport(beat=beat, text=result.text.strip(), citations=result.citations)
            except Exception as exc:
                log.warning("Idea scout %s failed", beat.id, exc_info=True)
                report = ScoutReport(beat=beat, error=str(exc)[:300])
        done += 1
        if ctx:
            await ctx.progress(span[0] + (span[1] - span[0]) * done / len(beats), f"Scouted: {beat.title}")
        return report

    return list(await asyncio.gather(*(one(beat) for beat in beats)))


# -- digest --------------------------------------------------------------------------------


def norm_label(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", label.lower()).strip()


def checked_trends(digest: TrendDigest, allowed: dict[str, str]) -> list[tuple[Trend, list[dict[str, str]]]]:
    """Keep only trends with at least one real link. ``allowed`` maps normalised URL -> title of a signal or citation."""
    out = []
    seen: set[str] = set()
    for trend in digest.trends:
        label = " ".join(trend.label.split())
        key = norm_label(label)
        if not key or key in seen:
            continue
        evidence: list[dict[str, str]] = []
        for url in trend.evidence_urls:
            normalised = norm_url(url)
            if normalised in allowed and not any(norm_url(e["url"]) == normalised for e in evidence):
                evidence.append({"url": url.strip(), "title": allowed[normalised]})
        if not evidence:
            log.info("Dropped trend with no verifiable link: %s", label)
            continue
        seen.add(key)
        trend.label = label
        out.append((trend, evidence[:5]))
    return out


def _digest_signal_lines(signals: list[IdeaSignal]) -> str:
    ranked = sorted(signals, key=lambda s: (s.engagement, s.fetched_at), reverse=True)
    per_source: dict[str, int] = {}
    lines = []
    for signal in ranked:
        per_source[signal.source_id] = per_source.get(signal.source_id, 0) + 1
        if per_source[signal.source_id] > 12:
            continue
        lines.append(f"{signal.source_name} | {signal.engagement} | {signal.title} | {signal.url}")
        if len(lines) >= MAX_DIGEST_SIGNALS:
            break
    return "\n".join(lines) or "_None._"


async def digest_trends(
    llm: LLM,
    settings: Settings,
    reports: list[ScoutReport],
    signals: list[IdeaSignal],
    existing: list[IdeaTrend],
    *,
    ctx: JobContext | None = None,
) -> list[tuple[Trend, list[dict[str, str]]]]:
    findings = "\n\n".join(f"## {r.beat.title}\n\n{r.text[:7000]}" for r in reports if r.text) or "_The scouts found nothing._"
    citations = {norm_url(c.url): c for r in reports for c in r.citations if c.url}
    allowed = {norm_url(s.url): s.title for s in signals}
    allowed.update({key: c.title or c.url for key, c in citations.items()})
    digest = await llm.structured(
        task="idea research digest",
        system=[SystemBlock(raw("idea_scout_system"))],
        prompt=render(
            "idea_digest",
            today=datetime.now(UTC).date().isoformat(),
            findings=findings,
            citations="\n".join(f"- {c.title or 'Untitled'} | {c.url}" for c in citations.values()) or "_None._",
            signals=_digest_signal_lines(signals),
            existing="\n".join(f"- {t.label}" for t in existing) or "_None yet._",
            max_trends=MAX_TRENDS,
        ),
        schema=TrendDigest,
        effort=settings.effort_idea_research,
        max_tokens=16000,
        usage=ctx.add_usage if ctx else None,
    )
    return checked_trends(digest, allowed)


# -- storage -------------------------------------------------------------------------------


def store_signals(session: Session, signals: list[Signal]) -> int:
    """Add new items by URL; an item seen again keeps its row and takes the higher engagement. Returns how many were new."""
    added = 0
    by_url: dict[str, Signal] = {}
    for signal in signals:
        by_url.setdefault(signal.url, signal)
    known = {row.url: row for row in session.exec(select(IdeaSignal).where(col(IdeaSignal.url).in_(list(by_url))))} if by_url else {}
    for url, signal in by_url.items():
        row = known.get(url)
        if row is None:
            session.add(IdeaSignal(**signal.__dict__))
            added += 1
        elif signal.engagement > row.engagement:
            row.engagement = signal.engagement
            session.add(row)
    session.commit()
    return added


def store_trends(session: Session, trends: list[tuple[Trend, list[dict[str, str]]]]) -> int:
    existing = {norm_label(t.label): t for t in session.exec(select(IdeaTrend))}
    now = utcnow()
    for trend, evidence in trends:
        row = existing.get(norm_label(trend.label))
        if row is None:
            row = IdeaTrend(label=trend.label, first_seen=now)
            merged = evidence
        else:
            have = {norm_url(e["url"]) for e in evidence}
            merged = evidence + [e for e in row.evidence if norm_url(str(e.get("url", ""))) not in have]
        row.kind = trend.kind
        row.summary = trend.summary.strip()
        row.heat = trend.heat
        row.industries = [i.strip() for i in trend.industries if i.strip()][:5]
        row.evidence = merged[:8]
        row.last_seen = now
        session.add(row)
    session.commit()
    return len(trends)


def prune(session: Session) -> None:
    now = utcnow()
    for signal in session.exec(select(IdeaSignal).where(IdeaSignal.fetched_at < now - timedelta(days=SIGNAL_KEEP_DAYS))):
        session.delete(signal)
    for trend in session.exec(select(IdeaTrend).where(IdeaTrend.last_seen < now - timedelta(days=TREND_KEEP_DAYS))):
        session.delete(trend)
    session.commit()


def load_state(session: Session) -> dict[str, Any]:
    row = session.get(AppSetting, STATE_KEY)
    return dict(row.value) if row is not None and isinstance(row.value, dict) else {}


def _save_state(session: Session, **changes: Any) -> None:
    state = {**load_state(session), **changes}
    row = session.get(AppSetting, STATE_KEY) or AppSetting(key=STATE_KEY)
    row.value = state
    session.add(row)
    session.commit()


def is_fresh(session: Session, hours: int = FRESH_HOURS) -> bool:
    """True when a full refresh ran recently and left trends to work from."""
    stamp = load_state(session).get("last_refresh")
    if not stamp or session.exec(select(IdeaTrend)).first() is None:
        return False
    try:
        return datetime.fromisoformat(stamp) > utcnow() - timedelta(hours=hours)
    except ValueError:
        return False


def current_trends(session: Session, limit: int = 60) -> list[IdeaTrend]:
    return list(session.exec(select(IdeaTrend).order_by(col(IdeaTrend.last_seen).desc(), col(IdeaTrend.heat).desc()).limit(limit)))


# -- the job -------------------------------------------------------------------------------


async def run_research(
    *,
    engine: Engine,
    llm: LLM,
    settings: Settings,
    collector: SignalCollector,
    ctx: JobContext | None = None,
    query: str | None = None,
    depth: Depth = "standard",
    span: tuple[float, float] = (0.0, 1.0),
) -> dict[str, Any]:
    """A full refresh of the research base, or (with ``query``) one more search added to it."""

    async def report(fraction: float, message: str) -> None:
        if ctx:
            await ctx.progress(span[0] + (span[1] - span[0]) * fraction, message)

    query = " ".join((query or "").split())[:300]
    with Session(engine) as session:
        config = load_config(session)
    since = datetime.now(UTC) - timedelta(days=settings.idea_window_days)
    if query:
        sources = [news_source(query, source_id="search_news", name=f"News: {query}", group="search")]
        beats = [query_beat(query)]
    else:
        sources = config.active()
        beats = standing_beats(config)

    await report(0.02, f"Reading {len(sources)} feeds" if not query else "Reading the news")
    collected, health = await collector.collect(sources, since=since)
    for signal in collected:
        signal.query = query
    with Session(engine) as session:
        if not query:
            save_health(session, health)
        new_signals = store_signals(session, collected)

    await report(0.15, f"Sending out {len(beats)} scouts" if len(beats) > 1 else "Searching the web")
    reports = await run_scouts(
        llm,
        settings,
        beats,
        collected,
        depth=depth,
        ctx=ctx,
        span=(span[0] + (span[1] - span[0]) * 0.15, span[0] + (span[1] - span[0]) * 0.75),
    )
    failed = [r for r in reports if r.error]
    if len(failed) == len(reports) and not collected:
        raise ResearchError(f"The research could not run: {failed[0].error}")

    cited = [
        Signal(
            source_id="search",
            source_name="Web search",
            group="search",
            url=c.url,
            title=c.title or c.url,
            summary=c.cited_text[:300],
            query=query,
        )
        for r in reports
        for c in r.citations
        if c.url.startswith(("http://", "https://"))
    ]
    with Session(engine) as session:
        new_signals += store_signals(session, cited)
        if query:
            # One more search is digested with what it found, not the whole base again.
            urls = [s.url for s in collected + cited]
            pool = list(session.exec(select(IdeaSignal).where(col(IdeaSignal.url).in_(urls)))) if urls else []
        else:
            pool = list(
                session.exec(select(IdeaSignal).where(IdeaSignal.fetched_at >= utcnow() - timedelta(days=settings.idea_window_days)))
            )
        existing = current_trends(session)

    await report(0.78, "Grouping what was found into trends")
    trends = await digest_trends(llm, settings, reports, pool, existing, ctx=ctx)
    with Session(engine) as session:
        store_trends(session, trends)
        prune(session)
        now = utcnow().isoformat()
        if query:
            searches = [{"query": query, "at": now, "trends": len(trends)}, *load_state(session).get("searches", [])]
            _save_state(session, searches=searches[:MAX_SEARCH_HISTORY])
        else:
            _save_state(session, last_refresh=now, depth=depth, scouts_failed=[r.beat.title for r in failed])
    await report(1.0, "Research ready")
    return {"signals": new_signals, "trends": len(trends), "scouts_failed": [r.beat.title for r in failed], "query": query}
