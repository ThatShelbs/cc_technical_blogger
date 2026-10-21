"""Claude credentials: "Sign in with Claude" (Anthropic CLI OAuth profile) or an API key.

Resolution order, first match wins:

1. An API key the user saved in Proseferno (OS keychain).
2. ``ANTHROPIC_API_KEY`` / ``ANTHROPIC_AUTH_TOKEN`` in the environment.
3. The active ``ant auth login`` profile (browser OAuth with Claude Console; works with org SSO).

Note: an environment API key silently shadows a signed-in profile. ``status()``
reports which source won so the Settings page can explain it.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from anthropic import AsyncAnthropic

from proseferno.llm.base import LLMNotConfiguredError
from proseferno.secrets import ANTHROPIC_API_KEY, SecretStore

Source = Literal["app_api_key", "env_api_key", "env_auth_token", "claude_sign_in", "none"]


@dataclass
class AuthStatus:
    signed_in: bool
    source: Source
    detail: str
    ant_installed: bool
    profile: str | None = None
    login_in_progress: bool = False
    login_output: str = ""
    warnings: list[str] = field(default_factory=list)


def anthropic_config_dir(env: dict[str, str] | os._Environ[str] = os.environ) -> Path:
    if env.get("ANTHROPIC_CONFIG_DIR"):
        return Path(env["ANTHROPIC_CONFIG_DIR"])
    if sys.platform == "win32" and env.get("APPDATA"):
        return Path(env["APPDATA"]) / "Anthropic"
    return Path.home() / ".config" / "anthropic"


def find_ant() -> str | None:
    found = shutil.which("ant")
    if found:
        return found
    # winget/zip installs land here; PATH may not be refreshed for this process yet.
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidate = Path(local) / "Programs" / "ant" / "ant.exe"
        if candidate.exists():
            return str(candidate)
    return None


class ClaudeAuth:
    def __init__(
        self,
        secrets: SecretStore,
        *,
        env: dict[str, str] | os._Environ[str] = os.environ,
        ant_path: str | None = None,
        discover_ant: bool = True,
    ) -> None:
        self.secrets = secrets
        self.env = env
        self._ant_path = ant_path
        # Tests turn discovery off so they can never launch the real CLI.
        self._discover_ant = discover_ant
        self._login: subprocess.Popen[str] | None = None
        self._login_output: list[str] = []

    # -- status ------------------------------------------------------------

    @property
    def ant_path(self) -> str | None:
        if self._ant_path:
            return self._ant_path
        return find_ant() if self._discover_ant else None

    def active_profile(self) -> str:
        if self.env.get("ANTHROPIC_PROFILE"):
            return self.env["ANTHROPIC_PROFILE"]
        marker = anthropic_config_dir(self.env) / "active_config"
        if marker.is_file():
            name = marker.read_text(encoding="utf-8").strip()
            if name:
                return name
        return "default"

    def profile_signed_in(self) -> bool:
        creds = anthropic_config_dir(self.env) / "credentials" / f"{self.active_profile()}.json"
        return creds.is_file() and creds.stat().st_size > 0

    def login_in_progress(self) -> bool:
        return self._login is not None and self._login.poll() is None

    def status(self) -> AuthStatus:
        warnings: list[str] = []

        def make(signed_in: bool, source: Source, detail: str) -> AuthStatus:
            return AuthStatus(
                signed_in=signed_in,
                source=source,
                detail=detail,
                ant_installed=self.ant_path is not None,
                profile=self.active_profile(),
                login_in_progress=self.login_in_progress(),
                login_output="".join(self._login_output)[-4000:],
                warnings=warnings,
            )

        if self.secrets.get(ANTHROPIC_API_KEY):
            if self.profile_signed_in():
                warnings.append("Your saved API key is used instead of your Claude sign-in. Remove the key to use the sign-in.")
            return make(True, "app_api_key", "Using the API key saved in Proseferno.")
        if self.env.get("ANTHROPIC_API_KEY"):
            if self.profile_signed_in():
                warnings.append("ANTHROPIC_API_KEY is set in your environment and overrides your Claude sign-in.")
            return make(True, "env_api_key", "Using ANTHROPIC_API_KEY from the environment.")
        if self.env.get("ANTHROPIC_AUTH_TOKEN"):
            return make(True, "env_auth_token", "Using ANTHROPIC_AUTH_TOKEN from the environment.")
        if self.profile_signed_in():
            return make(True, "claude_sign_in", f"Signed in with Claude (profile '{self.active_profile()}').")
        if self.ant_path is None:
            return make(False, "none", "Not signed in. Install the Anthropic CLI to use 'Sign in with Claude', or paste an API key.")
        return make(False, "none", "Not signed in.")

    # -- client ------------------------------------------------------------

    def build_client(self) -> AsyncAnthropic:
        key = self.secrets.get(ANTHROPIC_API_KEY)
        if key:
            return AsyncAnthropic(api_key=key, max_retries=3)
        if self.env.get("ANTHROPIC_API_KEY") or self.env.get("ANTHROPIC_AUTH_TOKEN"):
            return AsyncAnthropic(max_retries=3)
        if self.profile_signed_in():
            return AsyncAnthropic(profile=self.active_profile(), max_retries=3)
        raise LLMNotConfiguredError()

    # -- actions -----------------------------------------------------------

    def set_api_key(self, key: str) -> None:
        self.secrets.set(ANTHROPIC_API_KEY, key.strip())

    def clear_api_key(self) -> None:
        self.secrets.delete(ANTHROPIC_API_KEY)

    def start_login(self) -> None:
        """Run ``ant auth login``; it opens the browser and waits for the OAuth callback."""
        ant = self.ant_path
        if ant is None:
            raise FileNotFoundError("The Anthropic CLI ('ant') is not installed.")
        if self.login_in_progress():
            return
        self._login_output = []
        self._login = subprocess.Popen(
            [ant, "auth", "login"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        threading.Thread(target=self._pump_login_output, daemon=True).start()

    def logout(self) -> None:
        ant = self.ant_path
        if ant is not None:
            subprocess.run([ant, "auth", "logout"], capture_output=True, timeout=60, check=False)

    def _pump_login_output(self) -> None:
        proc = self._login
        if proc is None or proc.stdout is None:
            return
        for line in proc.stdout:
            self._login_output.append(line)
