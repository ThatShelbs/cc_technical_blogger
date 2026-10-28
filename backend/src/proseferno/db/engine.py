from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, event, inspect, text
from sqlmodel import SQLModel, create_engine

from proseferno.db import models  # noqa: F401  (registers tables)

log = logging.getLogger(__name__)


def make_engine(db_path: Path) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    rename_legacy_schema(engine)
    SQLModel.metadata.create_all(engine)
    add_missing_columns(engine)
    move_legacy_voice_files(db_path.parent)
    return engine


# Databases made before "voice soul" became "voice profile": (table, old column, new column).
_LEGACY_TABLES = {"voicesoul": "voiceprofile"}
_LEGACY_COLUMNS = [
    ("persona", "pinned_voice_soul_version", "pinned_voice_profile_version"),
    ("project", "voice_soul_version", "voice_profile_version"),
]


def rename_legacy_schema(engine: Engine) -> None:
    """Rename the pre-rename voice soul table and columns in place, keeping every user's data.

    Runs before ``create_all`` so the renamed table is found instead of an empty new one.
    """
    inspector = inspect(engine)
    with engine.begin() as conn:
        for old, new in _LEGACY_TABLES.items():
            if inspector.has_table(old) and not inspector.has_table(new):
                conn.execute(text(f'ALTER TABLE "{old}" RENAME TO "{new}"'))
                log.info("Renamed table %s to %s", old, new)
        for table, old, new in _LEGACY_COLUMNS:
            if not inspector.has_table(table):
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            if old in existing and new not in existing:
                conn.execute(text(f'ALTER TABLE "{table}" RENAME COLUMN "{old}" TO "{new}"'))
                log.info("Renamed column %s.%s to %s", table, old, new)


def move_legacy_voice_files(data_dir: Path) -> None:
    """Move each persona's saved ``voice_soul/voice_soul.vN.md`` files to ``voice_profile/``."""
    for old_dir in data_dir.glob("personas/*/voice_soul"):
        new_dir = old_dir.with_name("voice_profile")
        new_dir.mkdir(exist_ok=True)
        for file in old_dir.glob("voice_soul.v*.md"):
            target = new_dir / file.name.replace("voice_soul", "voice_profile", 1)
            if not target.exists():
                file.rename(target)
        try:
            old_dir.rmdir()
        except OSError:
            log.warning("Left %s in place: it still has files", old_dir)


def add_missing_columns(engine: Engine) -> None:
    """Additive migrations: add columns that newer versions of the models define.

    ``create_all`` only creates missing tables, so a database made by an older
    version would lack new columns. Columns are only ever added, never changed.
    """
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in SQLModel.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                ddl_type = column.type.compile(dialect=engine.dialect)
                default = _sql_default(getattr(column.default, "arg", None))
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {ddl_type}{default}'))
                log.info("Added column %s.%s", table.name, column.name)


def _sql_default(value: Any) -> str:
    if callable(value):
        try:
            value = value(None)
        except TypeError:
            value = value()
    if value is None:
        return ""
    if isinstance(value, bool):
        return f" DEFAULT {int(value)}"
    if isinstance(value, (int, float)):
        return f" DEFAULT {value}"
    if isinstance(value, (dict, list)):
        value = json.dumps(value)
    return " DEFAULT '" + str(value).replace("'", "''") + "'"
