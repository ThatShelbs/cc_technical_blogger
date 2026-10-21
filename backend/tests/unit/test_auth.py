from __future__ import annotations

from pathlib import Path

import pytest

from proseferno.llm import LLMNotConfiguredError
from proseferno.llm.auth import ClaudeAuth
from proseferno.secrets import MemorySecretStore


def make_auth(tmp_path: Path, env: dict[str, str] | None = None, key: str | None = None) -> ClaudeAuth:
    secrets = MemorySecretStore({"anthropic_api_key": key} if key else {})
    return ClaudeAuth(secrets, env={"ANTHROPIC_CONFIG_DIR": str(tmp_path), **(env or {})}, ant_path="ant", discover_ant=False)


def sign_in(tmp_path: Path, profile: str = "default") -> None:
    creds = tmp_path / "credentials"
    creds.mkdir(exist_ok=True)
    (creds / f"{profile}.json").write_text('{"access_token": "x"}')


def test_not_signed_in(tmp_path: Path) -> None:
    auth = make_auth(tmp_path)
    status = auth.status()
    assert not status.signed_in and status.source == "none"
    with pytest.raises(LLMNotConfiguredError):
        auth.build_client()


def test_claude_sign_in_profile(tmp_path: Path) -> None:
    sign_in(tmp_path)
    status = make_auth(tmp_path).status()
    assert status.signed_in and status.source == "claude_sign_in" and status.profile == "default"


def test_active_profile_marker(tmp_path: Path) -> None:
    (tmp_path / "active_config").write_text("work\n")
    sign_in(tmp_path, "work")
    status = make_auth(tmp_path).status()
    assert status.profile == "work" and status.signed_in


def test_saved_key_wins_and_warns_about_shadowing(tmp_path: Path) -> None:
    sign_in(tmp_path)
    status = make_auth(tmp_path, key="sk-ant-test").status()
    assert status.source == "app_api_key"
    assert status.warnings


def test_env_key_shadows_profile(tmp_path: Path) -> None:
    sign_in(tmp_path)
    status = make_auth(tmp_path, env={"ANTHROPIC_API_KEY": "sk-ant-env"}).status()
    assert status.source == "env_api_key"
    assert any("overrides" in w for w in status.warnings)


def test_build_client_with_saved_key(tmp_path: Path) -> None:
    client = make_auth(tmp_path, key="sk-ant-test").build_client()
    assert client.api_key == "sk-ant-test"
