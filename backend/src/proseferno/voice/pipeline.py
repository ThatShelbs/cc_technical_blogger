"""Turn a persona's samples into a versioned ``voice_profile.md``.

Steps: analyze each sample (cached on the sample) -> optional web research on
best practices -> synthesize the voice profile from analyses + measured baseline.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Engine
from sqlmodel import Session, col, select

from proseferno.config import Settings
from proseferno.db import Persona, Sample, VoiceProfile
from proseferno.ingest.stylometrics import aggregate
from proseferno.jobs import JobContext
from proseferno.llm import LLM, SystemBlock
from proseferno.prompts import raw, render
from proseferno.storage import Storage
from proseferno.voice.lessons import format_lessons
from proseferno.voice.schemas import SampleAnalysis

RESEARCH_MAX_AGE = timedelta(days=30)


class VoiceError(ValueError):
    pass


def latest_voice_profile(session: Session, persona_id: int) -> VoiceProfile | None:
    return session.exec(
        select(VoiceProfile).where(VoiceProfile.persona_id == persona_id).order_by(col(VoiceProfile.version).desc())
    ).first()


def voice_profile_version(session: Session, persona_id: int, version: int) -> VoiceProfile | None:
    return session.exec(select(VoiceProfile).where(VoiceProfile.persona_id == persona_id, VoiceProfile.version == version)).first()


def current_voice_profile(session: Session, persona_id: int) -> VoiceProfile | None:
    """The version new posts are written with: the pinned one, else the latest."""
    persona = session.get(Persona, persona_id)
    if persona is not None and persona.pinned_voice_profile_version is not None:
        pinned = voice_profile_version(session, persona_id, persona.pinned_voice_profile_version)
        if pinned is not None:
            return pinned
    return latest_voice_profile(session, persona_id)


def unpin(session: Session, persona_id: int) -> None:
    """A brand-new version becomes the one in use."""
    persona = session.get(Persona, persona_id)
    if persona is not None and persona.pinned_voice_profile_version is not None:
        persona.pinned_voice_profile_version = None
        session.add(persona)


INFLUENCE_GUIDE = {
    range(1, 4): "Light touch: borrow an occasional technique only where the author's own posts are silent.",
    range(4, 7): "Borrow the influences' techniques that fit the author's voice; the author's own posts decide identity.",
    range(7, 10): "Lean on the influences: fold their structure, hooks and devices in wherever they fit the author.",
    range(10, 11): "Make the influences a major source of technique, while identity and soul still come only from the author.",
}


def truncate_words(markdown: str, max_words: int) -> str:
    """The first ``max_words`` words of a sample, keeping its line breaks (0 = all of it)."""
    if max_words <= 0:
        return markdown
    kept: list[str] = []
    remaining = max_words
    for line in markdown.splitlines():
        words = line.split()
        if len(words) >= remaining:
            kept.append(" ".join(words[:remaining]))
            break
        kept.append(line)
        remaining -= len(words)
    return "\n".join(kept)


def samples_in_budget(samples: list[Sample], persona: Persona) -> list[Sample]:
    """The samples the voice profile learns from: those long enough for the persona's minimum."""
    return [s for s in samples if s.word_count >= persona.voice_sample_min_words]


def needs_analysis(sample: Sample, max_words: int) -> bool:
    """Not analyzed yet, or analyzed with a different word limit."""
    return not sample.analysis or int(sample.analysis.get("_word_limit", 0)) != max_words


async def analyze_sample(
    llm: LLM, settings: Settings, sample: Sample, ctx: JobContext | None = None, *, max_words: int = 0
) -> dict[str, Any]:
    kind_description = (
        "the persona's OWN writing (defines their identity and voice)"
        if sample.kind == "own"
        else "an INFLUENCE: writing by someone else the persona admires (borrow technique, not identity)"
    )
    analysis = await llm.structured(
        task="sample analysis",
        system=[SystemBlock(raw("analyst_system"), cache=True)],
        prompt=render(
            "analyze_sample",
            kind_description=kind_description,
            stylometrics=json.dumps(sample.stylometrics, indent=1),
            title=sample.title,
            markdown=truncate_words(sample.markdown, max_words),
        ),
        schema=SampleAnalysis,
        effort=settings.effort_analyze,
        usage=ctx.add_usage if ctx else None,
    )
    return {**analysis.model_dump(), "_word_limit": max_words}


async def research_best_practices(llm: LLM, settings: Settings, ctx: JobContext | None = None) -> str:
    result = await llm.research(
        system=[SystemBlock(raw("research_system"))],
        prompt=render("research", year=datetime.now(UTC).year),
        effort=settings.effort_research,
        max_searches=settings.research_max_searches,
        usage=ctx.add_usage if ctx else None,
    )
    text = result.text.strip()
    if result.citations:
        sources = "\n".join(f"- [{c.title or c.url}]({c.url})" for c in result.citations)
        text += f"\n\n## Sources\n{sources}\n"
    return text


