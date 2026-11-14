"""The persona's Insights page: a Claude digest of the voice plus charts measured from samples and posts."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from itertools import pairwise
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from sqlmodel import Session, col, select

from proseferno.api.deps import ServicesDep, SessionDep, persona_or_404
from proseferno.api.schemas import (
    CountItem,
    FingerprintOut,
    FingerprintRow,
    FormulaFlowOut,
    FormulaLink,
    FormulaNode,
    InsightsDigestOut,
    InsightsOverview,
    JobOut,
    LessonItem,
    PersonaInsightsOut,
    PostPoint,
    TrackRecordOut,
    VoiceMixSlice,
)
from proseferno.db import Persona, Project, ProjectImage, ProjectReference, Sample, VoiceProfile
from proseferno.images.memes.formats import get_format
from proseferno.images.memes.generate import load_state
from proseferno.ingest.stylometrics import aggregate
from proseferno.voice import current_voice_profile
from proseferno.voice.insights import INSIGHTS_JOB, normalize, refresh_insights
from proseferno.writer import Dials, resolve, word_count
from proseferno.writer.formulas import catalog

router = APIRouter(prefix="/api")

Stage = Literal["article_type", "opener", "body", "closer"]
STAGES: tuple[Stage, ...] = ("article_type", "opener", "body", "closer")
USUAL = "Your usual"

# key, label, unit, multiplier: the style fingerprint rows.
FINGERPRINT: list[tuple[str, str, str, float]] = [
    ("avg_sentence_words", "Words per sentence", "words", 1),
    ("short_paragraph_ratio", "One-sentence paragraphs", "% of paragraphs", 100),
    ("question_per_100_sentences", "Questions", "per 100 sentences", 1),
    ("second_person_per_1k", "You and your", "per 1k words", 1),
    ("first_person_singular_per_1k", "I, me and my", "per 1k words", 1),
    ("contractions_per_1k", "Contractions", "per 1k words", 1),
    ("em_dash_per_1k", "Dashes", "per 1k words", 1),
    ("flesch_reading_ease", "Reading ease", "0-100, higher is easier", 1),
]

# Rough reference values for a typical technical blog post, used when the persona has no influence samples.
# They are approximate on purpose: a point of comparison, not a standard to meet.
TYPICAL_TECH_BLOG: dict[str, float] = {
    "avg_sentence_words": 19.0,
    "short_paragraph_ratio": 0.25,
    "question_per_100_sentences": 4.0,
    "second_person_per_1k": 12.0,
    "first_person_singular_per_1k": 8.0,
    "contractions_per_1k": 9.0,
    "em_dash_per_1k": 3.0,
    "flesch_reading_ease": 50.0,
}

OPENING_LABELS = {
    "question": "A question",
    "fact_or_statistic": "A fact or number",
    "personal_anecdote": "A personal story",
    "direct_address": "Talking to the reader",
    "statement": "A plain statement",
}


@router.get("/personas/{persona_id}/insights", response_model=PersonaInsightsOut)
def persona_insights(persona_id: int, session: SessionDep, services: ServicesDep) -> PersonaInsightsOut:
    persona = persona_or_404(session, persona_id)
    samples = list(session.exec(select(Sample).where(Sample.persona_id == persona_id)))
    own = [s for s in samples if s.kind == "own"]
    influences = [s for s in samples if s.kind == "influence"]
    profile = current_voice_profile(session, persona_id)
    digest = _digest(session, persona_id, profile)
    projects = list(session.exec(select(Project).where(Project.persona_id == persona_id).order_by(col(Project.created_at))))
    written = [p for p in projects if p.markdown.strip()]
    return PersonaInsightsOut(
        overview=InsightsOverview(
            persona_name=persona.display_name or persona.name,
            own_samples=len(own),
            influence_samples=len(influences),
            own_words=sum(s.word_count for s in own),
            voice_profile_version=profile.version if profile else None,
            updated_at=_updated_at(profile, digest),
        ),
        digest=digest,
        fingerprint=_fingerprint(own, influences),
        openers=_openers(own),
        phrases=_phrases(own),
        formula=_formula_flow(persona, written, profile, services.settings.revision_passes),
        track_record=_track_record(session, persona, written),
    )


@router.post("/personas/{persona_id}/insights/refresh", response_model=JobOut, status_code=202)
async def refresh_persona_insights(persona_id: int, session: SessionDep, services: ServicesDep) -> JobOut:
    """Rebuild the digest for the voice profile in use (one short Claude call)."""
    persona_or_404(session, persona_id)
    if current_voice_profile(session, persona_id) is None:
        raise HTTPException(422, "Generate a voice profile before building insights.")
    running = [j for j in services.jobs.active_for(persona_id=persona_id) if j.kind == INSIGHTS_JOB]
    if running:
        return JobOut(**running[0].model_dump())
    job = await services.jobs.start(
        INSIGHTS_JOB,
        lambda ctx: refresh_insights(engine=services.engine, llm=services.llm, settings=services.settings, persona_id=persona_id, ctx=ctx),
        persona_id=persona_id,
    )
    return JobOut(**job.model_dump())


# -- digest ------------------------------------------------------------------------------


def _digest(session: Session, persona_id: int, profile: VoiceProfile | None) -> InsightsDigestOut | None:
    """The in-use version's digest, else the newest one made (marked stale): edited and evolved versions have none."""
    if profile is None:
        return None
    source: VoiceProfile | None = profile if profile.insights else None
    if source is None:
        versions = session.exec(
            select(VoiceProfile).where(VoiceProfile.persona_id == persona_id).order_by(col(VoiceProfile.version).desc())
        )
        source = next((v for v in versions if v.insights), None)
    if source is None or not source.insights:
        return None
    data: dict[str, Any] = source.insights
    return InsightsDigestOut(
        headline=str(data.get("headline", "")),
        tone=list(data.get("tone", [])),
        signature_phrases=list(data.get("signature_phrases", [])),
        steer_clear=list(data.get("steer_clear", [])),
        voice_mix=[VoiceMixSlice.model_validate(m) for m in data.get("voice_mix", [])],
        sentences_sampled=int(data.get("sentences_sampled", 0)),
        sentences_labeled=int(data.get("sentences_labeled", 0)),
        image_habits=list(data.get("image_habits", [])),
        caption_example=str(data.get("caption_example", "")),
        generated_at=str(data.get("generated_at", "")),
        version=source.version,
        stale=source.version != profile.version,
    )


