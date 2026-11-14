"""Run an A/B test of one post: two hidden generations, a blind choice, and what the persona learns from it.

The host project keeps its current text while the test runs. ``control`` and ``challenger`` are real ``Project``
rows (every pipeline step and image file is keyed by project id) marked with ``variant`` so lists skip them.
Deciding moves the winner into the host, takes any parts the author wanted from the other post, and deletes both
variants. Only then are the roles and the challenger's tweaks shown, and the author may adopt them.
"""

from __future__ import annotations

import asyncio
import logging
import random
import shutil
from typing import Any

from sqlalchemy import Engine
from sqlmodel import Session, col, delete, select

from proseferno.abtest.blend import PARTS, take_closer, take_opener, take_title
from proseferno.abtest.perturb import build_challenger
from proseferno.authenticity import analyze, author_profile
from proseferno.db import ABTest, Persona, PersonaEvolution, Project, ProjectImage, ProjectReference, Sample, utcnow
from proseferno.evolution.service import start_apply
from proseferno.images import PLACEHOLDER_RE
from proseferno.jobs import Job, JobContext
from proseferno.llm import LLMError
from proseferno.services import Services
from proseferno.storage import Storage
from proseferno.voice import current_voice_profile
from proseferno.writer.dials import Dials, resolve
from proseferno.writer.formulas import clean as clean_formula
from proseferno.writer.pipeline import Variation, WriterError, generate_article, measure, split_title
from proseferno.writer.tweak import TEXT_JOBS, tweak_post

log = logging.getLogger(__name__)

ROLES = ("control", "challenger")
# A test the author still has to act on: it takes over the post page.
OPEN = ("generating", "voting", "deciding", "error")
INTERRUPTED = "The app restarted before both posts were written. Try again."
EVIDENCE = "The version written this way won your blind A/B test."
# Which of the challenger's tweaks a part taken from it stands for.
_PART_TWEAKS: dict[str, tuple[str, str]] = {
    "opener": ("field", "opener"),
    "closer": ("field", "closer"),
    "title": ("group", "Title"),
    "hero": ("group", "Images"),
    "meme": ("group", "Images"),
    "image_style": ("group", "Images"),
}


class ABTestError(ValueError):
    pass


# -- lookups ---------------------------------------------------------------------------


def current_test(session: Session, project_id: int) -> ABTest | None:
    """The host project's test that still needs the author: running, waiting for a choice, or decided but not yet answered."""
    rows = session.exec(select(ABTest).where(ABTest.project_id == project_id).order_by(col(ABTest.id).desc())).all()
    for row in rows:
        if row.status in OPEN or (row.status == "decided" and row.adopted is None):
            return row
    return None


def other(role: str) -> str:
    return "challenger" if role == "control" else "control"


def role_of(test: ABTest, side: str) -> str:
    """The variant behind "left" (Post 1) or "right" (Post 2)."""
    return test.left_role if side == "left" else other(test.left_role)


def variant_id(test: ABTest, role: str) -> int | None:
    return test.control_project_id if role == "control" else test.challenger_project_id


def suggested_tweaks(test: ABTest) -> list[str]:
    """Tweak ids worth adopting: all of the winner's, minus parts taken back from the control (or only those taken from the challenger)."""
    taken = [_PART_TWEAKS[p] for p in test.taken or [] if p in _PART_TWEAKS]

    def stands_for_taken(tweak: dict[str, Any]) -> bool:
        return any(tweak.get(key) == value for key, value in taken)

    if test.winner == "challenger":
        return [t["id"] for t in test.tweaks or [] if not stands_for_taken(t)]
    return [t["id"] for t in test.tweaks or [] if stands_for_taken(t)]


# -- deleting ---------------------------------------------------------------------------


def _delete_rows(session: Session, storage: Storage, project_ids: list[int]) -> None:
    if not project_ids:
        return
    session.exec(delete(ProjectImage).where(col(ProjectImage.project_id).in_(project_ids)))  # type: ignore[call-overload]
    session.exec(delete(ProjectReference).where(col(ProjectReference.project_id).in_(project_ids)))  # type: ignore[call-overload]
    session.exec(delete(Project).where(col(Project.id).in_(project_ids)))  # type: ignore[call-overload]
    for project_id in project_ids:
        shutil.rmtree(storage.root / "projects" / str(project_id), ignore_errors=True)


