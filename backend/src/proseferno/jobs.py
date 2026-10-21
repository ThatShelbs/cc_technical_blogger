"""Background jobs with live progress.

Long LLM work (voice synthesis, article generation, image redraws) runs as an
asyncio task. Status is persisted in the ``job`` table; fine-grained events
(progress, streamed draft text) are kept in memory and replayed to any SSE
subscriber, so a browser that reconnects mid-job catches up.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Engine
from sqlmodel import Session, select

from proseferno.db import Job, utcnow

log = logging.getLogger(__name__)

TERMINAL = {"succeeded", "failed"}


@dataclass
class _Channel:
    events: list[dict[str, Any]] = field(default_factory=list)
    changed: asyncio.Event = field(default_factory=asyncio.Event)
    done: bool = False

    def push(self, event_type: str, data: Any) -> None:
        self.events.append({"seq": len(self.events), "type": event_type, "data": data})
        self.changed.set()


class JobContext:
    """Handed to a job function so it can report progress and stream output."""

    def __init__(self, manager: JobManager, job_id: str) -> None:
        self._manager = manager
        self.job_id = job_id
        self.usage: dict[str, int] = {}

    async def progress(self, fraction: float, message: str) -> None:
        fraction = max(0.0, min(1.0, fraction))
        self._manager._update(self.job_id, progress=fraction, message=message)
        self._manager._channel(self.job_id).push("progress", {"progress": fraction, "message": message})

    async def emit(self, event_type: str, data: Any) -> None:
        self._manager._channel(self.job_id).push(event_type, data)

    def add_usage(self, usage: dict[str, int]) -> None:
        for key, value in usage.items():
            self.usage[key] = self.usage.get(key, 0) + int(value or 0)


JobFn = Callable[[JobContext], Awaitable[dict[str, Any] | None]]


class JobManager:
    def __init__(self, engine: Engine, *, inline: bool = False) -> None:
        self.engine = engine
        # Inline mode awaits the job before returning (deterministic tests).
        self.inline = inline
        self._channels: dict[str, _Channel] = {}
        self._tasks: set[asyncio.Task[None]] = set()
        self._mark_interrupted()

    async def start(
        self,
        kind: str,
        fn: JobFn,
        *,
        persona_id: int | None = None,
        project_id: int | None = None,
    ) -> Job:
        with Session(self.engine) as session:
            job = Job(kind=kind, persona_id=persona_id, project_id=project_id)
            session.add(job)
            session.commit()
            session.refresh(job)
        self._channels[job.id] = _Channel()
        if self.inline:
            await self._run(job.id, fn)
        else:
            task = asyncio.create_task(self._run(job.id, fn))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        return self.get(job.id)

    def get(self, job_id: str) -> Job:
        with Session(self.engine) as session:
            job = session.get(Job, job_id)
            if job is None:
                raise KeyError(job_id)
            return job

    def active_for(self, *, persona_id: int | None = None, project_id: int | None = None) -> list[Job]:
        with Session(self.engine) as session:
            query = select(Job).where(Job.status.in_(["queued", "running"]))  # type: ignore[attr-defined]
            if persona_id is not None:
                query = query.where(Job.persona_id == persona_id)
            if project_id is not None:
                query = query.where(Job.project_id == project_id)
            return list(session.exec(query))

    async def events(self, job_id: str, after: int = -1) -> AsyncIterator[dict[str, Any]]:
        """Yield events with seq > ``after`` until the job finishes."""
        channel = self._channels.get(job_id)
        if channel is None:
            # Job from a previous run (or unknown): report its final status once.
            job = self.get(job_id)
            yield {"seq": 0, "type": "status", "data": _status_payload(job)}
            return
        cursor = after + 1
        while True:
            while cursor < len(channel.events):
                yield channel.events[cursor]
                cursor += 1
            if channel.done:
                return
            channel.changed.clear()
            await channel.changed.wait()

    async def shutdown(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    # -- internals -------------------------------------------------------

    async def _run(self, job_id: str, fn: JobFn) -> None:
        ctx = JobContext(self, job_id)
        channel = self._channel(job_id)
        self._update(job_id, status="running")
        channel.push("status", {"status": "running"})
        try:
            result = await fn(ctx)
        except asyncio.CancelledError:
            self._update(job_id, status="failed", error="Cancelled", usage=ctx.usage)
            raise
        except Exception as exc:
            log.exception("Job %s failed", job_id)
            self._update(job_id, status="failed", error=_friendly_error(exc), usage=ctx.usage)
        else:
            self._update(job_id, status="succeeded", progress=1.0, result=result or {}, usage=ctx.usage)
        finally:
            channel.push("status", _status_payload(self.get(job_id)))
            channel.done = True
            channel.changed.set()

    def _channel(self, job_id: str) -> _Channel:
        return self._channels.setdefault(job_id, _Channel())

    def _update(self, job_id: str, **fields: Any) -> None:
        with Session(self.engine) as session:
            job = session.get(Job, job_id)
            if job is None:
                return
            for key, value in fields.items():
                setattr(job, key, value)
            job.updated_at = utcnow()
            session.add(job)
            session.commit()

    def _mark_interrupted(self) -> None:
        with Session(self.engine) as session:
            stale = session.exec(select(Job).where(Job.status.in_(["queued", "running"])))  # type: ignore[attr-defined]
            for job in stale:
                job.status = "failed"
                job.error = "Interrupted because Proseferno was restarted."
                session.add(job)
            session.commit()


def _status_payload(job: Job) -> dict[str, Any]:
    return {"status": job.status, "error": job.error, "result": job.result, "progress": job.progress}


def _friendly_error(exc: Exception) -> str:
    message = str(exc) or exc.__class__.__name__
    return message[:2000]
