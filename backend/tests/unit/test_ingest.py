from __future__ import annotations

from proseferno.ingest import parse_file, parse_markdown
from proseferno.ingest.stylometrics import aggregate, compute, fidelity


def test_medium_export_is_cleaned(sample_docx: bytes) -> None:
    doc = parse_file("pie.docx", sample_docx)

    assert doc.title == "Pie Charts Are Lame"
    assert doc.subtitle.startswith("A short roast")
    texts = [b.text for b in doc.blocks]
    assert "Press enter or click to view image in full size" not in texts
    assert "42" not in texts and "Follow" not in texts
    assert doc.image_count == 2
    assert doc.captions == ["Source: Office survey; Author: Test Writer; Made with Tableau"]


def test_headings_are_recovered_but_image_prompts_are_not(sample_docx: bytes) -> None:
    doc = parse_file("pie.docx", sample_docx)
    headings = [b.text for b in doc.blocks if b.kind == "heading"]

    assert headings == ["Why Pie Charts Fail", "A Better Option"]


def test_markdown_shows_image_and_caption_markers(sample_docx: bytes) -> None:
    markdown = parse_file("pie.docx", sample_docx).to_markdown()

    assert markdown.startswith("# Pie Charts Are Lame")
    assert "[IMAGE]" in markdown
    assert "[CAPTION] Source: Office survey" in markdown
    assert "## Why Pie Charts Fail" in markdown


def test_markdown_parser_handles_lists_code_and_images() -> None:
    doc = parse_markdown("# Title\n\nIntro text here.\n\n- one\n- two\n\n```python\nprint(1)\n```\n\n![A chart](c.png)\n")

    kinds = [b.kind for b in doc.blocks]
    assert doc.title == "Title"
    assert kinds == ["paragraph", "list_item", "list_item", "code", "image", "caption"]


def test_unsupported_extension_is_rejected() -> None:
    import pytest

    from proseferno.ingest import UnsupportedFormatError

    with pytest.raises(UnsupportedFormatError):
        parse_file("notes.xyz", b"hello")


def test_stylometrics_measure_voice_features(sample_docx: bytes) -> None:
    metrics = compute(parse_file("pie.docx", sample_docx))

    assert metrics["image_count"] == 2
    assert metrics["heading_count"] == 2
    assert metrics["first_person_singular_per_1k"] > 0
    assert metrics["second_person_per_1k"] > 0
    assert metrics["exclamation_per_100_sentences"] > 0
    assert metrics["opening_style"] in {"statement", "personal_anecdote", "direct_address", "question", "fact_or_statistic"}


def test_fidelity_is_perfect_for_identical_style(sample_docx: bytes) -> None:
    metrics = compute(parse_file("pie.docx", sample_docx))
    baseline = aggregate([metrics])

    assert fidelity(baseline, metrics)["score"] == 100.0
    shifted = {**metrics, "avg_sentence_words": metrics["avg_sentence_words"] + 30}
    assert fidelity(baseline, shifted)["score"] < 100.0
