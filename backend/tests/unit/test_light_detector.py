"""The built-in light detector and the selectable, multi-model detector setup."""

from __future__ import annotations

import asyncio
from pathlib import Path

from inferno_ghostwriter.authenticity.light_detector import light_result, score_sentences, score_text
from inferno_ghostwriter.authenticity.local_detector import (
    BY_ID,
    CATALOG,
    FakeDetector,
    MultiDetector,
    active_models,
    clean_selection,
    detector_input,
    detector_report,
    get_detector,
    setup_detector,
    status,
)
from inferno_ghostwriter.authenticity.texture import prose_sentences
from inferno_ghostwriter.config import Settings

MACHINE = (
    "In today's fast-paced digital landscape, data science plays a crucial role in driving business success. "
    "Organizations must leverage data to make informed decisions. "
    "A/B testing is a powerful technique for comparing two versions of a product. "
    "It allows teams to measure the impact of changes. It also helps to reduce risk when launching new features. "
    "Understanding statistical significance is essential for interpreting results. "
    "This ensures that decisions are based on reliable evidence. "
    "Teams should define clear success metrics before running an experiment. This helps to avoid bias in the analysis. "
    "Furthermore, it is important to ensure an adequate sample size. This guarantees that the results are statistically meaningful."
)
HUMAN = (
    "I made a pie chart in 2019 and my VP asked which slice was bigger. I did not know either. We stared at it for a full minute. "
    "Pie charts feel friendly, though: they look like dessert, they fit on a slide, and nobody ever got fired for making one. "
    "But the eye is bad at angles. Ask anyone to rank five slices and you'll get five answers (three of them confident and wrong). "
    "So what do you do instead? A bar chart. Boring, yes; it works. "
    "Last spring, Priya rebuilt our churn dashboard with sorted bars and the arguing stopped within a week. "
    "Honestly, that was the whole win."
)


def settings(tmp_path: Path, **overrides: object) -> Settings:
    return Settings(data_dir=tmp_path, _env_file=None, **overrides)  # type: ignore[call-arg]


def test_light_check_reads_even_impersonal_prose_as_more_machine() -> None:
    machine, human = score_text(prose_sentences(MACHINE)), score_text(prose_sentences(HUMAN))
    assert machine is not None and human is not None
    assert machine > human + 0.25
    assert 0 <= human <= 1 and 0 <= machine <= 1


def test_light_check_needs_enough_prose() -> None:
    assert score_text(["Short one.", "Another."]) is None
    assert score_sentences(["Short one."]) == [None]
    result = light_result(prose_sentences(MACHINE))
    assert result["score"] is not None and len(result["sentences"]) == len(prose_sentences(MACHINE))  # type: ignore[arg-type]


def test_selection_is_cleaned_and_light_is_the_default(tmp_path: Path) -> None:
    assert clean_selection(["classifier", "bogus", "light", "light"]) == ["light", "classifier"]
    assert clean_selection([]) == []
    assert settings(tmp_path).detector_models == ["light"]
    assert CATALOG[0].id == "light" and not BY_ID["light"].heavy


def test_light_runs_with_no_setup_and_trained_models_wait_for_it(tmp_path: Path) -> None:
    only_light = settings(tmp_path)
    assert active_models(only_light) == ["light"]
    state = status(only_light)
    assert state["ready"] and state["enabled"] and state["selected"] == ["light"]

    mixed = settings(tmp_path, detector_models=["light", "classifier"])
    assert active_models(mixed) == ["light"]  # the classifier is not downloaded yet
    state = status(mixed)
    assert not state["ready"] and state["enabled"] and "not set up" in state["detail"]
    assert [m["installed"] for m in state["models"]] == [True, False, False]

    assert active_models(settings(tmp_path, detector_models=[])) == []
    assert get_detector(settings(tmp_path, detector_models=[])) is None


def test_setup_with_only_the_light_check_downloads_nothing(tmp_path: Path) -> None:
    assert setup_detector(settings(tmp_path)) == {}


def test_get_detector_is_the_light_check_by_default(tmp_path: Path) -> None:
    detector = get_detector(settings(tmp_path))
    assert isinstance(detector, MultiDetector) and detector.models == {"light": "built in"} and detector.worker is None
    [result] = asyncio.run(detector.score([detector_input(MACHINE)]))
    assert set(result) == {"light"} and result["light"]["score"] is not None


def test_report_with_the_light_check_alone_and_with_several_models(tmp_path: Path) -> None:
    config = settings(tmp_path)
    light = asyncio.run(detector_report(settings=config, detector=FakeDetector(ids=["light"]), markdown=MACHINE, author_texts=[HUMAN]))
    assert [m["id"] for m in light["models"]] == ["light"] and light["models"][0]["model"] == "built in"
    assert light["score"] is not None and light["score"] < 60  # even, impersonal prose is flagged against a varied author

    human = asyncio.run(detector_report(settings=config, detector=FakeDetector(ids=["light"]), markdown=HUMAN, author_texts=[HUMAN]))
    assert human["score"] is not None and human["score"] > light["score"]

    many = asyncio.run(
        detector_report(
            settings=config, detector=FakeDetector(ids=["light", "curvature", "classifier"]), markdown=MACHINE, author_texts=[HUMAN]
        )
    )
    assert [m["id"] for m in many["models"]] == ["light", "curvature", "classifier"]
    assert all(o["source"] == "detector" for o in many["outliers"])