def _updated_at(profile: VoiceProfile | None, digest: InsightsDigestOut | None) -> datetime | None:
    if digest and digest.generated_at:
        try:
            return datetime.fromisoformat(digest.generated_at)
        except ValueError:
            pass
    return profile.created_at if profile else None


# -- measured charts ------------------------------------------------------------------------


def _fingerprint(own: list[Sample], influences: list[Sample]) -> FingerprintOut | None:
    you = aggregate([s.stylometrics for s in own if s.stylometrics])
    if not you:
        return None
    measured = aggregate([s.stylometrics for s in influences if s.stylometrics])
    reference: dict[str, Any] = measured or TYPICAL_TECH_BLOG
    rows = []
    for key, label, unit, scale in FINGERPRINT:
        value = you.get(key)
        if not isinstance(value, (int, float)):
            continue
        ref = reference.get(key)
        rows.append(
            FingerprintRow(
                key=key,
                label=label,
                you=round(float(value) * scale, 1),
                reference=round(float(ref) * scale, 1) if isinstance(ref, (int, float)) else None,
                unit=unit,
            )
        )
    return FingerprintOut(
        reference_label="Writers you read" if measured else "A typical tech blog (approximate)",
        reference_kind="influences" if measured else "typical",
        rows=rows,
    )


def _openers(own: list[Sample]) -> list[CountItem]:
    counts = Counter(str(s.stylometrics.get("opening_style", "")) for s in own if s.stylometrics)
    return [CountItem(id=style, label=OPENING_LABELS[style], count=n) for style, n in counts.most_common() if style in OPENING_LABELS]


def _phrases(own: list[Sample], limit: int = 12) -> list[CountItem]:
    """Recurring and signature phrases, counted by how many of the author's posts use them."""
    candidates: list[str] = []
    for sample in own:
        for phrase in [*(sample.analysis or {}).get("signature_phrases", []), *sample.stylometrics.get("top_phrases", [])]:
            if isinstance(phrase, str) and phrase.strip() and normalize(phrase) not in {normalize(c) for c in candidates}:
                candidates.append(phrase.strip().strip("\"“”'‘’"))
    texts = [f" {normalize(s.markdown)} " for s in own]
    items = []
    for phrase in candidates:
        key = normalize(phrase)
        if not key:
            continue
        used = sum(1 for t in texts if f" {key} " in t)
        if used:
            items.append(CountItem(id=key, label=phrase, count=used))
    items.sort(key=lambda i: (-i.count, -len(i.label)))
    # "wrong one" adds nothing next to "wrong one time": keep the longest of overlapping phrases.
    kept: list[CountItem] = []
    for item in items:
        if not any(f" {item.id} " in f" {longer.id} " for longer in kept):
            kept.append(item)
    return kept[:limit]