def delete_variants(session: Session, storage: Storage, test: ABTest) -> None:
    """Remove both hidden posts of a test (rows and files). The caller commits."""
    ids = [i for i in (test.control_project_id, test.challenger_project_id) if i is not None]
    _delete_rows(session, storage, ids)
    test.control_project_id = test.challenger_project_id = None
    session.add(test)


def delete_project_data(session: Session, storage: Storage, project_id: int) -> None:
    """Delete a post with its images, references and A/B tests (and their hidden variants). The caller commits."""
    for test in session.exec(select(ABTest).where(ABTest.project_id == project_id)).all():
        delete_variants(session, storage, test)
        session.delete(test)
    _delete_rows(session, storage, [project_id])


def fail_interrupted(engine: Engine) -> int:
    """Tests whose job was lost in a restart: a generation becomes an error; an unfinished decision can be made again."""
    with Session(engine) as session:
        rows = list(session.exec(select(ABTest).where(col(ABTest.status).in_(["generating", "deciding"]))))
        for row in rows:
            if row.status == "generating":
                row.status, row.error = "error", INTERRUPTED
            elif row.control_project_id is not None and row.challenger_project_id is not None:
                row.status = "voting"
            else:
                row.status, row.decided_at = "decided", row.decided_at or utcnow()
            session.add(row)
        session.commit()
        return len(rows)


# -- starting and generating ---------------------------------------------------------------------------


async def start_ab_test(services: Services, project_id: int) -> Job:
    """Create the two variants of the host project's post and start writing both."""
    with Session(services.engine) as session:
        host = session.get(Project, project_id)
        if host is None:
            raise ABTestError("Project not found.")
        if host.variant is not None:
            raise ABTestError("This post is already part of an A/B test.")
        if services.jobs.active_for(project_id=project_id, kinds=TEXT_JOBS):
            raise ABTestError("Claude is still working on this post. Wait for it to finish.")
        persona = session.get(Persona, host.persona_id)
        voice_profile = current_voice_profile(session, host.persona_id)
        if persona is None or voice_profile is None:
            raise ABTestError("This persona has no voice profile yet. Generate it first.")
        previous = current_test(session, project_id)
        if previous is not None and previous.status in ("voting", "deciding", "generating"):
            raise ABTestError("This post already has an A/B test waiting. Pick a winner or discard it first.")
        if previous is not None:
            # A failed test is replaced; an unanswered "adopt?" question is taken as "keep my settings".
            if previous.status == "error":
                delete_variants(session, services.storage, previous)
                previous.status = "discarded"
            else:
                previous.adopted = []
            session.add(previous)
        samples = list(session.exec(select(Sample).where(Sample.persona_id == host.persona_id)))
        dials = Dials(**(host.dials or {}))
        control = resolve(
            dials,
            persona,
            host.prompt,
            default_revisions=services.settings.revision_passes,
            words_per_image=(voice_profile.baseline_stylometrics or {}).get("words_per_image"),
        )
        chooser = random.SystemRandom()
        seed = chooser.randrange(2**31)
        challenger = build_challenger(
            seed=seed,
            control=control,
            dials=dials,
            persona=persona,
            voice_profile=voice_profile,
            samples=samples,
            prompt=host.prompt,
            brand_kit=host.brand_kit,
        )
        test = ABTest(
            project_id=project_id,
            persona_id=host.persona_id,
            seed=seed,
            left_role=chooser.choice(ROLES),
            tweaks=challenger.tweaks,
            emphasis=challenger.emphasis,
            exemplar_ids=challenger.exemplar_ids,
        )
        session.add(test)
        session.flush()
        variants = {
            "control": Project(dials=dict(host.dials or {}), brand_kit=dict(host.brand_kit or {}), **_variant_base(host, test, "control")),
            "challenger": Project(
                dials=challenger.dials.model_dump(exclude_none=True),
                brand_kit=challenger.brand_kit,
                **_variant_base(host, test, "challenger"),
            ),
        }
        session.add_all(variants.values())
        session.flush()
        test.control_project_id, test.challenger_project_id = variants["control"].id, variants["challenger"].id
        session.add(test)
        session.commit()
        test_id = test.id
    assert test_id is not None
    return await services.jobs.start("ab_generate", lambda ctx: run_ab_test(services, test_id, ctx), project_id=project_id)


