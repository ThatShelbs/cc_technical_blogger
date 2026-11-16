"""What the author has written: a snapshot measured in code, with no model call.

Posts made in the app carry dates, stages and outcomes; the persona's own uploaded samples carry neither, so they
count as the older portfolio. Topic and article type are read the same way the writer reads them.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from sqlmodel import Session, col, select

from inferno_ghostwriter.db import Project, Sample
from inferno_ghostwriter.writer.dials import TOPICS, classify_topic
from inferno_ghostwriter.writer.formulas import ARTICLE_TYPES, AUTO, detect_article_type

RECENT_POSTS = 8
WINNING = ("good", "viral")


@dataclass
class PortfolioItem:
    title: str
    topic: str
    article_type: str
    # post | sample
    source: str
    stage: str = ""
    outcome: str | None = None
    date: datetime | None = None
    summary: str = ""


@dataclass
class Portfolio:
    items: list[PortfolioItem] = field(default_factory=list)

    @property
    def posts(self) -> list[PortfolioItem]:
        return [i for i in self.items if i.source == "post"]

    @property
    def recent(self) -> list[PortfolioItem]:
        """The latest posts; with too few posts, samples fill in as older work."""
        posts = sorted(self.posts, key=lambda i: i.date or datetime.min, reverse=True)[:RECENT_POSTS]
        samples = [i for i in self.items if i.source == "sample"]
        return posts + samples[: max(0, RECENT_POSTS - len(posts))]

    @property
    def winners(self) -> list[PortfolioItem]:
        return [i for i in self.posts if i.outcome in WINNING]

    def titles(self) -> list[str]:
        return [i.title for i in self.items if i.title]

    def topic_counts(self, items: list[PortfolioItem] | None = None) -> Counter[str]:
        return Counter(i.topic for i in (self.items if items is None else items))

    def type_counts(self, items: list[PortfolioItem] | None = None) -> Counter[str]:
        return Counter(i.article_type for i in (self.items if items is None else items) if i.article_type != AUTO)

    def unused_topics(self) -> list[str]:
        """Topics the author has not touched lately (or ever), least used first."""
        recent, overall = self.topic_counts(self.recent), self.topic_counts()
        return sorted((t for t in TOPICS if recent[t] == 0), key=lambda t: overall[t])

    def unused_types(self) -> list[str]:
        """Article type labels missing from the recent work."""
        recent = self.type_counts(self.recent)
        return [kind.label for kind in ARTICLE_TYPES if recent[kind.id] == 0]


def _type_of(dial: object, text: str) -> str:
    chosen = str(dial or "")
    known = {kind.id for kind in ARTICLE_TYPES}
    return chosen if chosen in known else detect_article_type(text)


def snapshot(session: Session, persona_id: int) -> Portfolio:
    items = []
    projects = session.exec(
        select(Project).where(Project.persona_id == persona_id, col(Project.variant).is_(None)).order_by(col(Project.created_at).desc())
    )
    for project in projects:
        if not project.markdown.strip():
            continue
        text = f"{project.title}\n{project.prompt}"
        items.append(
            PortfolioItem(
                title=project.title.strip(),
                topic=str((project.dials or {}).get("topic") or classify_topic(text)),
                article_type=_type_of((project.dials or {}).get("article_type"), text),
                source="post",
                stage=project.stage,
                outcome=project.outcome,
                date=project.published_at or project.created_at,
                summary=project.subtitle.strip(),
            )
        )
    for sample in session.exec(select(Sample).where(Sample.persona_id == persona_id, Sample.kind == "own")):
        analysis = sample.analysis or {}
        summary = str(analysis.get("summary") or sample.subtitle or "").strip()
        text = f"{sample.title}\n{summary}\n{analysis.get('topic') or ''}"
        items.append(
            PortfolioItem(
                title=(sample.title or sample.source_name).strip(),
                topic=classify_topic(text),
                article_type=detect_article_type(text),
                source="sample",
                summary=summary,
            )
        )
    return Portfolio(items=items)


def _type_label(type_id: str) -> str:
    return next((kind.label for kind in ARTICLE_TYPES if kind.id == type_id), "")


def format_portfolio(portfolio: Portfolio, limit: int = 40) -> str:
    """The portfolio as prompt text: the work, what it leans on, what did well, and what is missing."""
    if not portfolio.items:
        return "_The author has no posts or writing samples on file yet._"
    lines = ["## Posts and samples (newest posts first, then older samples)"]
    for item in portfolio.items[:limit]:
        bits = [item.topic]
        if label := _type_label(item.article_type):
            bits.append(label)
        if item.source == "post":
            bits.append(f"{item.stage}{f', did {item.outcome}' if item.outcome else ''}")
            if item.date:
                bits.append(item.date.date().isoformat())
        else:
            bits.append("older sample")
        summary = f": {item.summary[:160]}" if item.summary else ""
        lines.append(f'- "{item.title}" ({"; ".join(bits)}){summary}')
    topics = ", ".join(f"{topic} x{n}" for topic, n in portfolio.topic_counts().most_common())
    lines += ["", f"## Topic mix\n{topics}"]
    if types := portfolio.type_counts():
        lines += ["", "## Article type mix\n" + ", ".join(f"{_type_label(t) or t} x{n}" for t, n in types.most_common())]
    if portfolio.winners:
        lines += ["", "## Posts that did well\n" + "\n".join(f'- "{w.title}" ({w.outcome})' for w in portfolio.winners)]
    gaps = []
    if unused := portfolio.unused_topics():
        gaps.append("Topics not covered lately: " + ", ".join(unused))
    if unused_types := portfolio.unused_types():
        gaps.append("Article types not used lately: " + ", ".join(unused_types))
    if gaps:
        lines += ["", "## Gaps (measured)\n" + "\n".join(f"- {g}" for g in gaps)]
    return "\n".join(lines)
