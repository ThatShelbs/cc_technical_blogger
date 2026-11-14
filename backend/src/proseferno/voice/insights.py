"""The Insights digest: a short, quotable summary of a voice profile for the persona's Insights page.

Claude writes the wording and labels a fixed sample of the author's own sentences;
code counts the labels, so the voice mix percentages are measured, not guessed.
The digest is cached on ``VoiceProfile.insights`` and made with each generated version.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine
from sqlmodel import Session, select

from proseferno.config import Settings
from proseferno.db import Persona, Sample, VoiceProfile
from proseferno.ingest.stylometrics import split_sentences
from proseferno.jobs import JobContext
from proseferno.llm import LLM, SystemBlock
from proseferno.llm.base import UsageSink
from proseferno.prompts import raw, render
from proseferno.voice.schemas import VoiceInsights

log = logging.getLogger(__name__)

# Sentences Claude labels for the voice mix; the waffle chart shows their shares.
SAMPLE_SENTENCES = 60
# The job that rebuilds the digest; it does not count as the persona being busy.
INSIGHTS_JOB = "voice_insights"
_FENCE = re.compile(r"```.*?```", re.DOTALL)
_SKIP_LINE = re.compile(r"^\s*(#|!\[|\||<|\[IMAGE\]|\[CAPTION\]|---)")
_LIST_MARK = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_EMPHASIS = re.compile(r"[*_`]+")


class InsightsError(ValueError):
    pass


def prose_sentences(markdown: str) -> list[str]:
    """The author's prose sentences: no headings, code, images, tables or captions."""
    text = _FENCE.sub("\n", markdown)
    sentences: list[str] = []
    for line in text.splitlines():
        if not line.strip() or _SKIP_LINE.match(line):
            continue
        line = _EMPHASIS.sub("", _LINK.sub(r"\1", _LIST_MARK.sub("", line.lstrip("> "))))
        for sentence in split_sentences(line.strip()):
            if len(sentence.split()) >= 3:
                sentences.append(sentence[:300])
    return sentences


