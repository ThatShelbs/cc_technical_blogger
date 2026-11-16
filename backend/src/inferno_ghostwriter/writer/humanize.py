"""Humanize: rewrite only what reads as machine-written, measured by the detectors, the twin test and texture.

After the editor's pass the post is checked (``authenticity.analyze``). The sentences the detector models score
above the author's own range, the passages Claude could tell apart from the author's real paragraphs (with what gave
them away), and the texture outliers become targets. Claude returns surgical find/replace edits for those targets
only, written next to the author's closest real paragraphs; the post is checked again and the better version is kept.
Rounds are bounded by ``Settings.humanize_rounds``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from inferno_ghostwriter.authenticity import AuthorProfile, analyze
from inferno_ghostwriter.authenticity.local_detector import Detector, detector_input, get_detector
from inferno_ghostwriter.authenticity.passages import Passage, anchor_passages, format_anchors
from inferno_ghostwriter.config import Settings
from inferno_ghostwriter.llm import LLM, LLMError, SystemBlock
from inferno_ghostwriter.llm.base import UsageSink
from inferno_ghostwriter.prompts import render
from inferno_ghostwriter.writer.schemas import PostEdits

log = logging.getLogger(__name__)

MAX_TARGETS = 10
GOOD_ENOUGH = 88  # no humanize round when the post already scores this well
TARGET_SOURCES = ("detector", "twin", "judge", "texture", "scan")


def targets(report: dict[str, Any], limit: int = MAX_TARGETS) -> list[dict[str, str]]:
    """The flagged passages worth rewriting, most telling first (detector models, then the twin test, then the rest)."""
    flagged = [f for f in report.get("flagged", []) if f.get("source") in TARGET_SOURCES and str(f.get("quote", "")).strip()]
    flagged.sort(key=lambda f: TARGET_SOURCES.index(f["source"]))
    return [{"quote": str(f["quote"]), "why": str(f.get("reason", "")), "source": str(f["source"])} for f in flagged[:limit]]


def format_targets(found: list[dict[str, str]], passages: list[Passage]) -> str:
    blocks: list[str] = []
    used: set[str] = set()
    for number, target in enumerate(found, 1):
        anchors = anchor_passages(target["quote"], passages, k=1, exclude=used)
        used.update(a.text for a in anchors)
        anchor = f"\n{format_anchors(anchors)}" if anchors else ""
        blocks.append(f'<target number="{number}" why="{target["why"]}">\n{target["quote"]}\n</target>{anchor}')
    return "\n\n".join(blocks)


async def humanize_post(
    *,
    llm: LLM,
    settings: Settings,
    system: list[SystemBlock],
    markdown: str,
    voice_profile: str,
    profile: AuthorProfile,
    finish: Callable[[str], str],
    usage: UsageSink | None = None,
    on_round: Callable[[int], Any] | None = None,
) -> tuple[str, dict[str, Any] | None]:
    """Up to ``humanize_rounds`` rounds of targeted edits; returns the best text and its report (None if never checked)."""
    from inferno_ghostwriter.writer.tweak import apply_edits  # tweak imports the pipeline, which imports this module

    rounds = max(0, settings.humanize_rounds)
    if rounds == 0:
        return markdown, None
    best = markdown
    best_report = await analyze(
        llm=llm,
        settings=settings,
        markdown=best,
        voice_profile=voice_profile,
        profile=profile,
        use_judge=settings.ai_detection,
        usage=usage,
    )
    for round_number in range(rounds):
        found = targets(best_report)
        if not found or best_report["score"] >= GOOD_ENOUGH:
            break
        if on_round is not None:
            await on_round(round_number)
        try:
            edits = await llm.structured(
                task="humanize",
                system=system,
                prompt=render("humanize", targets=format_targets(found, profile.passages), post=best),
                schema=PostEdits,
                effort=settings.effort_critique,
                usage=usage,
            )
        except LLMError as exc:
            log.warning("Humanize round failed; keeping the current text: %s", exc)
            break
        candidate, applied, _skipped = apply_edits(best, edits.edits)
        if not applied:
            break
        candidate = finish(candidate)
        candidate_report = await analyze(
            llm=llm,
            settings=settings,
            markdown=candidate,
            voice_profile=voice_profile,
            profile=profile,
            use_judge=settings.ai_detection,
            usage=usage,
        )
        if candidate_report["score"] < best_report["score"]:
            break  # the edit made it read less like the author: keep what we had
        best, best_report = candidate, candidate_report
    return best, best_report


async def machine_scores(
    *, llm: LLM, settings: Settings, profile: AuthorProfile, passages: list[str], detector: Detector | None = None
) -> list[float] | None:
    """How machine-like each passage reads (higher = more machine), for keeping the better of two versions.

    Uses the detector models when set up; otherwise the twin test, pairing each passage with the author's closest
    paragraph. None when neither can run.
    """
    chosen = detector if detector is not None else get_detector(settings)
    if chosen is not None:
        try:
            results = await chosen.score([detector_input(p) for p in passages])
            out = []
            for result in results:
                curvature = (result.get("curvature") or {}).get("score")
                classifier = (result.get("classifier") or {}).get("score")
                out.append((curvature or 0.0) + 4 * (classifier or 0.0))
            return out
        except Exception as exc:  # noqa: BLE001 - fall back to the twin test
            log.warning("Detector models failed while comparing passages: %s", exc)
    if not profile.passages or not settings.ai_detection:
        return None
    from inferno_ghostwriter.authenticity.twin import Pair, TwinVerdicts, format_pairs, pair_score
    from inferno_ghostwriter.prompts import raw

    pairs = []
    for number, text in enumerate(passages, 1):
        anchors = anchor_passages(text, profile.passages, k=1, near_words=len(text.split()))
        if not anchors:
            return None
        pairs.append(Pair(number, text, anchors[0], anchors[0].role, number % 2 == 1))
    try:
        verdicts = await llm.structured(
            task="twin test",
            system=[SystemBlock(raw("twin_system"), cache=True)],
            prompt=render("twin", pairs=format_pairs(pairs), count=len(pairs)),
            schema=TwinVerdicts,
            effort=settings.effort_twin,
        )
    except LLMError:
        return None
    by_number = {v.pair: v for v in verdicts.verdicts}
    return [float(pair_score(pair, by_number.get(pair.number))[2]) for pair in pairs]
