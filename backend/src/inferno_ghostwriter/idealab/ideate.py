"""Turn the research base and the author's portfolio into ranked ideas.

Each source approach writes its ideas in batches of ten (about 30% more than needed), code removes duplicates and
anything too close to an existing post, one ranking call scores and themes what is left, and code keeps the best N
while holding the mix between approaches.
"""

from __future__ import annotations

import asyncio
import logging
import math
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from inferno_ghostwriter.config import Settings
from inferno_ghostwriter.db import IdeaTrend
from inferno_ghostwriter.idealab.portfolio import Portfolio, format_portfolio
from inferno_ghostwriter.idealab.research import norm_label
from inferno_ghostwriter.idealab.schemas import IdeaBatch, IdeaDraft, IdeaRanking
from inferno_ghostwriter.jobs import JobContext
from inferno_ghostwriter.llm import LLM, SystemBlock
from inferno_ghostwriter.prompts import raw, render
from inferno_ghostwriter.writer.formulas import ARTICLE_TYPES, AUTO

log = logging.getLogger(__name__)

MODES: dict[str, int] = {"light": 10, "medium": 25, "heavy": 50}
CORE: tuple[str, ...] = ("emerging", "builder", "expander")
EXTRAS: tuple[str, ...] = ("reader_questions", "counter_take", "sparks")
APPROACHES: tuple[str, ...] = CORE + EXTRAS
# Emerging / Builder / Expander for each mode.
CORE_MIX: dict[str, tuple[int, int, int]] = {"light": (5, 3, 2), "medium": (12, 7, 6), "heavy": (24, 13, 13)}
# Earlier brainstorm titles named in each prompt; code checks against all of them anyway.
EARLIER_IN_PROMPT = 40

APPROACH_LABELS: dict[str, str] = {
    "emerging": "Live and Emerging",
    "builder": "Portfolio Builder",
    "expander": "Portfolio Expander",
    "reader_questions": "Reader Questions",
    "counter_take": "Counter-take",
    "sparks": "Your Sparks",
    # Added by hand to the bank, not by a brainstorm.
    "own": "Your own idea",
}

GUIDES: dict[str, str] = {
    "emerging": (
        "Ideas that come from what is happening in the field right now: a release, an industry pattern, a subject many "
        "writers are covering. Every idea must rest on at least one trend from the material (copy its label into "
        "`trend_labels`). Do not summarise the news: give the author's take on it. What does it change for practitioners, "
        "what did the announcement leave out, what should a team do on Monday? Where many writers are already covering a "
        "subject, find the angle they have not taken. Use the tag `calendar` for an idea tied to a dated event."
    ),
    "builder": (
        "Ideas that build on the portfolio: the next post a reader of the author's recent work would want. A sequel, a "
        "deeper cut into one section of an earlier post, the practical follow-up to an opinion piece, an update now that "
        "things have changed. Posts that did well are the best ones to follow: tag those ideas `sequel`. Copy the title "
        "of the post each idea follows into `builds_on`. Stay close to the subjects and article types the author already uses."
    ),
    "expander": (
        "Ideas that widen the portfolio into ground the author has not covered lately. Use the measured gaps: topics not "
        "covered and article types not used. If the recent work is mostly opinion, propose a tutorial or a project "
        "walkthrough; if it is mostly how-to, propose a point of view. Each idea must still be one the author is credible "
        "to write: connect the new ground to something they clearly know. Say in `angle` which gap it fills."
    ),
    "reader_questions": (
        "Ideas that answer what practitioners keep asking. Every idea must rest on a question or discussion from the "
        "material (copy its label into `trend_labels`). The post is the answer the thread never got: complete, opinionated "
        "where the author has a view, and useful to someone who arrives by search a year from now."
    ),
    "counter_take": (
        "Ideas that push back on a claim that is spreading. Every idea must rest on a claim from the material (copy its "
        "label into `trend_labels`). State the claim fairly, then say where the author would disagree, add a condition, or "
        "show what it misses, based on their portfolio and what has worked for them. Disagree with the argument, never "
        "the person. If the author would plainly agree with a claim, skip it."
    ),
    "sparks": (
        "The author dropped in their own half-ideas, links or notes (the material). Develop each one into a full idea: find "
        "the post inside it, give it an angle and an outline. Keep the author's intent; do not replace their idea with a "
        "different one. If a spark connects to a trend, copy that trend's label into `trend_labels`."
    ),
}

