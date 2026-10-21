"""Job status and live progress over Server-Sent Events."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from proseferno.api.deps import ServicesDep
from proseferno.api.schemas import JobOut

router = APIRouter(prefix="/api")


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, services: ServicesDep) -> JobOut:
    try:
        return JobOut(**services.jobs.get(job_id).model_dump())
    except KeyError as exc:
        raise HTTPException(404, "Job not found.") from exc


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str, services: ServicesDep, after: int = -1) -> EventSourceResponse:
    try:
        services.jobs.get(job_id)
    except KeyError as exc:
        raise HTTPException(404, "Job not found.") from exc

    async def stream() -> AsyncIterator[dict[str, str]]:
        async for event in services.jobs.events(job_id, after=after):
            yield {"id": str(event["seq"]), "event": event["type"], "data": json.dumps(event["data"])}

    return EventSourceResponse(stream(), ping=15)
