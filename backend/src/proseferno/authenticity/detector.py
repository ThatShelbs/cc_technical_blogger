"""AI-generation detection report: 100 = reads as authentic human prose, 0 = almost certainly flagged as AI.

Four parts, each calibrated to the author's own posts:

- the real detector models, run locally once set up (``local_detector``);
- the twin test: can Claude tell passages of the post from the author's real paragraphs (``twin``)? Without own posts,
  a Claude judge reads the post the way a skeptical editor would instead;
- the tell scan (``heuristics``);
- texture: sentence shape compared with the author's (``texture``).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from proseferno.authenticity.heuristics import AuthorProfile, ScanResult, profile_author, scan
from proseferno.authenticity.local_detector import Detector, detector_report, get_detector
from proseferno.authenticity.passages import author_passages
from proseferno.authenticity.texture import TextureReport, author_texture, texture_report
from proseferno.authenticity.twin import twin_test
from proseferno.config import Settings
from proseferno.db import Sample
from proseferno.llm import LLM, LLMError, SystemBlock
from proseferno.llm.base import UsageSink
from proseferno.prompts import raw, render

log = logging.getLogger(__name__)

# How the parts weigh in the score; the weights of parts that did not run are shared out among the others.
# "judge" is the twin test when the author has posts of their own, else the Claude judge.
WEIGHTS = {"detectors": 40, "judge": 30, "scan": 15, "texture": 15}
MAX_FLAGS = 20
BANDS = [
    (80, "human", "Reads as authentic human writing"),
    (60, "mostly_human", "Mostly human, with a few AI tells"),
    (40, "mixed", "Mixed: AI detectors may flag it"),
    (0, "likely_ai", "Highly probable AI generation"),
]


class FlaggedPassage(BaseModel):
    quote: str = Field(description="Text copied exactly from the post, one to three sentences.")
    reason: str = Field(description="The AI tell, in a few words.")
    suggestion: str = Field(description="How the author would say it instead, briefly.")


class AIDetectionJudgement(BaseModel):
    human_score: int = Field(description="0-100. 100 = clearly written by a human; 0 = clearly AI-generated.")
    verdict: str = Field(description="One sentence summary of the judgement.")
    human_signals: list[str] = Field(description="What reads as genuinely human (specific details, voice, lived experience).")
    ai_signals: list[str] = Field(description="Patterns that read as machine-written.")
    flagged_passages: list[FlaggedPassage] = Field(description="Up to eight passages most likely to trip a detector, worst first.")


def band(score: int) -> tuple[str, str]:
    return next((key, label) for floor, key, label in BANDS if score >= floor)


def author_profile(samples: list[Sample], baseline: dict[str, Any] | None) -> AuthorProfile:
    own = [(s.title, s.markdown) for s in samples if s.kind == "own" and s.markdown]
    profile = profile_author([markdown for _, markdown in own], baseline)
    profile.texts = [markdown for _, markdown in own]
    profile.passages = author_passages(own)
    profile.texture = author_texture(profile.texts)
    return profile


def blend(parts: dict[str, int | None]) -> int:
    """Weighted mean of the parts that ran; the weights of the missing ones are shared out among the others."""
    present = {k: v for k, v in parts.items() if v is not None}
    total = sum(WEIGHTS[k] for k in present)
    return round(sum(WEIGHTS[k] * v for k, v in present.items()) / total) if total else 100


def report(
    scan_result: ScanResult,
    judgement: AIDetectionJudgement | None,
    judge_error: str | None = None,
    *,
    texture: TextureReport | None = None,
    twin: dict[str, Any] | None = None,
    detectors: dict[str, Any] | None = None,
    detector_error: str | None = None,
) -> dict[str, Any]:
    judge_score: int | None
    if twin is not None and twin.get("score") is not None:
        judge_score, judge_kind = int(twin["score"]), "twin"
    elif judgement is not None:
        judge_score, judge_kind = max(0, min(100, judgement.human_score)), "judge"
    else:
        judge_score, judge_kind = None, None
    detector_score = detectors.get("score") if detectors else None
    score = blend(
        {
            "detectors": detector_score,
            "judge": judge_score,
            "scan": scan_result.score,
            "texture": texture.score if texture else None,
        }
    )
    key, label = band(score)
    flagged: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(entry: dict[str, Any]) -> None:
        quote = str(entry.get("quote", "")).strip()
        if quote and quote not in seen:
            seen.add(quote)
            flagged.append(entry)

    for entry in (detectors or {}).get("outliers", []):
        add({k: entry[k] for k in ("quote", "reason", "suggestion", "source")})
    for row in (twin or {}).get("pairs", []):
        if row["caught"]:
            reason = row["giveaway"] or "Claude could tell this from your own writing"
            add({"quote": row["quote"], "reason": reason, "suggestion": "", "source": "twin"})
    if judgement is not None:
        for passage in judgement.flagged_passages:
            add({**passage.model_dump(), "source": "judge"})
    for entry in texture.outliers if texture else []:
        add({**entry, "suggestion": "", "source": "texture"})
    for flag in scan_result.flags:
        add(flag.as_dict())
    twin_giveaways = [r["giveaway"] for r in (twin or {}).get("pairs", []) if r["giveaway"]]
    return {
        "score": score,
        "band": key,
        "label": label,
        "scan_score": scan_result.score,
        "judge_score": judge_score,
        "judge_kind": judge_kind,
        "texture_score": texture.score if texture else None,
        "detector_score": detector_score,
        "verdict": judgement.verdict if judgement else _twin_verdict(twin),
        "human_signals": judgement.human_signals if judgement else [],
        "ai_signals": judgement.ai_signals if judgement else twin_giveaways,
        "signals": [s.as_dict() for s in scan_result.signals],
        "texture": texture.as_dict() if texture else None,
        "twin": twin,
        "detectors": detectors,
        "flagged": flagged[:MAX_FLAGS],
        "word_count": scan_result.word_count,
        "judge_error": judge_error,
        "detector_error": detector_error,
        "checked_at": datetime.now(UTC).isoformat(),
    }


def _twin_verdict(twin: dict[str, Any] | None) -> str:
    if not twin or not twin.get("total"):
        return ""
    caught, total = twin["caught"], twin["total"]
    if caught == 0:
        return f"Claude could not tell any of {total} passages from your own writing."
    return f"Claude told {caught} of {total} passages apart from your own writing."


async def run_detectors(
    settings: Settings, markdown: str, profile: AuthorProfile, detector: Detector | Literal["auto"] | None = "auto"
) -> tuple[dict[str, Any] | None, str | None]:
    """The detector models' report, or (None, why) when they are off or failed. Never raises."""
    chosen = get_detector(settings) if detector == "auto" else detector
    if chosen is None:
        return None, None
    try:
        return await detector_report(settings=settings, detector=chosen, markdown=markdown, author_texts=profile.texts), None
    except Exception as exc:  # noqa: BLE001 - the models are a bonus: a failure must never cost the author the post
        log.warning("Detector models failed: %s", exc)
        return None, str(exc)[:500]


