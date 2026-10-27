from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlmodel import Session, select

from proseferno.db import Persona, make_engine


def test_older_databases_gain_new_columns_with_defaults(tmp_path: Path) -> None:
    db = tmp_path / "old.db"
    with sqlite3.connect(db) as conn:
        # The persona table as the first release created it.
        conn.execute(
            "CREATE TABLE persona (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL, display_name VARCHAR NOT NULL, "
            "is_active BOOLEAN NOT NULL, research_enabled BOOLEAN NOT NULL, default_humor INTEGER NOT NULL, "
            "default_education VARCHAR NOT NULL, visual_style VARCHAR NOT NULL, credit_template VARCHAR NOT NULL, "
            "created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL)"
        )
        conn.execute("INSERT INTO persona VALUES (1, 'Shelby', 'Shelby', 1, 0, 7, 'expert', '', 'x', '2026-01-01', '2026-01-01')")

    engine = make_engine(db)
    with Session(engine) as session:
        persona = session.exec(select(Persona)).one()
    assert persona.default_humor == 7
    assert persona.default_storytelling == 5 and persona.default_platform == "medium" and persona.default_target_words == 1500
    assert persona.pinned_voice_soul_version is None and persona.default_image_count is None
    make_engine(db)  # idempotent