def _variant_base(host: Project, test: ABTest, role: str) -> dict[str, Any]:
    return {
        "persona_id": host.persona_id,
        "prompt": host.prompt,
        "title": host.title,
        "pinned_titles": list(host.pinned_titles or []),
        "ab_test_id": test.id,
        "variant": role,
    }


async def retry_ab_test(services: Services, test_id: int) -> Job:
    """Write again whichever of the two posts failed."""
    with Session(services.engine) as session:
        test = session.get(ABTest, test_id)
        if test is None:
            raise ABTestError("A/B test not found.")
        if test.status != "error" or test.control_project_id is None or test.challenger_project_id is None:
            raise ABTestError("This A/B test has nothing to retry.")
        if services.jobs.active_for(project_id=test.project_id, kinds=TEXT_JOBS):
            raise ABTestError("Claude is still working on this post. Wait for it to finish.")
        test.status, test.error = "generating", None
        session.add(test)
        session.commit()
        project_id = test.project_id
    return await services.jobs.start("ab_generate", lambda ctx: run_ab_test(services, test_id, ctx), project_id=project_id)


class LaneReporter:
    """One variant's progress, re-sent on the shared job as ``lane`` events so the page can show two columns.

    Lanes are positions ("left" = Post 1), never roles: nothing sent while the test is open says which post is which.
    """

    def __init__(self, ctx: JobContext, lane: str, fractions: dict[str, float]) -> None:
        self._ctx, self._lane, self._fractions = ctx, lane, fractions

    async def progress(self, fraction: float, message: str) -> None:
        self._fractions[self._lane] = fraction
        await self._ctx.emit("lane", {"lane": self._lane, "type": "progress", "data": {"progress": fraction, "message": message}})
        await self._ctx.progress(sum(self._fractions.values()) / len(self._fractions), "Writing two versions of your post")

    async def emit(self, event_type: str, data: Any) -> None:
        await self._ctx.emit("lane", {"lane": self._lane, "type": event_type, "data": data})

    def add_usage(self, usage: dict[str, int]) -> None:
        self._ctx.add_usage(usage)


async def run_ab_test(services: Services, test_id: int, ctx: JobContext) -> dict[str, Any]:
    """The ``ab_generate`` job: write both variants at once (only the unfinished ones on a retry)."""
    with Session(services.engine) as session:
        test = session.get(ABTest, test_id)
        if test is None:
            raise ABTestError("A/B test not found.")
        todo: dict[str, int] = {}
        for role in ROLES:
            project = session.get(Project, variant_id(test, role) or 0)
            if project is None:
                raise ABTestError("This A/B test's posts are gone. Start a new one.")
            if project.status != "ready":
                assert project.id is not None
                todo[role] = project.id
        left_role = test.left_role
        variation = Variation(exemplar_ids=list(test.exemplar_ids or []), emphasis=test.emphasis)
    fractions = {("left" if role == left_role else "right"): 0.0 for role in todo}

    async def write(role: str, project_id: int) -> None:
        lane = "left" if role == left_role else "right"
        await generate_article(
            engine=services.engine,
            llm=services.llm,
            settings=services.settings,
            images=services.images,
            project_id=project_id,
            ctx=LaneReporter(ctx, lane, fractions),
            links=services.links,
            variation=variation if role == "challenger" else None,
        )

    await ctx.progress(0.01, "Writing two versions of your post")
    results = await asyncio.gather(*(write(role, pid) for role, pid in todo.items()), return_exceptions=True)
    failures = [r for r in results if isinstance(r, BaseException)]
    with Session(services.engine) as session:
        row = session.get(ABTest, test_id)
        if row is None:
            raise ABTestError("A/B test not found.")
        row.status = "error" if failures else "voting"
        row.error = str(failures[0])[:2000] if failures else None
        session.add(row)
        session.commit()
    if failures:
        raise ABTestError(f"One of the two posts could not be written: {failures[0]}")
    await ctx.progress(1.0, "Both posts are ready to compare")
    return {"project_id": test.project_id, "ab_test_id": test_id}


# -- deciding ---------------------------------------------------------------------------


