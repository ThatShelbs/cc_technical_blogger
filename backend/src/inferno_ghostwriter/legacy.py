"""Carry an installation made before the product was named Inferno Ghostwriter (it was "Proseferno").

Everything here only ever *adds* to the new location and leaves the old one in place, so a failed
or interrupted move never loses data. Keep this module until a major version.
"""

from __future__ import annotations

import logging
import os
import shutil
from collections.abc import MutableMapping
from pathlib import Path

from inferno_ghostwriter.secrets import ANTHROPIC_API_KEY, SecretStore

log = logging.getLogger(__name__)

LEGACY_ENV_PREFIX = "PROSEFERNO_"
ENV_PREFIX = "INFERNO_GHOSTWRITER_"
LEGACY_DB_NAME = "proseferno.db"
DB_NAME = "inferno_ghostwriter.db"
LEGACY_KEYRING_SERVICE = "proseferno"
LEGACY_APP_FOLDER = "Proseferno"


def adopt_legacy_env(env: MutableMapping[str, str] | None = None) -> None:
    """Honor ``PROSEFERNO_*`` variables when the matching ``INFERNO_GHOSTWRITER_*`` one is not set."""
    env = os.environ if env is None else env
    for name in list(env):
        if name.startswith(LEGACY_ENV_PREFIX):
            env.setdefault(ENV_PREFIX + name[len(LEGACY_ENV_PREFIX) :], env[name])


def move_legacy_app_folder(new_dir: Path) -> None:
    """Windows installer: move ``%LOCALAPPDATA%\\Proseferno`` to the new folder name."""
    old_dir = new_dir.with_name(LEGACY_APP_FOLDER)
    if old_dir.is_dir() and not new_dir.exists():
        try:
            old_dir.rename(new_dir)
        except OSError:
            log.warning("Could not move %s to %s; copying instead.", old_dir, new_dir)
            shutil.copytree(old_dir, new_dir)


def move_legacy_database(db_path: Path) -> None:
    """Rename ``proseferno.db`` (and its WAL files) to the new database name when the new one is absent."""
    if db_path.exists():
        return
    for suffix in ("", "-wal", "-shm"):
        old = db_path.with_name(LEGACY_DB_NAME + suffix)
        if old.exists():
            old.rename(db_path.with_name(db_path.name + suffix))


def copy_legacy_secrets(store: SecretStore, legacy: SecretStore) -> None:
    """Copy the saved API key from the old keychain service to the new one (the old entry is kept)."""
    if store.get(ANTHROPIC_API_KEY):
        return
    key = legacy.get(ANTHROPIC_API_KEY)
    if key:
        store.set(ANTHROPIC_API_KEY, key)
