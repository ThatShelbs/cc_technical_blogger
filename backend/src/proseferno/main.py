"""FastAPI application factory and static frontend hosting."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from proseferno import __version__
from proseferno.api import jobs, personas, projects, system
from proseferno.config import Settings, get_settings
from proseferno.services import Services, build_services

log = logging.getLogger("proseferno")

NOT_BUILT = """<!doctype html><html><head><meta charset="utf-8"><title>Proseferno</title></head>
<body style="font-family:system-ui;background:#1b0c41;color:#fcffa4;padding:48px">
<h1>Proseferno API is running</h1>
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
        yield
        await services.jobs.shutdown()

    app = FastAPI(title="Proseferno", version=__version__, lifespan=lifespan)
    app.state.services = services
    for module in (system, personas, projects, jobs):
        app.include_router(module.router)
    _mount_frontend(app, settings.frontend_dist)
    return app


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