async def start_decision(services: Services, test_id: int, *, winner: str, take: list[str], notes: str) -> Job:
    """Start the ``ab_decide`` job: ``winner`` is "left" or "right"; ``take`` lists parts wanted from the other post."""
    with Session(services.engine) as session:
        test = session.get(ABTest, test_id)
        if test is None:
            raise ABTestError("A/B test not found.")
        if test.status != "voting":
            raise ABTestError("This A/B test is not waiting for a winner.")
        if services.jobs.active_for(project_id=test.project_id, kinds=TEXT_JOBS):
            raise ABTestError("Claude is still working on this post. Wait for it to finish.")
        test.status = "deciding"
        session.add(test)
        session.commit()
        project_id = test.project_id
    parts = [p for p in PARTS if p in take]
    return await services.jobs.start(
        "ab_decide",
        lambda ctx: decide(services, test_id, role_side=winner, take=parts, notes=notes.strip(), ctx=ctx),
        project_id=project_id,
    )


async def decide(services: Services, test_id: int, *, role_side: str, take: list[str], notes: str, ctx: JobContext) -> dict[str, Any]:
    try:
        return await _decide(services, test_id, role_side=role_side, take=take, notes=notes, ctx=ctx)
    except Exception:
        # Nothing was committed before the failure: the author can choose again.
        with Session(services.engine) as session:
            row = session.get(ABTest, test_id)
            if row is not None and row.status == "deciding":
                row.status = "voting"
                session.add(row)
                session.commit()
        raise


def _move_image(session: Session, storage: Storage, image: ProjectImage, host_id: int, slot_id: str | None = None) -> None:
    """Give an image (row, file and redraw history) to the host project."""
    source, target = storage.image_dir(image.project_id), storage.image_dir(host_id)
    names = {image.file_name, *(entry.get("file_name") for entry in image.history or [])}
    for name in names:
        if name and (source / name).exists():
            shutil.move(str(source / name), str(target / name))
    image.project_id = host_id
    if slot_id:
        image.slot_id = slot_id
    session.add(image)