async def analyze(
    *,
    llm: LLM,
    settings: Settings,
    markdown: str,
    voice_profile: str,
    profile: AuthorProfile,
    use_judge: bool = True,
    usage: UsageSink | None = None,
    detector: Detector | Literal["auto"] | None = "auto",
) -> dict[str, Any]:
    """Scan, texture, the detector models when set up, and the twin test (or the Claude judge without own posts)."""
    scan_result = scan(markdown, profile)
    texture = texture_report(markdown, profile.texture)
    detectors, detector_error = await run_detectors(settings, markdown, profile, detector)
    twin: dict[str, Any] | None = None
    judgement: AIDetectionJudgement | None = None
    judge_error: str | None = None
    if use_judge:
        try:
            twin = await twin_test(llm=llm, settings=settings, markdown=markdown, passages=profile.passages, usage=usage)
        except LLMError as exc:
            judge_error = str(exc)
        if twin is None and judge_error is None:
            try:
                judgement = await llm.structured(
                    task="ai detection",
                    system=[SystemBlock(raw("detect_system"), cache=True)],
                    prompt=render(
                        "detect", voice_profile=voice_profile or "_No voice profile._", scan=scan_result.tells_text(), post=markdown
                    ),
                    schema=AIDetectionJudgement,
                    effort=settings.effort_detect,
                    usage=usage,
                )
            except LLMError as exc:
                judge_error = str(exc)
    return report(scan_result, judgement, judge_error, texture=texture, twin=twin, detectors=detectors, detector_error=detector_error)
