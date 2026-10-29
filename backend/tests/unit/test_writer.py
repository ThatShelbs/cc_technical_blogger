from __future__ import annotations

from proseferno.db import Persona, Project, Sample
from proseferno.voice import rank_by_similarity, select_exemplars
from proseferno.writer import (
    MAX_REVISIONS,
    Dials,
    ImageSlot,
    TextEdit,
    apply_edits,
    classify_topic,
    ensure_placeholders,
    finish_text,
    merge_titles,
    normalize_slots,
    push_revision,
    resolve,
    set_title,
    split_title,
)
from proseferno.writer.pipeline import strip_image_captions, strip_todos


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


def test_strip_image_captions_removes_credit_lines_next_to_images() -> None:
    markdown = "\n".join(
        [
            "# Nobody Has a Single Source of Truth",
            "*Did your source of truth disagree with finance again?*",
            "",
            "{{image:hero}}",
            "",
            "Photo by [TODO: photographer name] on Unsplash",
            "",
            "Made with Unsplash is a real sentence I keep, far from any image.",
            "",
            "Source: internal survey",
            "{{image:img2}}",
            "*Visualization: Shelby Temple, made with a spreadsheet; data: made-up example numbers*",
            "",
            "The chart above shows why. Images are great, but this paragraph is prose.",
            "",
            "{{image:meme}}",
        ]
    )
    cleaned = strip_image_captions(markdown)

    assert "Photo by" not in cleaned
    assert "Visualization:" not in cleaned
    assert "Source: internal survey" not in cleaned
    # Prose, the subtitle (italic, right above the hero) and placeholders stay.
    assert "*Did your source of truth disagree with finance again?*" in cleaned
    assert "Made with Unsplash is a real sentence" in cleaned
    assert "The chart above shows why." in cleaned
    assert all(f"{{{{image:{s}}}}}" in cleaned for s in ("hero", "img2", "meme"))


def test_strip_todos_removes_notes_but_not_code() -> None:
    markdown = "\n".join(
        [
            "Uplift models need a holdout [TODO: verify the 10% figure]. Keep it.",
            "TODO: add a link to the paper",
            "- (todo: cite) Randomize first.",
            "```python",
            "# TODO: tune this",
            "```",
        ]
    )
    cleaned = strip_todos(markdown)

    assert "Uplift models need a holdout. Keep it." in cleaned
    assert "add a link" not in cleaned
    assert "- Randomize first." in cleaned
    assert "# TODO: tune this" in cleaned


def test_merge_titles_dedupes_case_insensitively() -> None:
    assert merge_titles(["A Title", " "], ["a title", "Another"]) == ["A Title", "Another"]


def test_audience_and_x_platform_resolve() -> None:
    resolved = resolve(Dials(audience="  data science managers ", platform="x"), Persona(name="Me"), "x", default_revisions=1)
    assert resolved.audience == "data science managers" and resolved.platform == "x"
    assert "X Article" in resolved.platform_guide
    assert resolve(Dials(), Persona(name="Me"), "x", default_revisions=1).audience == ""


def test_apply_edits_exact_whitespace_tolerant_and_skipped() -> None:
    post = "# T\n\nFirst line here.\nIt wraps.\n\n{{image:img2}}\n\nLast line."
    edits = [
        TextEdit(find="Last line.", replace="Final line."),
        TextEdit(find="First line here. It wraps.", replace="One line now."),
        TextEdit(find="Not in the post", replace="x"),
        TextEdit(find="same", replace="same"),
    ]
    out, applied, skipped = apply_edits(post, edits)
    assert applied == 2 and skipped == ["Not in the post"]
    assert out == "# T\n\nOne line now.\n\n{{image:img2}}\n\nFinal line."


def test_finish_text_restores_a_dropped_placeholder() -> None:
    plan = {
        "image_slots": [
            slot("hero", "hero", -1).model_dump(),
            slot("img2", "diagram", 0).model_dump(),
            slot("meme", "meme", 0).model_dump(),
        ]
    }
    post = "# T\n\n*Sub*\n\n{{image:hero}}\n\n## One\n\nText.\n\n{{image:meme}}\n"
    out, _, _ = apply_edits(post, [TextEdit(find="Text.", replace="New text.")])
    fixed = finish_text(out, plan)
    assert "{{image:img2}}" in fixed and "New text." in fixed
    assert finish_text("anything", None) == "anything"


def test_revisions_are_newest_first_and_capped() -> None:
    project = Project(persona_id=1, prompt="p", markdown="v0")
    push_revision(Project(persona_id=1, prompt="p"), "empty posts are not kept", "edit")
    for i in range(MAX_REVISIONS + 3):
        push_revision(project, f"change {i}", "tweak")
        project.markdown = f"v{i + 1}"
    assert len(project.revisions) == MAX_REVISIONS
    assert project.revisions[0]["label"] == f"change {MAX_REVISIONS + 2}" and project.revisions[0]["markdown"] == f"v{MAX_REVISIONS + 2}"


def test_extract_and_record_lessons() -> None:
    from proseferno.voice.lessons import extract_lessons, format_lessons, record_lessons

    before = "Let's delve into it. Honestly, the model is a total game-changer for most teams."
    after = "Let's dig into it. The model helps most teams."
    lessons = extract_lessons(before, after)
    assert {"kind": "replace", "old": "delve", "new": "dig"} in lessons
    assert {"kind": "replace", "old": "Honestly, the", "new": "The"} in lessons
    assert {"kind": "replace", "old": "is a total game-changer for", "new": "helps"} in lessons
    persona = Persona(name="Me")
    record_lessons(persona, lessons)
    record_lessons(persona, lessons[:1])
    assert persona.edit_lessons[0]["count"] == 2
    assert "times)" in format_lessons(persona.edit_lessons)
    # A long rewrite is content, not a habit.
    assert extract_lessons("one two three four five six seven eight nine ten", "completely different text here") == []