async def _decide(services: Services, test_id: int, *, role_side: str, take: list[str], notes: str, ctx: JobContext) -> dict[str, Any]:
    engine, storage = services.engine, services.storage
    await ctx.progress(0.05, "Making the winner your post")
    with Session(engine, expire_on_commit=False) as session:
        test = session.get(ABTest, test_id)
        if test is None:
            raise ABTestError("A/B test not found.")
        winner_role = role_of(test, role_side)
        host = session.get(Project, test.project_id)
        winner = session.get(Project, variant_id(test, winner_role) or 0)
        loser = session.get(Project, variant_id(test, other(winner_role)) or 0)
        if host is None or winner is None or loser is None or host.id is None or winner.id is None or loser.id is None:
            raise ABTestError("This A/B test's posts are gone. Start a new one.")
        persona = session.get(Persona, host.persona_id)
        voice_profile = current_voice_profile(session, host.persona_id)
        if persona is None or voice_profile is None:
            raise ABTestError("The post's persona or voice profile no longer exists.")
        samples = list(session.exec(select(Sample).where(Sample.persona_id == host.persona_id)))

        # 1. The text: the winner's, with the parts taken from the other post spliced in.
        markdown = winner.markdown
        moved: dict[str, str] = {}
        dropped: list[str] = []
        if "title" in take:
            markdown = take_title(markdown, loser.markdown)
        for part, splice in (("opener", take_opener), ("closer", take_closer)):
            if part in take:
                result = splice(markdown, loser.markdown)
                markdown = result.markdown
                moved.update(result.moved)
                dropped += result.dropped
        spliced = markdown != winner.markdown

        # 2. The images: the winner's, minus those in replaced text, plus those that came with the other post's parts.
        session.exec(delete(ProjectImage).where(col(ProjectImage.project_id) == host.id))  # type: ignore[call-overload]
        session.exec(delete(ProjectReference).where(col(ProjectReference.project_id) == host.id))  # type: ignore[call-overload]
        theirs = {i.slot_id: i for i in session.exec(select(ProjectImage).where(ProjectImage.project_id == loser.id))}
        swapped = [slot for slot in ("hero", "meme") if slot in take and slot in theirs]
        for image in list(session.exec(select(ProjectImage).where(ProjectImage.project_id == winner.id))):
            if image.slot_id in dropped or image.slot_id in swapped:
                session.delete(image)
            else:
                _move_image(session, storage, image, host.id)
        for old, new in moved.items():
            if old in theirs:
                _move_image(session, storage, theirs[old], host.id, new)
        for slot in swapped:
            _move_image(session, storage, theirs[slot], host.id)
        for reference in session.exec(select(ProjectReference).where(ProjectReference.project_id == winner.id)):
            reference.project_id = host.id
            session.add(reference)
        session.flush()
        images = list(session.exec(select(ProjectImage).where(ProjectImage.project_id == host.id)))
        order = [m.group(1) for m in PLACEHOLDER_RE.finditer(markdown)]
        for image in images:
            image.position = order.index(image.slot_id) if image.slot_id in order else len(order)
            session.add(image)

        # 3. The plan follows the images, so later tweaks keep every placeholder.
        plan = dict(winner.plan or {})
        their_slots = {s.get("slot_id"): s for s in (loser.plan or {}).get("image_slots", [])}
        slots = [s for s in plan.get("image_slots", []) if s.get("slot_id") not in dropped]
        slots = [their_slots.get(s.get("slot_id"), s) if s.get("slot_id") in swapped else s for s in slots]
        slots += [{**their_slots[old], "slot_id": new} for old, new in moved.items() if old in their_slots]
        meme = [s for s in slots if s.get("slot_id") == "meme"]
        plan["image_slots"] = [s for s in slots if s.get("slot_id") != "meme"] + meme
        title, subtitle = split_title(markdown)
        if "title" in take:
            plan["chosen_title"], plan["subtitle"] = title or loser.title, subtitle or loser.subtitle
            plan["title_options"] = [*dict.fromkeys([plan["chosen_title"], *plan.get("title_options", [])])]

        brand_kit = dict((loser if "image_style" in take else winner).brand_kit or {})
        host.markdown = markdown
        host.title, host.subtitle = title or winner.title, subtitle or winner.subtitle
        host.plan, host.critique, host.social = plan, winner.critique, None
        host.fidelity = measure(markdown, voice_profile.baseline_stylometrics) if spliced else winner.fidelity
        host.authenticity = winner.authenticity
        host.dials, host.brand_kit = dict(winner.dials or {}), brand_kit
        host.voice_profile_version = winner.voice_profile_version
        host.revisions, host.status, host.error = [], "ready", None
        host.baseline_markdown, host.baseline_title = markdown, host.title
        host.updated_at = utcnow()
        session.add(host)

        loser_markdown = loser.markdown
        delete_variants(session, storage, test)
        test.status, test.winner, test.taken, test.decided_at = "decided", winner_role, take, utcnow()
        # Nothing of the challenger was kept: there is nothing to adopt.
        if not suggested_tweaks(test):
            test.adopted = []
        session.add(test)
        session.commit()
        host_id = host.id
        # Images that came from the other post already have its look.
        theirs_now = {*moved.values(), *swapped}
        restyle = [i.id for i in images if i.id is not None and i.kind != "meme" and i.slot_id not in theirs_now]

    # 4. "Image style" from the other post: its look, drawn for this post's images.
    if "image_style" in take and restyle:
        await ctx.progress(0.2, f"Redrawing {len(restyle)} images in the other post's style")
        semaphore = asyncio.Semaphore(3)

        async def redraw(image_id: int) -> None:
            async with semaphore:
                await services.images.create(
                    image_id,
                    persona=persona,
                    title=title,
                    markdown=markdown,
                    voice_profile=voice_profile.markdown,
                    redraw=True,
                    brand_kit=brand_kit,
                    usage=ctx.add_usage,
                )
            await ctx.emit("image_ready", {"image_id": image_id})

        await asyncio.gather(*(redraw(i) for i in restyle), return_exceptions=True)

    # 5. The author's note, as a normal tweak that can see the other post. A note that cannot be applied never undoes the choice.
    notes_error: str | None = None
    if notes:
        try:
            await tweak_post(
                engine=engine,
                llm=services.llm,
                settings=services.settings,
                images=services.images,
                project_id=host_id,
                feedback=notes,
                ctx=ctx,
                other_post=loser_markdown,
                learn=False,
            )
        except (WriterError, LLMError) as exc:
            notes_error = str(exc)
    elif spliced:
        try:
            await ctx.progress(0.8, "Checking how human the post reads")
            authenticity = await analyze(
                llm=services.llm,
                settings=services.settings,
                markdown=markdown,
                voice_profile=voice_profile.markdown,
                profile=author_profile(samples, voice_profile.baseline_stylometrics),
                use_judge=services.settings.ai_detection,
                usage=ctx.add_usage,
            )
        except LLMError:
            log.warning("Could not re-check the blended post; keeping the winner's report")
        else:
            _save_host(engine, host_id, authenticity=authenticity)

    # What the app generated, blend and note included: later edits by hand are measured against this (see evolution).
    with Session(engine) as session:
        row = session.get(Project, host_id)
        if row is not None:
            row.baseline_markdown, row.baseline_title, row.revisions = row.markdown, row.title, []
            session.add(row)
            session.commit()
    await ctx.progress(1.0, "Your post is ready")
    return {"project_id": host_id, "ab_test_id": test_id, "winner": winner_role, "notes_error": notes_error}