def sample_sentences(texts: list[str], limit: int = SAMPLE_SENTENCES) -> list[str]:
    """Up to ``limit`` sentences spread evenly through each text, taking turns between texts."""
    per_text = [prose_sentences(t) for t in texts]
    per_text = [s for s in per_text if s]
    if not per_text:
        return []
    share = max(1, -(-limit // len(per_text)))
    picked: list[list[str]] = []
    for sentences in per_text:
        if len(sentences) <= share:
            picked.append(sentences)
        else:
            step = len(sentences) / share
            picked.append([sentences[int(i * step)] for i in range(share)])
    out: list[str] = []
    for i in range(max(len(p) for p in picked)):
        out.extend(p[i] for p in picked if i < len(p))
    return out[:limit]


def count_mix(insights: VoiceInsights, sentence_count: int) -> tuple[list[dict[str, Any]], int]:
    """Count the sentence labels per category; ignore unknown categories, bad numbers and repeats."""
    names = {c.name.strip().lower(): c for c in insights.mix_categories if c.name.strip()}
    seen: set[int] = set()
    counts: Counter[str] = Counter()
    for label in insights.sentence_categories:
        key = label.category.strip().lower()
        if key not in names or not 1 <= label.index <= sentence_count or label.index in seen:
            continue
        seen.add(label.index)
        counts[key] += 1
    total = sum(counts.values())
    mix: list[dict[str, Any]] = [
        {
            "name": category.name.strip(),
            "description": category.description.strip(),
            "count": counts[key],
            "share": round(100 * counts[key] / total, 1) if total else 0.0,
        }
        for key, category in names.items()
        if counts[key]
    ]
    mix.sort(key=lambda m: -int(m["count"]))
    return mix, total


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower().replace("’", "'")).strip()


def verbatim_only(phrases: list[str], texts: list[str]) -> list[str]:
    """Keep the phrases that really occur in the author's writing (ignoring case and punctuation)."""
    haystack = " ".join(normalize(t) for t in texts)
    out: list[str] = []
    for phrase in phrases:
        clean = phrase.strip().strip("\"“”'‘’")
        key = normalize(clean)
        if key and f" {key} " in f" {haystack} " and clean not in out:
            out.append(clean)
    return out


def analysis_phrases(samples: list[Sample]) -> list[str]:
    phrases: list[str] = []
    for sample in samples:
        for phrase in (sample.analysis or {}).get("signature_phrases", []) or []:
            if isinstance(phrase, str) and phrase not in phrases:
                phrases.append(phrase)
    return phrases


async def build_insights(
    llm: LLM,
    settings: Settings,
    *,
    persona_name: str,
    profile_markdown: str,
    baseline: dict[str, Any],
    own_samples: list[Sample],
    usage: UsageSink | None = None,
) -> dict[str, Any]:
    """Ask Claude for the digest and turn its sentence labels into a measured voice mix."""
    texts = [s.markdown for s in own_samples if s.markdown.strip()]
    sentences = sample_sentences(texts)
    if not sentences:
        raise InsightsError("Add some of your own writing before building insights.")
    digest = await llm.structured(
        task="voice insights",
        system=[SystemBlock(raw("analyst_system"), cache=True)],
        prompt=render(
            "voice_insights",
            persona_name=persona_name,
            voice_profile=profile_markdown.strip(),
            baseline=json.dumps({k: v for k, v in baseline.items() if k != "recurring_phrases"}, indent=1),
            signature_phrases="\n".join(f"- {p}" for p in analysis_phrases(own_samples)) or "_None found._",
            sentences="\n".join(f"{i}. {s}" for i, s in enumerate(sentences, start=1)),
        ),
        schema=VoiceInsights,
        effort=settings.effort_insights,
        max_tokens=8000,
        usage=usage,
    )
    mix, labeled = count_mix(digest, len(sentences))
    return {
        "headline": digest.headline.strip(),
        "tone": [t.strip() for t in digest.tone if t.strip()][:6],
        "signature_phrases": verbatim_only(digest.signature_phrases, texts)[:8],
        "steer_clear": [t.strip() for t in digest.steer_clear if t.strip()][:5],
        "voice_mix": mix,
        "sentences_sampled": len(sentences),
        "sentences_labeled": labeled,
        "image_habits": [t.strip() for t in digest.image_habits if t.strip()][:4],
        "caption_example": digest.caption_example.strip(),
        "generated_at": datetime.now(UTC).isoformat(),
    }


async def try_build_insights(llm: LLM, settings: Settings, **kwargs: Any) -> dict[str, Any] | None:
    """The digest, or None when it fails: a missing digest never fails the voice profile."""
    try:
        return await build_insights(llm, settings, **kwargs)
    except Exception:
        log.warning("Could not build the voice insights digest", exc_info=True)
        return None


async def refresh_insights(*, engine: Engine, llm: LLM, settings: Settings, persona_id: int, ctx: JobContext) -> dict[str, Any]:
    """Rebuild the digest for the voice profile in use (older, edited and evolved versions have none)."""
    from proseferno.voice.pipeline import current_voice_profile

    with Session(engine) as session:
        persona = session.get(Persona, persona_id)
        profile = current_voice_profile(session, persona_id)
        if persona is None or profile is None:
            raise InsightsError("Generate a voice profile before building insights.")
        own = list(session.exec(select(Sample).where(Sample.persona_id == persona_id, Sample.kind == "own")))
        profile_id = profile.id
        persona_name = persona.display_name or persona.name
        markdown = profile.markdown
        baseline = profile.baseline_stylometrics or {}
    await ctx.progress(0.1, "Reading your voice profile")
    insights = await build_insights(
        llm, settings, persona_name=persona_name, profile_markdown=markdown, baseline=baseline, own_samples=own, usage=ctx.add_usage
    )
    with Session(engine) as session:
        row = session.get(VoiceProfile, profile_id)
        if row is not None:
            row.insights = insights
            session.add(row)
            session.commit()
    await ctx.progress(1.0, "Insights ready")
    return {"voice_profile_id": profile_id}