# -- posts ---------------------------------------------------------------------------------


def _labels() -> dict[Stage, dict[str, str]]:
    parts = catalog()
    return {
        "article_type": {t.id: t.label for t in parts["article_types"]},
        "opener": {o.id: o.label for o in parts["openers"]},
        "body": {o.id: o.label for o in parts["bodies"]},
        "closer": {o.id: o.label for o in parts["closers"]},
    }


def _formula_flow(persona: Persona, posts: list[Project], profile: VoiceProfile | None, revisions: int) -> FormulaFlowOut:
    """How the persona's posts flow through article type -> opener -> body -> closer."""
    labels = _labels()
    words_per_image = (profile.baseline_stylometrics or {}).get("words_per_image") if profile else None
    nodes: dict[str, FormulaNode] = {}
    links: Counter[tuple[str, str]] = Counter()
    for post in posts:
        resolved = resolve(Dials(**(post.dials or {})), persona, post.prompt, default_revisions=revisions, words_per_image=words_per_image)
        path = []
        for stage in STAGES:
            value = str(getattr(resolved, stage) or "auto")
            node_id = f"{stage}:{value}"
            nodes.setdefault(node_id, FormulaNode(id=node_id, stage=stage, label=labels[stage].get(value, USUAL)))
            path.append(node_id)
        for source, target in pairwise(path):
            links[(source, target)] += 1
    return FormulaFlowOut(
        posts=len(posts),
        nodes=list(nodes.values()),
        links=[FormulaLink(source=s, target=t, value=v) for (s, t), v in links.items()],
    )


def _score(report: dict[str, Any] | None, key: str) -> float | None:
    value = (report or {}).get(key)
    return float(value) if isinstance(value, (int, float)) else None


def _track_record(session: Session, persona: Persona, posts: list[Project]) -> TrackRecordOut:
    ids = [p.id for p in posts if p.id is not None]
    images = list(session.exec(select(ProjectImage).where(col(ProjectImage.project_id).in_(ids)))) if ids else []
    references = (
        list(session.exec(select(ProjectReference).where(col(ProjectReference.project_id).in_(ids), ProjectReference.status == "ready")))
        if ids
        else []
    )
    memes: Counter[str] = Counter()
    for image in images:
        if image.kind == "meme" and image.status == "ready":
            state = load_state(image.spec)
            meme_format = get_format(str(state.get("format", ""))) if state else None
            if meme_format is not None:
                memes[meme_format.id] += 1
    meme_names = {i: f.name for i in memes if (f := get_format(i)) is not None}
    stages = Counter(p.stage for p in posts)
    outcomes = Counter(p.outcome for p in posts if p.outcome)
    lessons = sorted(persona.edit_lessons or [], key=lambda lesson: -int(lesson.get("count", 1) or 1))[:5]
    points = [
        PostPoint(
            project_id=p.id,
            title=p.title or "Untitled post",
            created_at=p.created_at,
            stage=p.stage,
            outcome=p.outcome,
            words=word_count(p.markdown),
            authenticity=_score(p.authenticity, "score"),
            voice_match=_score(p.fidelity, "score"),
            critique=_score(p.critique, "overall"),
        )
        for p in posts
        if p.id is not None
    ]
    return TrackRecordOut(
        posts=len(posts),
        published=stages.get("published", 0),
        words=sum(point.words for point in points),
        images=sum(1 for i in images if i.status == "ready"),
        references=len(references),
        stages=[CountItem(id=s, label=s, count=n) for s, n in stages.most_common()],
        outcomes=[CountItem(id=o, label=o, count=n) for o, n in outcomes.most_common()],
        points=points,
        meme_formats=[CountItem(id=i, label=meme_names.get(i, i), count=n) for i, n in memes.most_common(3)],
        lessons=[
            LessonItem(
                kind=str(lesson.get("kind", "")),
                old=str(lesson.get("old", "")),
                new=str(lesson.get("new", "") or ""),
                count=int(lesson.get("count", 1) or 1),
            )
            for lesson in lessons
        ],
        playbook=len(persona.playbook or []),
    )
