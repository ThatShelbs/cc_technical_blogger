"""FastAPI application factory and static frontend hosting."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select

from inferno_ghostwriter import __version__
from inferno_ghostwriter.abtest.service import fail_interrupted
from inferno_ghostwriter.api import ab_tests, evolution, formulas, idea_lab, insights, jobs, personas, projects, references, system
from inferno_ghostwriter.authenticity import local_detector
from inferno_ghostwriter.config import Settings, get_settings
from inferno_ghostwriter.db import Persona
from inferno_ghostwriter.evolution import fail_analyzing
from inferno_ghostwriter.example import ExampleError, seed_example
from inferno_ghostwriter.idealab import fail_interrupted as fail_interrupted_brainstorms
from inferno_ghostwriter.services import Services, build_services
from inferno_ghostwriter.writer.references import fail_pending as fail_pending_references

log = logging.getLogger("inferno_ghostwriter")

NOT_BUILT = """<!doctype html><html><head><meta charset="utf-8"><title>Inferno Ghostwriter</title></head>
<body style="font-family:system-ui;background:#1b0c41;color:#fcffa4;padding:48px">
<h1>Inferno Ghostwriter API is running</h1>
<p>The web app has not been built yet. Run <code>launch.bat</code> (Windows) or <code>./launch.sh</code>,
or <code>npm run build</code> in <code>frontend/</code>. API docs: <a style="color:#fb9b06" href="/docs">/docs</a></p>
</body></html>"""


def create_app(settings: Settings | None = None, services: Services | None = None) -> FastAPI:
    settings = settings or get_settings()
    services = services or build_services(settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        # Jobs live in memory, so an image still "pending" at startup lost its job in a previous run.
        services.images.fail_pending()
        fail_pending_references(services.engine)
        fail_analyzing(services.engine)
        fail_interrupted(services.engine)
        fail_interrupted_brainstorms(services.engine)
        await _seed_demo(settings, services)
        yield
        await services.jobs.shutdown()
        # The detector models' worker process (if it was started) ends with the app.
        local_detector.shutdown()

    app = FastAPI(title="Inferno Ghostwriter", version=__version__, lifespan=lifespan)
    app.state.services = services
    for module in (system, personas, insights, projects, ab_tests, references, formulas, evolution, idea_lab, jobs):
        app.include_router(module.router)
    _mount_frontend(app, settings.frontend_dist)
    return app


async def _seed_demo(settings: Settings, services: Services) -> None:
    """A first demo run opens on the example persona and post instead of an empty app."""
    if not (settings.demo and settings.demo_seed):
        return
    with Session(services.engine) as session:
        if session.exec(select(Persona)).first() is not None:
            return
    try:
        await seed_example(services, activate=True)
    except ExampleError:
        log.exception("Could not build the demo example; starting empty.")


def _mount_frontend(app: FastAPI, dist: Path) -> None:
    index = dist / "index.html"
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False, response_model=None)
    def spa(path: str) -> FileResponse | HTMLResponse:
        if path.startswith("api/"):
            raise HTTPException(404, "Not found.")
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(dist.resolve()):
            return FileResponse(candidate)
        if index.is_file():
            return FileResponse(index, headers={"Cache-Control": "no-cache"})
        return HTMLResponse(NOT_BUILT)
