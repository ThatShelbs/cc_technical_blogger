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

    SQLModel.metadata.create_all(engine)
    add_missing_columns(engine)
    return engine


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
