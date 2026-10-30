"""The example persona: a finished voice profile and post to look at before setting up your own.

Everything is built offline by running the real voice and writing pipelines against
``demo.FakeLLM``, so it costs nothing, needs no Claude connection, and cannot drift from
how the app really stores a persona, a voice profile, a post and its credited images.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from sqlmodel import Session, col, select

from proseferno.db import Persona, Project, VoiceProfile
from proseferno.demo import FakeLLM
from proseferno.images import ImageService
from proseferno.ingest import parse_file
from proseferno.jobs import JobContext
from proseferno.personas import add_sample, delete_persona_data
from proseferno.sample_content import SAMPLE_AUTHOR, example_voice_profile, sample_posts
from proseferno.services import Services
from proseferno.voice import generate_voice_profile
from proseferno.writer import generate_article

EXAMPLE_PROMPT = "Why pie charts are lame and what to use instead"
EXAMPLE_LABEL = "Example voice profile"


class ExampleError(RuntimeError):
    pass


def find_example(session: Session) -> Persona | None:
    return session.exec(select(Persona).where(Persona.is_example == True)).first()  # noqa: E712


async def _run(services: Services, kind: str, fn: Callable[[JobContext], Awaitable[dict[str, Any] | None]], **ids: int) -> None:
    """Run a job through the app's own job manager and wait for it to finish."""
    job = await services.jobs.start(kind, fn, **ids)
    async for _ in services.jobs.events(job.id):
        pass
    final = services.jobs.get(job.id)
    if final.status != "succeeded":
        raise ExampleError(final.error or f"The example {kind} job did not finish.")


async def seed_example(services: Services, *, activate: bool) -> int:
    """Create the example persona, its samples, voice profile and one finished post. Returns the persona id.

    ``activate`` turns the persona on, so New post works as it is; otherwise it is only for looking at.
    Calling this again returns the existing example.
    """
    with Session(services.engine) as session:
        existing = find_example(session)
        if existing and existing.id is not None:
            return existing.id
        if activate:
            for other in session.exec(select(Persona).where(Persona.is_active == True)):  # noqa: E712
                other.is_active = False
                session.add(other)
        persona = Persona(name=SAMPLE_AUTHOR, display_name=SAMPLE_AUTHOR, is_example=True, is_active=activate)
        session.add(persona)
        session.commit()
        session.refresh(persona)
        assert persona.id is not None
        persona_id = persona.id

    fake = FakeLLM()
    try:
        with Session(services.engine) as session:
            for name, data in sample_posts():
                add_sample(session, persona_id, "own", name, parse_file(name, data))
        await _run(
            services,
            "voice_profile",
            lambda ctx: generate_voice_profile(
                engine=services.engine,
                llm=fake,
                settings=services.settings,
                storage=services.storage,
                persona_id=persona_id,
                ctx=ctx,
                label=EXAMPLE_LABEL,
            ),
            persona_id=persona_id,
        )
        _use_written_voice_profile(services, persona_id)

        with Session(services.engine) as session:
            project = Project(persona_id=persona_id, prompt=EXAMPLE_PROMPT, title=EXAMPLE_PROMPT)
            session.add(project)
            session.commit()
            session.refresh(project)
            assert project.id is not None
            project_id = project.id
        images = ImageService(engine=services.engine, llm=fake, settings=services.settings, storage=services.storage)
        await _run(
            services,
            "generate_post",
            lambda ctx: generate_article(
                engine=services.engine,
                llm=fake,
                settings=services.settings,
                images=images,
                project_id=project_id,
                ctx=ctx,
            ),
            project_id=project_id,
        )
    except Exception:
        remove_example(services)
        raise
    return persona_id


def _use_written_voice_profile(services: Services, persona_id: int) -> None:
    """Swap the canned test profile for the hand-written one, which shows what a real profile holds."""
    markdown = example_voice_profile()
    with Session(services.engine) as session:
        profile = session.exec(select(VoiceProfile).where(VoiceProfile.persona_id == persona_id)).one()
        profile.markdown = markdown
        session.add(profile)
        session.commit()
        services.storage.voice_profile_path(persona_id, profile.version).write_text(markdown, encoding="utf-8")


def remove_example(services: Services) -> bool:
    """Delete the example persona and everything built for it. False if there was none."""
    with Session(services.engine) as session:
        persona = find_example(session)
        if persona is None:
            return False
        was_active = delete_persona_data(session, services.storage, persona)
        if was_active:
            remaining = session.exec(select(Persona).order_by(col(Persona.created_at))).first()
            if remaining is not None:
                remaining.is_active = True
                session.add(remaining)
                session.commit()
    return True
