"""Wiring: one place that builds every long-lived service the API uses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import Engine
from sqlmodel import Session

from proseferno.config import Settings
from proseferno.db import AppSetting, make_engine
from proseferno.images import CloudflareFluxProvider, ImageService, RasterProvider
from proseferno.jobs import JobManager
from proseferno.llm import LLM
from proseferno.llm.auth import ClaudeAuth
from proseferno.llm.claude import ClaudeLLM
from proseferno.secrets import CLOUDFLARE_API_TOKEN, KeyringSecretStore, SecretStore
from proseferno.storage import Storage

# Settings the user can change in the app; persisted in the app_setting table.
RUNTIME_SETTINGS = ("model", "use_fallbacks", "revision_passes", "cloudflare_account_id")


@dataclass
class Services:
    settings: Settings
    engine: Engine
    storage: Storage
    secrets: SecretStore
    auth: ClaudeAuth
    llm: LLM
    raster: RasterProvider
    images: ImageService
    jobs: JobManager

    def save_runtime_setting(self, key: str, value: Any) -> None:
        if key not in RUNTIME_SETTINGS:
            raise KeyError(key)
        setattr(self.settings, key, value)
        with Session(self.engine) as session:
            row = session.get(AppSetting, key) or AppSetting(key=key)
            row.value = value
            session.add(row)
            session.commit()


def load_runtime_settings(engine: Engine, settings: Settings) -> None:
    with Session(engine) as session:
        for key in RUNTIME_SETTINGS:
            row = session.get(AppSetting, key)
            if row is not None and row.value is not None:
                setattr(settings, key, row.value)


def build_services(
    settings: Settings,
    *,
    secrets: SecretStore | None = None,
    llm: LLM | None = None,
    raster: RasterProvider | None = None,
    auth: ClaudeAuth | None = None,
    inline_jobs: bool = False,
) -> Services:
    engine = make_engine(settings.db_path)
    load_runtime_settings(engine, settings)
    storage = Storage(settings.data_dir)
    if settings.demo:
        from proseferno.demo import FakeLLM, FakeRaster
        from proseferno.secrets import MemorySecretStore

        secrets = secrets or MemorySecretStore({"anthropic_api_key": "demo-mode"})
        llm = llm or FakeLLM(delay=0.03)
        raster = raster or FakeRaster(pretty=True)
    secrets = secrets or KeyringSecretStore(settings.keyring_service)
    auth = auth or ClaudeAuth(secrets)
    llm = llm or ClaudeLLM(settings, auth.build_client)
    raster = raster or CloudflareFluxProvider(
        account_id=lambda: settings.cloudflare_account_id,
        api_token=lambda: secrets.get(CLOUDFLARE_API_TOKEN) or settings.cloudflare_api_token,
        model=settings.cloudflare_model,
    )
    images = ImageService(engine=engine, llm=llm, settings=settings, storage=storage, raster=raster)
    jobs = JobManager(engine, inline=inline_jobs)
    return Services(
        settings=settings,
        engine=engine,
        storage=storage,
        secrets=secrets,
        auth=auth,
        llm=llm,
        raster=raster,
        images=images,
        jobs=jobs,
    )