async def generate_voice_profile(
    *,
    engine: Engine,
    llm: LLM,
    settings: Settings,
    storage: Storage,
    persona_id: int,
    ctx: JobContext,
    label: str = "",
) -> dict[str, Any]:
    with Session(engine) as session:
        persona = session.get(Persona, persona_id)
        if persona is None:
            raise VoiceError("Persona not found.")
        all_samples = list(session.exec(select(Sample).where(Sample.persona_id == persona_id)))
        previous = latest_voice_profile(session, persona_id)
    if not any(s.kind == "own" for s in all_samples):
        raise VoiceError("Add at least one sample of your own writing before generating a voice profile.")
    samples = samples_in_budget(all_samples, persona)
    if persona.voice_influence_weight <= 0:
        samples = [s for s in samples if s.kind == "own"]
    own = [s for s in samples if s.kind == "own"]
    if not own:
        raise VoiceError(
            f"None of your own samples has at least {persona.voice_sample_min_words} words. "
            "Lower the minimum sample length in the voice profile settings."
        )
    max_words = persona.voice_sample_max_words

    # 1. Analyze every sample not analyzed yet with this word limit (cached on the sample row).
    pending = [s for s in samples if needs_analysis(s, max_words)]
    done = 0
    semaphore = asyncio.Semaphore(4)

    async def analyze(sample: Sample) -> None:
        nonlocal done
        async with semaphore:
            analysis = await analyze_sample(llm, settings, sample, ctx, max_words=max_words)
        with Session(engine) as session:
            row = session.get(Sample, sample.id)
            if row is not None:
                row.analysis = analysis
                session.add(row)
                session.commit()
        sample.analysis = analysis
        done += 1
        await ctx.progress(0.05 + 0.5 * done / max(1, len(pending)), f"Analyzed {done} of {len(pending)} samples")

    await ctx.progress(0.05, f"Analyzing {len(pending)} samples" if pending else "Using cached sample analyses")
    await asyncio.gather(*(analyze(s) for s in pending))

    # 2. Optional research (reused for 30 days).
    best_practices = ""
    if persona.research_enabled:
        fresh = (
            previous is not None
            and previous.best_practices
            and previous.created_at.replace(tzinfo=UTC) > datetime.now(UTC) - RESEARCH_MAX_AGE
        )
        if fresh and previous is not None and previous.best_practices:
            best_practices = previous.best_practices
            await ctx.progress(0.6, "Reusing recent best-practice research")
        else:
            await ctx.progress(0.58, "Researching best practices on the web")
            best_practices = await research_best_practices(llm, settings, ctx)

    # 3. Synthesize.
    baseline = aggregate([s.stylometrics for s in own])
    influences = [s for s in samples if s.kind == "influence"]
    await ctx.progress(0.65, "Writing your voice profile")

    async def on_delta(text: str) -> None:
        await ctx.emit("voice_delta", {"text": text})

    markdown = await llm.text(
        task="voice profile synthesis",
        system=[SystemBlock(raw("voice_system"))],
        prompt=render(
            "voice_synthesize",
            persona_name=persona.name,
            display_name=persona.display_name or persona.name,
            baseline=json.dumps(baseline, indent=1),
            own_count=len(own),
            own_analyses=json.dumps([_analysis_payload(s) for s in own], indent=1),
            influence_count=len(influences),
            influence_analyses=json.dumps([_analysis_payload(s) for s in influences], indent=1) if influences else "[]",
            influence_guide=_influence_guide(persona.voice_influence_weight, len(influences)),
            best_practices=best_practices or "_No research requested._",
            target_words=persona.voice_profile_words,
            edit_lessons=format_lessons(persona.edit_lessons) or "_None recorded yet._",
        ),
        effort=settings.effort_synthesize,
        on_delta=on_delta,
        usage=ctx.add_usage,
    )
    markdown = markdown.strip() + "\n"

    with Session(engine) as session:
        version = (previous.version + 1) if previous else 1
        voice_profile = VoiceProfile(
            persona_id=persona_id,
            version=version,
            label=label.strip()[:80],
            markdown=markdown,
            best_practices=best_practices or None,
            sample_ids=[s.id for s in samples if s.id is not None],
            baseline_stylometrics=baseline,
            model=settings.model,
        )
        session.add(voice_profile)
        unpin(session, persona_id)
        visual = _extract_visual_style(markdown)
        persona_row = session.get(Persona, persona_id)
        if persona_row is not None and visual and not persona_row.visual_style:
            persona_row.visual_style = visual
            session.add(persona_row)
        session.commit()
        session.refresh(voice_profile)
    storage.voice_profile_path(persona_id, version).write_text(markdown, encoding="utf-8")
    await ctx.progress(1.0, f"Voice profile v{version} ready")
    return {"voice_profile_id": voice_profile.id, "version": version}


def _analysis_payload(sample: Sample) -> dict[str, Any]:
    analysis = {k: v for k, v in (sample.analysis or {}).items() if not k.startswith("_")}
    return {"title": sample.title, "subtitle": sample.subtitle, "word_count": sample.word_count, **analysis}


def _influence_guide(weight: int, count: int) -> str:
    if count == 0:
        return "No influence posts are used for this profile."
    weight = max(1, min(10, weight))
    return f"Influence weight {weight}/10. " + next(text for span, text in INFLUENCE_GUIDE.items() if weight in span)


def _extract_visual_style(markdown: str) -> str:
    for line in markdown.splitlines():
        lowered = line.lower()
        if "visual style" in lowered and ":" in line:
            value = line.split(":", 1)[1].strip(" *_")
            if value:
                return value[:300]
    return ""