BATCH = 10
OVERSHOOT = 1.3
WEIGHTS: dict[str, float] = {"timeliness": 0.25, "demand": 0.25, "fit": 0.2, "differentiation": 0.2, "effort": 0.1}
SIMILAR = 0.6
_STOP_WORDS = (
    "a an and are as at be but by can do for from how i in is it its my of on or so that the this to we what when "
    "why with you your not don t s vs via into than then them they our"
)
_STOP = frozenset(_STOP_WORDS.split())
# Which trend kinds feed which approach. Claims and questions feed Emerging too when their own approach is off.
TREND_KINDS: dict[str, tuple[str, ...]] = {
    "emerging": ("launch", "industry_pattern", "creator_wave"),
    "reader_questions": ("question",),
    "counter_take": ("claim",),
}


@dataclass
class Candidate:
    approach: str
    draft: IdeaDraft
    evidence: list[dict[str, Any]] = field(default_factory=list)
    theme: str = ""
    scores: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0


# -- the mix -------------------------------------------------------------------------------


def plan_mix(mode: str, extras: list[str], available: dict[str, bool]) -> tuple[dict[str, int], list[str]]:
    """How many ideas each approach is asked for, and notes about approaches that had nothing to work from.

    The three core approaches follow ``CORE_MIX``. Each extra that is switched on takes a tenth of the total (at
    least one), taken from the core approaches largest first. An approach with no material hands its share to
    Emerging, or to Expander when there is no research either (Expander always has the topic catalog).
    """
    total = MODES[mode]
    mix = dict(zip(CORE, CORE_MIX[mode], strict=True))
    for extra in (e for e in EXTRAS if e in extras):
        share = max(1, total // 10)
        mix[extra] = share
        for _ in range(share):
            # On a tie the later approach gives way, so Live and Emerging stays the largest share.
            biggest = max(CORE, key=lambda a: (mix[a], CORE.index(a)))
            mix[biggest] -= 1
    notes = []
    fallback = "emerging" if available.get("emerging") else "expander"
    for approach in list(mix):
        if available.get(approach, True) or approach == fallback:
            continue
        if mix[approach]:
            notes.append(_NO_MATERIAL[approach])
        mix[fallback] = mix.get(fallback, 0) + mix.pop(approach)
    return {a: n for a, n in mix.items() if n > 0}, notes


_NO_MATERIAL: dict[str, str] = {
    "emerging": "There was no live research to work from, so Live and Emerging ideas were replaced with portfolio ideas. "
    "Refresh the research and try again.",
    "builder": "This persona has no posts or samples yet, so Portfolio Builder ideas were replaced.",
    "reader_questions": "The research found no reader questions this time, so those ideas were replaced.",
    "counter_take": "The research found no claims to push back on this time, so those ideas were replaced.",
    "sparks": "No sparks were given, so those ideas were replaced.",
}


def availability(trends: list[IdeaTrend], portfolio: Portfolio, sparks: str) -> dict[str, bool]:
    kinds = {t.kind for t in trends}
    return {
        "emerging": bool(trends),
        "builder": bool(portfolio.items),
        "expander": True,
        "reader_questions": "question" in kinds,
        "counter_take": "claim" in kinds,
        "sparks": bool(sparks.strip()),
    }


# -- duplicates ----------------------------------------------------------------------------


def title_tokens(title: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", title.lower()) if w not in _STOP and len(w) > 1}


def too_similar(a: set[str], b: set[str]) -> bool:
    if not a or not b:
        return False
    shared = len(a & b)
    if shared / len(a | b) >= SIMILAR:
        return True
    # One title contained in the other ("X" and "X: a practical guide").
    return shared >= 3 and shared == min(len(a), len(b))


def dedupe(candidates: list[Candidate], against: list[str]) -> list[Candidate]:
    """Drop ideas whose title repeats an earlier candidate, an existing post, or an idea the author already saw."""
    seen = [title_tokens(t) for t in against]
    kept = []
    for candidate in candidates:
        tokens = title_tokens(candidate.draft.title)
        if not tokens or any(too_similar(tokens, other) for other in seen):
            continue
        seen.append(tokens)
        kept.append(candidate)
    return kept


# -- prompts -------------------------------------------------------------------------------


def _trend_lines(trends: list[IdeaTrend], limit: int = 30) -> str:
    ranked = sorted(trends, key=lambda t: t.heat, reverse=True)[:limit]
    lines = []
    for trend in ranked:
        where = f" Industries: {', '.join(trend.industries)}." if trend.industries else ""
        lines.append(f"- [{trend.kind}, heat {trend.heat}/10] {trend.label}: {trend.summary}{where}")
    return "\n".join(lines) or "_No trends on file._"


def material_for(approach: str, trends: list[IdeaTrend], portfolio: Portfolio, sparks: str, mix: dict[str, int]) -> str:
    if approach in TREND_KINDS:
        kinds = set(TREND_KINDS[approach])
        if approach == "emerging":
            # With their own approach off, claims and questions are still news worth an idea.
            kinds |= {k for a, ks in TREND_KINDS.items() if a != "emerging" and a not in mix for k in ks}
        picked = [t for t in trends if t.kind in kinds] or trends
        return "## Trends\n\n" + _trend_lines(picked)
    if approach == "sparks":
        hooks = "\n\n## Trends that may connect\n\n" + _trend_lines(trends, 15) if trends else ""
        return "## The author's sparks\n\n" + sparks.strip()[:6000] + hooks
    if approach == "expander" and trends:
        return (
            "The portfolio below, and its measured gaps, are the material.\n\n"
            "## Timely hooks (optional: use one only if it fits a gap)\n\n" + _trend_lines(trends, 12)
        )
    return "The portfolio below is the material."


def article_type_lines() -> str:
    return "\n".join(f"- `{kind.id}`: {kind.label}. {kind.summary}" for kind in ARTICLE_TYPES)


def author_blocks(author: str) -> list[SystemBlock]:
    """The stable system prefix shared by every idea call in a session, cached after the author block."""
    return [SystemBlock(raw("idea_system")), SystemBlock("# The author\n\n" + (author.strip() or "_No voice profile yet._"), cache=True)]


# -- generation ----------------------------------------------------------------------------


def _attach(approach: str, draft: IdeaDraft, trends: dict[str, IdeaTrend], portfolio_titles: dict[str, str]) -> Candidate | None:
    """Validate one draft against what it claims to rest on. Returns None when a trend-based idea has no real trend."""
    draft.title = " ".join(draft.title.split()).strip(' "')
    draft.outline = [" ".join(b.split()).lstrip("-*• ").strip() for b in draft.outline if b.strip()][:8]
    if not draft.title or len(draft.outline) < 2:
        return None
    matched = [trends[key] for label in draft.trend_labels if (key := norm_label(label)) in trends]
    draft.trend_labels = [t.label for t in matched]
    if approach in TREND_KINDS and not matched:
        return None
    draft.builds_on = portfolio_titles.get(draft.builds_on.strip().lower(), "")
    if draft.article_type not in {kind.id for kind in ARTICLE_TYPES}:
        draft.article_type = AUTO
    draft.tags = [t.strip().lower()[:24] for t in draft.tags if t.strip()][:3]
    evidence: list[dict[str, Any]] = []
    for trend in matched:
        for link in trend.evidence:
            if link.get("url") and all(link["url"] != e["url"] for e in evidence):
                evidence.append({"url": link["url"], "title": link.get("title") or link["url"]})
    return Candidate(approach=approach, draft=draft, evidence=evidence[:6])


@dataclass
class IdeaContext:
    """Everything a brainstorm needs, loaded once."""

    author: str
    portfolio: Portfolio
    trends: list[IdeaTrend]
    focus: str = ""
    sparks: str = ""
    liked: list[str] = field(default_factory=list)
    passed: list[str] = field(default_factory=list)
    # Every other idea already on file for the author (earlier brainstorms, the saved bank), newest first.
    earlier: list[str] = field(default_factory=list)

    def known(self) -> list[str]:
        """Titles no new idea may repeat: the portfolio and every idea already on file."""
        return self.portfolio.titles() + self.liked + self.passed + self.earlier

    def feedback(self) -> str:
        lines = []
        if self.liked:
            lines.append(
                "Saved or written (more like these, but never the same idea again): " + "; ".join(f'"{t}"' for t in self.liked[:15])
            )
        if self.passed:
            lines.append(
                "Passed on (do not propose these again, and take the hint about what they do not want): "
                + "; ".join(f'"{t}"' for t in self.passed[:15])
            )
        if self.earlier:
            lines.append(
                "Already proposed in earlier brainstorms (do not repeat these or close variants): "
                + "; ".join(f'"{t}"' for t in self.earlier[:EARLIER_IN_PROMPT])
            )
        return "\n".join(lines) or "_Nothing yet._"


async def _write_batch(
    llm: LLM,
    settings: Settings,
    context: IdeaContext,
    approach: str,
    count: int,
    taken: list[str],
    mix: dict[str, int],
    ctx: JobContext | None,
) -> list[Candidate]:
    batch = await llm.structured(
        task=f"ideas {approach}",
        system=author_blocks(context.author),
        prompt=render(
            "idea_batch",
            today=datetime.now(UTC).date().isoformat(),
            approach=approach,
            guide=GUIDES[approach],
            material=material_for(approach, context.trends, context.portfolio, context.sparks, mix),
            portfolio=format_portfolio(context.portfolio),
            focus=context.focus.strip() or "_Nothing specific: the best ideas across the board._",
            feedback=context.feedback(),
            taken="\n".join(f"- {t}" for t in taken) or "_None yet._",
            article_types=article_type_lines(),
            count=count,
        ),
        schema=IdeaBatch,
        effort=settings.effort_idea_ideas,
        max_tokens=16000,
        usage=ctx.add_usage if ctx else None,
    )
    trends = {norm_label(t.label): t for t in context.trends}
    titles = {t.lower(): t for t in context.portfolio.titles()}
    out = []
    for draft in batch.ideas:
        candidate = _attach(approach, draft, trends, titles)
        if candidate is not None:
            out.append(candidate)
    return out


async def _write_approach(
    llm: LLM,
    settings: Settings,
    context: IdeaContext,
    approach: str,
    want: int,
    taken: list[str],
    mix: dict[str, int],
    ctx: JobContext | None,
) -> list[Candidate]:
    """Batches run one after another so each sees the titles before it. A failed batch ends the approach with what it has."""
    found: list[Candidate] = []
    seen = list(taken)
    while len(found) < want:
        size = min(BATCH, want - len(found))
        try:
            batch = await _write_batch(llm, settings, context, approach, size, seen, mix, ctx)
        except Exception:
            log.warning("Idea batch failed for %s", approach, exc_info=True)
            break
        if not batch:
            break
        found.extend(batch)
        seen.extend(c.draft.title for c in batch)
    return found


# -- ranking -------------------------------------------------------------------------------


def overall(scores: dict[str, Any]) -> float:
    return round(sum(float(scores.get(key, 5)) * weight for key, weight in WEIGHTS.items()), 2)


async def rank(llm: LLM, settings: Settings, context: IdeaContext, candidates: list[Candidate], ctx: JobContext | None) -> None:
    """Score and theme every candidate in place. If the ranking call fails, ideas keep neutral scores and their order."""
    lines = "\n".join(
        f"[{i}] ({APPROACH_LABELS[c.approach]}, {c.draft.shelf_life}) {c.draft.title} | {c.draft.angle} | {c.draft.why_now}"
        for i, c in enumerate(candidates, start=1)
    )
    by_index: dict[int, Any] = {}
    try:
        ranking = await llm.structured(
            task="idea ranking",
            system=author_blocks(context.author),
            prompt=render(
                "idea_rank",
                today=datetime.now(UTC).date().isoformat(),
                portfolio=format_portfolio(context.portfolio, limit=25),
                focus=context.focus.strip() or "_Nothing specific._",
                ideas=lines,
            ),
            schema=IdeaRanking,
            effort=settings.effort_idea_rank,
            max_tokens=16000,
            usage=ctx.add_usage if ctx else None,
        )
        by_index = {item.index: item for item in ranking.items}
    except Exception:
        log.warning("Idea ranking failed; keeping neutral scores", exc_info=True)
    for i, candidate in enumerate(candidates, start=1):
        item = by_index.get(i)
        if item is None:
            candidate.scores = {key: 5 for key in WEIGHTS} | {"note": ""}
            candidate.theme = candidate.theme or "Other"
        else:
            candidate.scores = {key: getattr(item, key) for key in WEIGHTS} | {"note": item.note.strip()}
            candidate.theme = " ".join(item.theme.split())[:40] or "Other"
        # Earlier candidates win ties: each approach lists its best first.
        candidate.score = overall(candidate.scores) - i * 1e-4


def select(candidates: list[Candidate], mix: dict[str, int]) -> list[Candidate]:
    """The best of each approach up to its share, topped up from the rest, best first."""
    ranked = sorted(candidates, key=lambda c: c.score, reverse=True)
    chosen: list[Candidate] = []
    for approach, share in mix.items():
        chosen.extend([c for c in ranked if c.approach == approach][:share])
    total = sum(mix.values())
    spare = [c for c in ranked if all(c is not picked for picked in chosen)]
    chosen.extend(spare[: max(0, total - len(chosen))])
    return sorted(chosen, key=lambda c: c.score, reverse=True)[:total]


# -- the whole run -------------------------------------------------------------------------


async def brainstorm(
    llm: LLM,
    settings: Settings,
    context: IdeaContext,
    mix: dict[str, int],
    *,
    ctx: JobContext | None = None,
    span: tuple[float, float] = (0.0, 1.0),
) -> list[Candidate]:
    async def report(fraction: float, message: str) -> None:
        if ctx:
            await ctx.progress(span[0] + (span[1] - span[0]) * fraction, message)

    against = context.known()
    total = sum(mix.values())
    await report(0.02, f"Writing {total} ideas")
    done = 0

    async def approach_ideas(approach: str, share: int) -> list[Candidate]:
        nonlocal done
        found = await _write_approach(llm, settings, context, approach, math.ceil(share * OVERSHOOT) + 1, [], mix, ctx)
        done += 1
        await report(0.05 + 0.6 * done / len(mix), f"{APPROACH_LABELS[approach]}: {len(found)} ideas drafted")
        return found

    drafted = await asyncio.gather(*(approach_ideas(a, n) for a, n in mix.items()))
    candidates = dedupe([c for found in drafted for c in found], against)

    # One more batch for any approach that duplicates left short of its share.
    short = {a: n - sum(1 for c in candidates if c.approach == a) for a, n in mix.items()}
    short = {a: n for a, n in short.items() if n > 0}
    if short:
        await report(0.7, "Replacing duplicates")
        taken = [c.draft.title for c in candidates]
        more = await asyncio.gather(*(_write_approach(llm, settings, context, a, n + 2, taken, mix, ctx) for a, n in short.items()))
        candidates = dedupe(candidates + [c for found in more for c in found], against)

    if not candidates:
        return []
    await report(0.8, f"Ranking {len(candidates)} ideas")
    await rank(llm, settings, context, candidates, ctx)
    await report(1.0, "Ideas ready")
    return select(candidates, mix)