def _save_host(engine: Engine, project_id: int, **fields: Any) -> None:
    with Session(engine) as session:
        row = session.get(Project, project_id)
        if row is None:
            return
        for key, value in fields.items():
            setattr(row, key, value)
        session.add(row)
        session.commit()


def discard(session: Session, services: Services, test: ABTest) -> None:
    """Drop an open test and both its posts; the host project stays exactly as it was."""
    if test.status in ("decided", "discarded"):
        raise ABTestError("This A/B test is already closed.")
    if services.jobs.active_for(project_id=test.project_id, kinds=TEXT_JOBS):
        raise ABTestError("Claude is still working on this post. Wait for it to finish.")
    delete_variants(session, services.storage, test)
    test.status = "discarded"
    session.add(test)
    session.commit()


# -- adopting ---------------------------------------------------------------------------

_PERSONA_FIELDS = (
    "default_humor",
    "default_storytelling",
    "default_opinion",
    "default_formality",
    "default_technical_depth",
    "default_skimmability",
    "default_education",
    "default_image_count",
    "default_reference_count",
    "visual_style",
)
_FORMULA_FIELDS = ("opener", "body", "closer")


async def adopt(services: Services, test_id: int, tweak_ids: list[str]) -> Job | None:
    """Make the chosen tweaks the persona's way of writing; an empty list keeps the persona as it is.

    Dials, formula parts and the image style become persona defaults; example tweaks raise a sample's weight; voice,
    principle and title tweaks go through persona evolution into a new voice profile version (the returned job).
    """
    with Session(services.engine) as session:
        test = session.get(ABTest, test_id)
        if test is None:
            raise ABTestError("A/B test not found.")
        if test.status != "decided" or test.adopted is not None:
            raise ABTestError("This A/B test has nothing left to adopt.")
        persona = session.get(Persona, test.persona_id)
        host = session.get(Project, test.project_id)
        if persona is None:
            raise ABTestError("The persona no longer exists.")
        chosen = [t for t in test.tweaks or [] if t.get("id") in tweak_ids]
        formula = dict(persona.default_formula or {})
        profile_items: list[dict[str, Any]] = []
        for tweak in chosen:
            target, name, value = tweak.get("target"), str(tweak.get("field") or ""), tweak.get("value")
            if target == "persona" and name in _PERSONA_FIELDS:
                setattr(persona, name, value)
            elif target == "persona" and name in _FORMULA_FIELDS:
                formula[name] = value
            elif target == "sample":
                sample = session.get(Sample, tweak.get("sample_id") or 0)
                if sample is not None and sample.persona_id == persona.id and isinstance(value, (int, float)):
                    sample.weight = max(sample.weight or 1.0, float(value))
                    session.add(sample)
            elif target == "profile" and tweak.get("change"):
                profile_items.append(
                    {
                        "id": tweak["id"],
                        "area": str(tweak.get("group", "")),
                        "change": str(tweak["change"]),
                        "evidence": EVIDENCE,
                        "target": "profile",
                        "applied": False,
                    }
                )
        persona.default_formula = clean_formula(formula)
        persona.updated_at = utcnow()
        session.add(persona)
        evolution_id: int | None = None
        voice_profile = current_voice_profile(session, test.persona_id)
        if profile_items and voice_profile is not None:
            evolution = PersonaEvolution(
                persona_id=test.persona_id,
                project_id=test.project_id,
                kind="ab_test",
                project_title=host.title if host else "",
                state="pending",
                summary="What won your blind A/B test.",
                items=profile_items,
                voice_profile_version=voice_profile.version,
            )
            session.add(evolution)
            session.flush()
            evolution_id = evolution.id
        test.adopted = [t["id"] for t in chosen]
        test.evolution_id = evolution_id
        session.add(test)
        session.commit()
    if evolution_id is None:
        return None
    return await start_apply(services, evolution_id, [item["id"] for item in profile_items])
