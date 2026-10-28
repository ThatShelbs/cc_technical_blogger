"""AI-generation detection report: 100 = reads as authentic human prose, 0 = almost certainly flagged as AI.

Combines the deterministic scan (calibrated to the author's own posts) with a Claude
judge that reads the post the way an AI-text detector or a skeptical editor would.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from proseferno.authenticity.heuristics import AuthorProfile, ScanResult, profile_author, scan
from proseferno.config import Settings
from proseferno.db import Sample
from proseferno.llm import LLM, LLMError, SystemBlock
from proseferno.llm.base import UsageSink
from proseferno.prompts import raw, render

JUDGE_WEIGHT = 0.6
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
    own = [s.markdown for s in samples if s.kind == "own" and s.markdown]
    return profile_author(own, baseline)


def report(scan_result: ScanResult, judgement: AIDetectionJudgement | None, judge_error: str | None = None) -> dict[str, Any]:
    if judgement is not None:
        judge_score = max(0, min(100, judgement.human_score))
        score = round(JUDGE_WEIGHT * judge_score + (1 - JUDGE_WEIGHT) * scan_result.score)
    else:
        judge_score = None
        score = scan_result.score
    key, label = band(score)
    flagged = [f.as_dict() for f in scan_result.flags]
    if judgement is not None:
        seen = {f["quote"] for f in flagged}
        judge_flags = [{**p.model_dump(), "source": "judge"} for p in judgement.flagged_passages if p.quote not in seen]
        flagged = judge_flags + flagged
    return {
        "score": score,
        "band": key,
        "label": label,
        "scan_score": scan_result.score,
        "judge_score": judge_score,
        "verdict": judgement.verdict if judgement else "",
        "human_signals": judgement.human_signals if judgement else [],
        "ai_signals": judgement.ai_signals if judgement else [],
        "signals": [s.as_dict() for s in scan_result.signals],
        "flagged": flagged[:15],
        "word_count": scan_result.word_count,
        "judge_error": judge_error,
        "checked_at": datetime.now(UTC).isoformat(),
    }


async def analyze(
    *,
    llm: LLM,
    settings: Settings,
    markdown: str,
    voice_profile: str,
    profile: AuthorProfile,
    use_judge: bool = True,
    usage: UsageSink | None = None,
) -> dict[str, Any]:
    """Scan, optionally ask the Claude judge, and return the combined report."""
    scan_result = scan(markdown, profile)
    if not use_judge:
        return report(scan_result, None)
    try:
        judgement = await llm.structured(
            task="ai detection",
            system=[SystemBlock(raw("detect_system"), cache=True)],
            prompt=render("detect", voice_profile=voice_profile or "_No voice profile._", scan=scan_result.tells_text(), post=markdown),
            schema=AIDetectionJudgement,
            effort=settings.effort_detect,
            usage=usage,
        )
    except LLMError as exc:
        return report(scan_result, None, judge_error=str(exc))
    return report(scan_result, judgement)
