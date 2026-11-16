"""Health, Claude sign-in, and app settings."""

from __future__ import annotations

import asyncio
import dataclasses
from typing import Any

import anthropic
from fastapi import APIRouter, HTTPException
from sqlmodel import Session, col, select

from proseferno import __version__
from proseferno.api.deps import ServicesDep
from proseferno.api.schemas import (
    ApiKeyIn,
    AuthStatusOut,
    AuthTestOut,
    DetectorStatusOut,
    Health,
    JobOut,
    SettingsIn,
    SettingsOut,
)
from proseferno.authenticity import local_detector
from proseferno.db import Job
from proseferno.images import model_label
from proseferno.jobs import JobContext
from proseferno.llm import LLMNotConfiguredError
from proseferno.services import RUNTIME_SETTINGS

router = APIRouter(prefix="/api")


@router.get("/health", response_model=Health)
def health(services: ServicesDep) -> Health:
    return Health(version=__version__, demo=services.settings.demo)


# -- auth ------------------------------------------------------------------------


def _status(services: ServicesDep) -> AuthStatusOut:
    return AuthStatusOut(**dataclasses.asdict(services.auth.status(services.settings.claude_connection)))


@router.get("/auth/status", response_model=AuthStatusOut)
def auth_status(services: ServicesDep) -> AuthStatusOut:
    return _status(services)


@router.post("/auth/login", response_model=AuthStatusOut)
def auth_login(services: ServicesDep) -> AuthStatusOut:
    """Start 'Sign in with Claude' (browser OAuth through the Anthropic CLI)."""
    if services.settings.demo:
        raise HTTPException(409, "Sign-in is disabled in demo mode.")
    try:
        services.auth.start_login()
    except FileNotFoundError as exc:
        raise HTTPException(409, str(exc)) from exc
    return _status(services)


@router.post("/auth/claude-code/login", response_model=AuthStatusOut)
def claude_code_login(services: ServicesDep) -> AuthStatusOut:
    """Start Claude Code's own sign-in, which uses the person's Claude Pro/Max plan."""
    if services.settings.demo:
        raise HTTPException(409, "Sign-in is disabled in demo mode.")
    try:
        services.auth.start_claude_code_login()
    except FileNotFoundError as exc:
        raise HTTPException(409, str(exc)) from exc
    return _status(services)


@router.post("/auth/logout", response_model=AuthStatusOut)
def auth_logout(services: ServicesDep) -> AuthStatusOut:
    services.auth.logout()
    return _status(services)


@router.put("/auth/api-key", response_model=AuthStatusOut)
def save_api_key(body: ApiKeyIn, services: ServicesDep) -> AuthStatusOut:
    services.auth.set_api_key(body.api_key)
    return _status(services)


@router.delete("/auth/api-key", response_model=AuthStatusOut)
def delete_api_key(services: ServicesDep) -> AuthStatusOut:
    services.auth.clear_api_key()
    return _status(services)


@router.post("/auth/test", response_model=AuthTestOut)
async def test_auth(services: ServicesDep) -> AuthTestOut:
    """Check the credentials with a free metadata call (no tokens used)."""
    if services.settings.demo:
        return AuthTestOut(ok=True, message="Demo mode: Claude is simulated.")
    if services.settings.claude_connection == "subscription":
        services.auth.claude_code.forget_status()
        status = services.auth.status("subscription")
        ok = status.claude_code_signed_in and status.claude_code_auth_method == "claude.ai"
        return AuthTestOut(ok=ok, message=status.detail)
    try:
        client = services.auth.build_client()
        model = await client.models.retrieve(services.settings.model)
    except LLMNotConfiguredError as exc:
        return AuthTestOut(ok=False, message=str(exc))
    except anthropic.AuthenticationError:
        return AuthTestOut(ok=False, message="Claude rejected these credentials.")
    except anthropic.NotFoundError:
        return AuthTestOut(ok=False, message=f"Signed in, but model '{services.settings.model}' is not available to this account.")
    except anthropic.APIError as exc:
        return AuthTestOut(ok=False, message=f"Could not verify: {exc}")
    return AuthTestOut(ok=True, message=f"Connected. Using {model.display_name}.")


# -- settings ----------------------------------------------------------------------


def _settings_out(services: ServicesDep) -> SettingsOut:
    s = services.settings
    return SettingsOut(
        claude_connection=s.claude_connection,
        model=s.model,
        use_fallbacks=s.use_fallbacks,
        revision_passes=s.revision_passes,
        ai_detection=s.ai_detection,
        deep_check=s.deep_check,
        humanize_rounds=s.humanize_rounds,
        reference_max_searches=s.reference_max_searches,
        check_reference_links=s.check_reference_links,
        image_tool_label=f"{model_label(s.model)}: SVG illustrations, icons and diagrams; Vega-Lite charts",
        data_dir=str(s.data_dir),
        seed_samples_dir=str(s.seed_samples_dir),
        version=__version__,
        demo=s.demo,
    )


@router.get("/settings", response_model=SettingsOut)
def get_settings(services: ServicesDep) -> SettingsOut:
    return _settings_out(services)


@router.put("/settings", response_model=SettingsOut)
def update_settings(body: SettingsIn, services: ServicesDep) -> SettingsOut:
    for key in RUNTIME_SETTINGS:
        value = getattr(body, key)
        if value is not None:
            services.save_runtime_setting(key, value.strip() if isinstance(value, str) else value)
    return _settings_out(services)


# -- local AI-text detector models -----------------------------------------------------

DETECTOR_SETUP_JOB = "detector_setup"


def _detector_out(services: ServicesDep) -> DetectorStatusOut:
    state = local_detector.status(services.settings)
    # The latest setup while it runs, or when it failed (so the author sees why); a finished one shows as "ready".
    with Session(services.engine) as session:
        latest = session.exec(select(Job).where(Job.kind == DETECTOR_SETUP_JOB).order_by(col(Job.created_at).desc())).first()
    job = JobOut(**latest.model_dump()) if latest is not None and latest.status != "succeeded" else None
    return DetectorStatusOut(**state, job=job)


@router.get("/detector", response_model=DetectorStatusOut)
def detector_status(services: ServicesDep) -> DetectorStatusOut:
    return _detector_out(services)


@router.post("/detector/setup", response_model=DetectorStatusOut, status_code=202)
async def setup_detector(services: ServicesDep) -> DetectorStatusOut:
    """Install the detector packages and download the models once (about 1.3 GB), then turn the detectors on."""
    state = local_detector.status(services.settings)
    if not state["available"]:
        raise HTTPException(409, state["detail"])
    if not services.jobs.active_for(kinds=(DETECTOR_SETUP_JOB,)):

        async def run(ctx: JobContext) -> dict[str, Any]:
            await ctx.progress(0.05, "Installing PyTorch and downloading the detector models (one time, about 1.3 GB)")
            if not services.settings.demo:
                await asyncio.to_thread(local_detector.setup_detector, services.settings)
            services.save_runtime_setting("deep_check", True)
            await ctx.progress(1.0, "The detector models are ready")
            return {"ready": True}

        await services.jobs.start(DETECTOR_SETUP_JOB, run)
    return _detector_out(services)
