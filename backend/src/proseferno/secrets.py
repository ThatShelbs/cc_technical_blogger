"""Secret storage backed by the OS keychain (Windows Credential Manager, macOS
Keychain, Secret Service on Linux). Secrets never touch the database or repo."""

from __future__ import annotations

import contextlib
from typing import Protocol

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

ANTHROPIC_API_KEY = "anthropic_api_key"
CLOUDFLARE_API_TOKEN = "cloudflare_api_token"


class SecretStore(Protocol):
    def get(self, name: str) -> str | None: ...
    def set(self, name: str, value: str) -> None: ...
    def delete(self, name: str) -> None: ...


class KeyringSecretStore:
    def __init__(self, service: str) -> None:
        self.service = service

    def get(self, name: str) -> str | None:
        try:
            return keyring.get_password(self.service, name)
        except KeyringError:
            return None

    def set(self, name: str, value: str) -> None:
        keyring.set_password(self.service, name, value)

    def delete(self, name: str) -> None:
        with contextlib.suppress(PasswordDeleteError):
            keyring.delete_password(self.service, name)


class MemorySecretStore:
    """In-memory store used by tests."""

    def __init__(self, initial: dict[str, str] | None = None) -> None:
        self._values = dict(initial or {})

    def get(self, name: str) -> str | None:
        return self._values.get(name)

    def set(self, name: str, value: str) -> None:
        self._values[name] = value

    def delete(self, name: str) -> None:
        self._values.pop(name, None)
