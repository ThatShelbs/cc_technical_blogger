from __future__ import annotations

from proseferno.db import Persona, Sample
from proseferno.voice import rank_by_similarity, select_exemplars
from proseferno.writer import (
    Dials,
    ImageSlot,
    classify_topic,
    ensure_placeholders,
    normalize_slots,
    resolve,
    set_title,
    split_title,
)


def slot(slot_id: str, kind: str, section: int = 0) -> ImageSlot:
    return ImageSlot(slot_id=slot_id, kind=kind, section_index=section, purpose="p", brief="b")  # type: ignore[arg-type]


def test_dials_resolve_to_smart_defaults() -> None:
    persona = Persona(name="Me", default_humor=7, default_education="expert")
    resolved = resolve(Dials(), persona, "Uplift modeling with causal forests", default_revisions=1)

    assert resolved.target_words == 1500
    assert resolved.image_count == 4
    assert resolved.humor == 7
    assert resolved.education == "expert"
    assert resolved.topic == "Causality, Experimentation & Causal Inference"
    assert resolved.revision_passes == 1


def test_explicit_dials_win() -> None:
    persona = Persona(name="Me")
    resolved = resolve(Dials(target_words=3000, image_count=8, humor=0, education="beginner"), persona, "x", default_revisions=1)

    assert (resolved.image_count, resolved.humor, resolved.education) == (8, 0, "beginner")


def test_topic_classification() -> None:
    assert classify_topic("Shipping a feature with Claude Code and Cursor") == "Building with Agentic Coding Tools"
    assert classify_topic("Why word clouds and pie charts mislead") == "Data Visualization"
    assert classify_topic("Snowflake Cortex vs AWS Bedrock") == "AI/ML Platforms (AWS, Snowflake)"


def test_normalize_slots_forces_hero_first_meme_last_and_count() -> None:
    slots = [slot("a", "diagram"), slot("b", "chart"), slot("c", "illustration"), slot("h", "hero"), slot("m", "meme")]
    normalized = normalize_slots(slots, count=4, section_count=3)

    assert [s.slot_id for s in normalized] == ["hero", "img2", "img3", "meme"]
    assert [s.kind for s in normalized] == ["hero", "diagram", "chart", "meme"]
    assert normalized[-1].section_index == 2


def test_normalize_slots_adds_missing_hero_and_meme() -> None:
    normalized = normalize_slots([slot("a", "diagram")], count=3, section_count=2)
    assert [s.kind for s in normalized] == ["hero", "diagram", "meme"]


def test_ensure_placeholders_inserts_missing_and_drops_unknown() -> None:
    slots = normalize_slots([slot("x", "diagram", 1)], count=3, section_count=2)
    markdown = "# T\n\n*Sub*\n\nIntro.\n\n## One\n\nText.\n\n{{image:bogus}}\n\n## Two\n\nMore.\n"
    fixed = ensure_placeholders(markdown, slots)

    assert "{{image:bogus}}" not in fixed
    assert fixed.index("{{image:hero}}") < fixed.index("Intro.")
    assert fixed.index("## Two") < fixed.index("{{image:img2}}")
    assert fixed.rstrip().endswith("{{image:meme}}")


def test_title_helpers() -> None:
    markdown = "# Old Title\n\n*The subtitle*\n\nBody."
    assert split_title(markdown) == ("Old Title", "The subtitle")
    assert split_title(set_title(markdown, "New Title"))[0] == "New Title"


def test_exemplars_prefer_similar_posts() -> None:
    ranked = rank_by_similarity("causal inference uplift", ["pie charts are lame", "uplift modeling and causal inference basics"])
    assert ranked[0][0] == 1

    samples = [
        Sample(
            id=1, persona_id=1, kind="own", source_name="a", source_type="md", title="Pies", markdown="pie chart pie chart", word_count=4000
        ),
        Sample(
            id=2,
            persona_id=1,
            kind="own",
            source_name="b",
            source_type="md",
            title="Uplift",
            markdown="uplift causal uplift",
            word_count=4000,
        ),
        Sample(
            id=3, persona_id=1, kind="influence", source_name="c", source_type="md", title="Other", markdown="uplift uplift", word_count=10
        ),
        Sample(id=4, persona_id=1, kind="own", source_name="d", source_type="md", title="Big", markdown="causal", word_count=8000),
    ]
    chosen = select_exemplars("uplift causal", samples, max_words=9000)
    assert chosen[0].id == 2
    assert all(s.kind == "own" for s in chosen)
    assert sum(s.word_count for s in chosen) <= 9000
