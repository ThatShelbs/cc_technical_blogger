"""Learn from published posts: analyze them into proposals, and apply the ones the author approves.

``change_stage`` moves a post through draft -> ready -> published and says which analyses are due:
publishing compares the generated baseline with the published text (``edits``); a Good traction or Viral
outcome reads the post for what made it work (``secret_sauce``). Each analysis is a ``PersonaEvolution`` row
the author reviews. Applying it adds playbook entries and, for profile changes, saves a new voice profile version.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Literal

from sqlalchemy import Engine
from sqlmodel import Session, col, select

from proseferno.config import Settings
from proseferno.db import Job, Persona, PersonaEvolution, Project, VoiceProfile, utcnow
from proseferno.evolution.diff import baseline_hash, diff_digest, edit_rate
from proseferno.evolution.schemas import EvolutionPlan, ProfileEdits, SecretSauce
from proseferno.images import PLACEHOLDER_RE
from proseferno.jobs import JobContext
from proseferno.llm import LLM, SystemBlock
from proseferno.prompts import raw, render
from proseferno.storage import Storage
from proseferno.voice import current_voice_profile, latest_voice_profile, unpin
from proseferno.voice.lessons import format_lessons
from proseferno.voice.playbook import OUTCOME_LABEL, OUTCOME_RANK, add_playbook, approved_changes, format_playbook
from proseferno.writer.dials import Dials, resolve
from proseferno.writer.schemas import TextEdit
from proseferno.writer.tweak import apply_edits

if TYPE_CHECKING:
    from proseferno.services import Services

Kind = Literal["edits", "secret_sauce"]
STAGES = ("draft", "ready", "published")
OUTCOMES = ("too_early", "small", "good", "viral")
# Outcomes worth learning a post's secret sauce from.
SAUCE_OUTCOMES = ("good", "viral")
EVOLUTION_JOBS = ("evolve_post", "apply_evolution")
# Below this share of changed text the persona got the post right: nothing to learn, no model call.
MIN_EDIT_RATE = 0.02
MAX_ITEMS = 6
MAX_POST_WORDS = 8000
INTERRUPTED = "The app restarted before this analysis finished. Analyze the post again."
_DO_DONT_RE = re.compile(r"^##\s+Do\s*/\s*Don\S?t\s*$", re.IGNORECASE | re.MULTILINE)
_ANCHORS_RE = re.compile(r"^##\s+Voice Anchors\s*$", re.IGNORECASE | re.MULTILINE)


class EvolutionError(ValueError):
    pass


def latest_evolution(session: Session, project_id: int, kind: str) -> PersonaEvolution | None:
    return session.exec(
        select(PersonaEvolution)
        .where(PersonaEvolution.project_id == project_id, PersonaEvolution.kind == kind)
        .order_by(col(PersonaEvolution.created_at).desc(), col(PersonaEvolution.id).desc())
    ).first()


def change_stage(session: Session, project: Project, *, stage: str | None, outcome: str | None) -> list[Kind]:
    """Set the post's stage and outcome, and return the analyses now due. The caller commits, then starts them.

    An outcome implies the post is published; leaving "published" clears the outcome.
    """
    assert project.id is not None
    old_stage, old_outcome = project.stage, project.outcome
    if stage is not None:
        project.stage = stage
    if outcome is not None:
        project.outcome = outcome
        if stage is None:
            project.stage = "published"
    if project.stage == "published":
        project.outcome = project.outcome or "too_early"
        project.published_at = project.published_at or utcnow()
    else:
        project.outcome, project.published_at = None, None

    due: list[Kind] = []
    if project.stage != "published":
        return due
    if old_stage != "published" and project.baseline_markdown:
        previous = latest_evolution(session, project.id, "edits")
        if previous is None or previous.state == "error" or previous.baseline_hash != baseline_hash(project.baseline_markdown):
            due.append("edits")
    if project.outcome in SAUCE_OUTCOMES and project.outcome != old_outcome:
        previous = latest_evolution(session, project.id, "secret_sauce")
        better = previous is not None and OUTCOME_RANK.get(project.outcome, 0) > OUTCOME_RANK.get(previous.outcome or "", 0)
        if previous is None or previous.state == "error" or (better and previous.state != "applied"):
            due.append("secret_sauce")
    return due


async def start_analysis(services: Services, project_id: int, kind: Kind) -> PersonaEvolution:
    """Create the proposal row (state "analyzing") and run the analysis as a job. Replaces an unapplied one."""
    with Session(services.engine) as session:
        project = session.get(Project, project_id)
        if project is None:
            raise EvolutionError("Post not found.")
        if kind == "edits" and not project.baseline_markdown:
            raise EvolutionError("This post has no generated text on record to compare with. Regenerate it to start tracking edits.")
        if kind == "secret_sauce" and not project.markdown:
            raise EvolutionError("Generate the post first.")
        for old in session.exec(select(PersonaEvolution).where(PersonaEvolution.project_id == project_id, PersonaEvolution.kind == kind)):
            if old.state == "analyzing":
                return old
            if old.state != "applied":
                session.delete(old)
        voice_profile = current_voice_profile(session, project.persona_id)
        row = PersonaEvolution(
            persona_id=project.persona_id,
            project_id=project_id,
            kind=kind,
            outcome=project.outcome,
            project_title=project.title,
            baseline_hash=baseline_hash(project.baseline_markdown) if project.baseline_markdown else "",
            voice_profile_version=voice_profile.version if voice_profile else None,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        assert row.id is not None
        evolution_id, persona_id = row.id, row.persona_id

    job = await services.jobs.start(
        "evolve_post",
        lambda ctx: analyze(engine=services.engine, llm=services.llm, settings=services.settings, evolution_id=evolution_id, ctx=ctx),
        persona_id=persona_id,
    )
    with Session(services.engine) as session:
        fresh = session.get(PersonaEvolution, evolution_id)
        assert fresh is not None
        fresh.job_id = job.id
        session.add(fresh)
        session.commit()
        session.refresh(fresh)
        return fresh


def _save(engine: Engine, evolution_id: int, **fields: Any) -> None:
    with Session(engine) as session:
        row = session.get(PersonaEvolution, evolution_id)
        if row is None:
            return
        for key, value in fields.items():
            setattr(row, key, value)
        session.add(row)
        session.commit()


def _post_text(markdown: str) -> str:
    text = PLACEHOLDER_RE.sub("[image]", markdown)
    words = text.split(" ")
    if len(words) <= MAX_POST_WORDS:
        return text
    return " ".join(words[:MAX_POST_WORDS]) + "\n\n[The rest is left out for length.]"


async def analyze(*, engine: Engine, llm: LLM, settings: Settings, evolution_id: int, ctx: JobContext) -> dict[str, Any]:
    """The ``evolve_post`` job. A failure is recorded on the proposal, never on the post."""
    try:
        return await _analyze(engine=engine, llm=llm, settings=settings, evolution_id=evolution_id, ctx=ctx)
    except Exception as exc:
        _save(engine, evolution_id, state="error", error=str(exc)[:400] or type(exc).__name__)
        raise


async def _analyze(*, engine: Engine, llm: LLM, settings: Settings, evolution_id: int, ctx: JobContext) -> dict[str, Any]:
    with Session(engine) as session:
        row = session.get(PersonaEvolution, evolution_id)
        if row is None:
            raise EvolutionError("Proposal not found.")
        project = session.get(Project, row.project_id) if row.project_id else None
        persona = session.get(Persona, row.persona_id)
        if project is None or persona is None:
            raise EvolutionError("The post or its persona no longer exists.")
        voice_profile = current_voice_profile(session, row.persona_id)
        approved = approved_changes(session, row.persona_id)
    if voice_profile is None:
        raise EvolutionError("This persona has no voice profile yet.")
    common = {
        "title": project.title,
        "persona_name": persona.name,
        "voice_profile": voice_profile.markdown,
        "voice_profile_version": voice_profile.version,
        "playbook": format_playbook(persona.playbook) or "_Nothing yet._",
        "approved": approved or "_None yet._",
    }
    schema: type[EvolutionPlan] | type[SecretSauce]
    if row.kind == "edits":
        if not project.baseline_markdown:
            raise EvolutionError("This post has no generated text on record to compare with.")
        rate = edit_rate(project.baseline_markdown, project.markdown)
        _save(engine, evolution_id, edit_rate=rate)
        if rate < MIN_EDIT_RATE:
            summary = f"You changed {rate:.0%} of the generated text, so the persona already writes this kind of post the way you want."
            _save(engine, evolution_id, state="clean", summary=summary)
            await ctx.progress(1.0, "Barely edited: nothing to change")
            return {"evolution_id": evolution_id, "items": 0}
        await ctx.progress(0.2, f"Reading your edits ({rate:.0%} of the text changed)")
        prompt = render(
            "evolve_edits",
            **common,
            edit_percent=f"{rate:.0%}",
            diff=diff_digest(project.baseline_markdown, project.markdown),
            lessons=format_lessons(persona.edit_lessons) or "_None yet._",
        )
        schema, task = EvolutionPlan, "persona evolution"
    else:
        dials = resolve(Dials(**(project.dials or {})), persona, project.prompt, default_revisions=settings.revision_passes)
        await ctx.progress(0.2, "Working out what made this post land")
        prompt = render(
            "secret_sauce",
            **common,
            outcome=OUTCOME_LABEL.get(project.outcome or "", "it did well"),
            post=_post_text(project.markdown),
            formula=dials.formula_guide or "_No formula chosen._",
        )
        schema, task = SecretSauce, "secret sauce"

    result = await llm.structured(
        task=task,
        system=[SystemBlock(raw("evolve_system"))],
        prompt=prompt,
        schema=schema,
        effort=settings.effort_evolve,
        usage=ctx.add_usage,
    )
    kept = [item for item in result.items if item.change.strip()][:MAX_ITEMS]
    items = [
        {
            "id": f"c{i + 1}",
            "area": item.area.strip(),
            "change": " ".join(item.change.split()),
            "evidence": item.evidence.strip(),
            "target": item.target,
            "applied": False,
        }
        for i, item in enumerate(kept)
    ]
    _save(engine, evolution_id, state="pending" if items else "clean", summary=result.summary.strip(), items=items)
    await ctx.progress(1.0, f"{len(items)} suggestions ready to review" if items else "Nothing to change")
    return {"evolution_id": evolution_id, "items": len(items)}


async def start_apply(services: Services, evolution_id: int, item_ids: list[str]) -> Job:
    with Session(services.engine) as session:
        row = session.get(PersonaEvolution, evolution_id)
        if row is None:
            raise EvolutionError("Proposal not found.")
        if row.state != "pending":
            raise EvolutionError("This proposal is not waiting for review.")
        known = {str(item.get("id")) for item in row.items or []}
        chosen = [i for i in item_ids if i in known]
        if not chosen:
            raise EvolutionError("Choose at least one change to apply.")
        persona_id = row.persona_id
    return await services.jobs.start(
        "apply_evolution",
        lambda ctx: apply_evolution(
            engine=services.engine,
            llm=services.llm,
            settings=services.settings,
            storage=services.storage,
            evolution_id=evolution_id,
            item_ids=chosen,
            ctx=ctx,
        ),
        persona_id=persona_id,
    )


def add_rules(markdown: str, rules: list[str]) -> str:
    """Add bullets to the end of the Do / Don't section, creating it (before the Voice Anchors) if missing."""
    if not rules:
        return markdown
    bullets = "".join(f"- {rule}\n" for rule in rules)
    heading = _DO_DONT_RE.search(markdown)
    if heading:
        following = re.search(r"^## ", markdown[heading.end() :], re.MULTILINE)
        end = heading.end() + following.start() if following else len(markdown)
        head = markdown[:end].rstrip("\n") + "\n" + bullets
        return head + ("\n" + markdown[end:] if following else "")
    block = f"## Do / Don't\n\n{bullets}\n"
    anchors = _ANCHORS_RE.search(markdown)
    if anchors:
        return markdown[: anchors.start()] + block + markdown[anchors.start() :]
    return markdown.rstrip("\n") + "\n\n" + block


