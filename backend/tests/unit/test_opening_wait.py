"""When must the closing meme wait for the opening image, and the old detector switch migrates."""

from __future__ import annotations

from pathlib import Path

from sqlmodel import Session

from inferno_ghostwriter.config import Settings
from inferno_ghostwriter.db import AppSetting, make_engine
from inferno_ghostwriter.images.opening.styles import eligible, may_be_meme
from inferno_ghostwriter.services import load_runtime_settings


def test_only_a_possible_meme_opening_makes_the_closer_wait() -> None:
    assert may_be_meme("meme", [])  # chosen
    assert not may_be_meme("editorial", ["meme"])  # a fixed non-meme style never turns into a meme
    assert may_be_meme("auto", ["editorial", "meme"])
    assert not may_be_meme("auto", ["editorial", "data_art"])
    assert not may_be_meme("auto", [])
    assert may_be_meme("auto", eligible("auto", "auto", 10))  # high humor offers the meme styles


def test_old_deep_check_switch_keeps_the_trained_detectors(tmp_path: Path) -> None:
    engine = make_engine(tmp_path / "t.db")
    with Session(engine) as session:
        session.add(AppSetting(key="deep_check", value=True))
        session.commit()
    settings = Settings(data_dir=tmp_path, _env_file=None)  # type: ignore[call-arg]
    load_runtime_settings(engine, settings)
    assert settings.detector_models == ["light", "curvature", "classifier"]

    fresh = Settings(data_dir=tmp_path, _env_file=None)  # type: ignore[call-arg]
    with Session(engine) as session:
        session.add(AppSetting(key="detector_models", value=["light"]))
        session.commit()
    load_runtime_settings(engine, fresh)
    assert fresh.detector_models == ["light"]  # an explicit choice wins over the old switch
