"""Health, Claude sign-in, and app settings."""

from __future__ import annotations

import dataclasses

import anthropic
from fastapi import APIRouter, HTTPException

from proseferno import __version__
from proseferno.api.deps import ServicesDep
from proseferno.api.schemas import (
    ApiKeyIn,
    AuthStatusOut,
    AuthTestOut,
    Health,
    SettingsIn,
    SettingsOut,
)
from proseferno.llm import LLMNotConfiguredError
from proseferno.secrets import CLOUDFLARE_API_TOKEN

router = APIRouter(prefix="/api")


@router.get("/health", response_model=Health)
def health(services: ServicesDep) -> Health:
    return Health(version=__version__, demo=services.settings.demo)


# -- auth ------------------------------------------------------------------------


def _status(services: ServicesDep) -> AuthStatusOut:
    return AuthStatusOut(**dataclasses.asdict(services.auth.status()))


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
        model=s.model,
        use_fallbacks=s.use_fallbacks,
        revision_passes=s.revision_passes,
        cloudflare_account_id=s.cloudflare_account_id,
        cloudflare_configured=services.raster.is_configured(),
        image_provider_label=services.raster.label,
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
    for key in ("model", "use_fallbacks", "revision_passes", "cloudflare_account_id"):
        value = getattr(body, key)
        if value is not None:
            services.save_runtime_setting(key, value.strip() if isinstance(value, str) else value)
    if body.cloudflare_api_token:
        services.secrets.set(CLOUDFLARE_API_TOKEN, body.cloudflare_api_token.strip())
    return _settings_out(services)


@router.delete("/settings/cloudflare-token", response_model=SettingsOut)
def delete_cloudflare_token(services: ServicesDep) -> SettingsOut:
    services.secrets.delete(CLOUDFLARE_API_TOKEN)
    return _settings_out(services)