async def apply_evolution(
    *,
    engine: Engine,
    llm: LLM,
    settings: Settings,
    storage: Storage,
    evolution_id: int,
    item_ids: list[str],
    ctx: JobContext,
) -> dict[str, Any]:
    """The ``apply_evolution`` job: playbook entries, then (for profile changes) a new voice profile version."""
    with Session(engine) as session:
        row = session.get(PersonaEvolution, evolution_id)
        if row is None or row.state != "pending":
            raise EvolutionError("This proposal is not waiting for review.")
        voice_profile = current_voice_profile(session, row.persona_id)
        latest = latest_voice_profile(session, row.persona_id)
    chosen = [item for item in row.items or [] if item.get("id") in item_ids]
    profile_items = [item for item in chosen if item.get("target") == "profile"]
    playbook_items = [item for item in chosen if item.get("target") != "profile"]

    new_version: int | None = None
    if profile_items:
        if voice_profile is None or latest is None:
            raise EvolutionError("This persona has no voice profile yet.")
        await ctx.progress(0.2, "Working the changes into the voice profile")
        changes = "\n".join(f"- {item['id']} ({item.get('area', '')}): {item['change']}" for item in profile_items)
        result = await llm.structured(
            task="voice profile evolution",
            system=[SystemBlock(raw("evolve_system"))],
            prompt=render("evolve_apply", changes=changes, voice_profile=voice_profile.markdown),
            schema=ProfileEdits,
            effort=settings.effort_evolve,
            usage=ctx.add_usage,
        )
        markdown, placed = voice_profile.markdown, set()
        for edit in result.edits:
            updated, applied, _ = apply_edits(markdown, [TextEdit(find=edit.find, replace=edit.replace)])
            if applied:
                markdown = updated
                placed.add(edit.item)
        # A change the model could not place still reaches the profile, as a rule.
        markdown = add_rules(markdown, [item["change"] for item in profile_items if item["id"] not in placed])
        markdown = markdown.strip() + "\n"
        new_version = latest.version + 1
        with Session(engine) as session:
            session.add(
                VoiceProfile(
                    persona_id=row.persona_id,
                    version=new_version,
                    label=f"Evolved: {row.project_title}"[:80],
                    markdown=markdown,
                    best_practices=voice_profile.best_practices,
                    sample_ids=voice_profile.sample_ids,
                    baseline_stylometrics=voice_profile.baseline_stylometrics,
                    model=voice_profile.model,
                )
            )
            unpin(session, row.persona_id)
            session.commit()
        storage.voice_profile_path(row.persona_id, new_version).write_text(markdown, encoding="utf-8")

    with Session(engine) as session:
        persona = session.get(Persona, row.persona_id)
        fresh = session.get(PersonaEvolution, evolution_id)
        if persona is None or fresh is None:
            raise EvolutionError("The persona no longer exists.")
        added = add_playbook(
            persona,
            [item["change"] for item in playbook_items],
            project_id=fresh.project_id,
            title=fresh.project_title,
            outcome=fresh.outcome,
        )
        persona.updated_at = utcnow()
        fresh.items = [{**item, "applied": item.get("id") in item_ids} for item in fresh.items or []]
        fresh.state, fresh.applied_version, fresh.applied_at = "applied", new_version, utcnow()
        session.add(persona)
        session.add(fresh)
        session.commit()
    parts = [f"voice profile v{new_version}"] if new_version else []
    if added:
        parts.append(f"{added} playbook {'entry' if added == 1 else 'entries'}")
    await ctx.progress(1.0, "Applied: " + (", ".join(parts) or "nothing new"))
    return {"evolution_id": evolution_id, "version": new_version, "playbook_added": added}


def dismiss(session: Session, row: PersonaEvolution) -> None:
    if row.state not in ("pending", "error", "clean"):
        raise EvolutionError("Only proposals waiting for review can be dismissed.")
    row.state = "dismissed"
    session.add(row)
    session.commit()


def fail_analyzing(engine: Engine) -> int:
    """Analyses still running at startup lost their job in a previous run."""
    with Session(engine) as session:
        rows = list(session.exec(select(PersonaEvolution).where(PersonaEvolution.state == "analyzing")))
        for row in rows:
            row.state, row.error = "error", INTERRUPTED
            session.add(row)
        session.commit()
        return len(rows)
