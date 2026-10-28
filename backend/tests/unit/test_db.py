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
    assert persona.pinned_voice_profile_version is None and persona.default_image_count is None
    make_engine(db)  # idempotent


def test_voice_soul_data_is_carried_over_to_voice_profile(tmp_path: Path) -> None:
    db = tmp_path / "proseferno.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE persona (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL, pinned_voice_soul_version INTEGER)")
        conn.execute("INSERT INTO persona (id, name, pinned_voice_soul_version) VALUES (1, 'Shelby', 2)")
        conn.execute("CREATE TABLE project (id INTEGER PRIMARY KEY, voice_soul_version INTEGER)")
        conn.execute("INSERT INTO project (id, voice_soul_version) VALUES (1, 3)")
        conn.execute("CREATE TABLE voicesoul (id INTEGER PRIMARY KEY, persona_id INTEGER, version INTEGER, label VARCHAR, markdown TEXT)")
        conn.execute("INSERT INTO voicesoul VALUES (1, 1, 2, 'Punchier', '# Voice Soul: mine')")
    old_dir = tmp_path / "personas" / "1" / "voice_soul"
    old_dir.mkdir(parents=True)
    (old_dir / "voice_soul.v2.md").write_text("# Voice Soul: mine", encoding="utf-8")

    engine = make_engine(db)
    make_engine(db)  # idempotent

    with engine.connect() as conn:
        tables = {r[0] for r in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "voiceprofile" in tables and "voicesoul" not in tables
        assert conn.exec_driver_sql("SELECT label, markdown FROM voiceprofile").one() == ("Punchier", "# Voice Soul: mine")
        assert conn.exec_driver_sql("SELECT pinned_voice_profile_version FROM persona").scalar_one() == 2
        assert conn.exec_driver_sql("SELECT voice_profile_version FROM project").scalar_one() == 3
    assert (tmp_path / "personas" / "1" / "voice_profile" / "voice_profile.v2.md").read_text(encoding="utf-8") == "# Voice Soul: mine"
    assert not old_dir.exists()
