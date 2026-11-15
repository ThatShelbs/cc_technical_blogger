"""Humanizing: the author's paragraphs, texture, the twin test, the detector models and the humanize loop."""

from __future__ import annotations

import asyncio
from pathlib import Path

from proseferno.authenticity import AuthorProfile, analyze, blend
from proseferno.authenticity.detector_worker import ai_label_index, assign_tokens, join_spans
from proseferno.authenticity.local_detector import FakeDetector, author_range, detector_report, model_score, status
from proseferno.authenticity.passages import anchor_passages, author_passages, section_anchors, split_paragraphs, tagged
from proseferno.authenticity.texture import author_texture, measure_texture, monotone_runs, texture_report
from proseferno.authenticity.twin import Pair, TwinVerdict, TwinVerdicts, build_pairs, pair_score, score_pairs
from proseferno.config import Settings
from proseferno.demo import DEMO_HUMANIZE, FakeLLM
from proseferno.prompts import raw
from proseferno.writer.humanize import humanize_post, targets
from proseferno.writer.pipeline import author_material_check, format_author_material

AUTHOR_POST = """# Pie Charts Are Lame

*A rant, with charts.*

I made a pie chart in 2019 and my VP asked which slice was bigger. I did not know either. We stared at it for a full minute.

## Why we keep doing this

Pie charts feel friendly. They look like dessert, they fit on a slide, and nobody ever got fired for making one in a meeting.

But the eye is bad at angles. Ask anyone to rank five slices and you will get five answers, three of them confident and wrong.

{{image:hero}}

## What to do instead

Here is the fix:

- sort your bars
- label the ends

Sort the bars. Put the biggest one on top. Label the end of each bar so nobody has to squint at an axis to find out what you meant.

```python
df.sort_values("share").plot.barh()
```

Honestly, I think the pie chart should be retired. Bars are boring, and boring is exactly what you want when the CFO is reading.

Go sort something.
"""

DRAFT = """# Bars Beat Pies

*Why your charts should stop looking like dessert.*

Data visualization is an important aspect of communication in modern organizations and teams.

## The problem

Pie charts are a common choice for showing parts of a whole in a business setting. They are widely used across many industries and teams. They are often chosen because they look friendly and simple. They can make comparisons difficult for the readers who view them. Their angles are hard to compare accurately and consistently.

## The fix

Bar charts provide a more effective alternative for the comparison of categories. Sorting the bars helps the reader see the ranking at a glance and reduces cognitive load significantly.

In conclusion, choosing the right visualization is essential for effective communication.
"""  # noqa: E501 - prose paragraphs, as the writer produces them


def test_paragraphs_skip_structure_and_tag_roles() -> None:
    paragraphs = split_paragraphs(AUTHOR_POST)
    texts = [p.text for p in paragraphs]
    assert texts[0].startswith("I made a pie chart")  # the subtitle and title are not prose
    assert not any("sort_values" in t or t.startswith("{{") or t.startswith("- ") for t in texts)
    roles = dict((p.text[:12], role) for p, role in tagged(AUTHOR_POST))
    assert roles["I made a pie"] == "opener"
    assert roles["Here is the "] == "list_intro"
    assert roles["Honestly, I "] == "opinion"
    assert roles["Go sort some"] == "closer"
    assert paragraphs[1].heading == "Why we keep doing this" and paragraphs[1].section == 0


def test_anchor_passages_match_role_and_topic() -> None:
    passages = author_passages([("Pie charts", AUTHOR_POST)])
    found = anchor_passages("sorting bars and labels", passages, ("explain", "story", "opinion"), k=1)
    assert found and "Sort the bars" in found[0].text
    block = section_anchors("A confession about a chart", [("Bars", "sort them")], "Go do it", passages)
    assert '<part name="opening">' in block and '<part name="closing">' in block and "<author_paragraph" in block
    assert section_anchors("hook", [], "close", []) == ""


def test_texture_finds_monotone_runs_and_generic_sentences() -> None:
    assert monotone_runs([10, 11, 12, 10, 30, 5, 6]) == [(0, 4)]
    author = author_texture([AUTHOR_POST] * 6)
    assert author is not None and author.specificity > 0
    report = texture_report(DRAFT, author)
    assert report.score < 100
    ids = {g.id for g in report.gaps if g.penalty > 0}
    assert "monotony" in ids or "length_mix" in ids
    assert report.outliers and all(o["quote"] and o["reason"] for o in report.outliers)
    assert "- " in report.text()
    # Too little text to judge: no penalty.
    assert texture_report("# T\n\nShort.", author).score == 100
    assert measure_texture([]).sentences == 0


def test_twin_scores_pairs_against_the_authors_paragraphs() -> None:
    passages = author_passages([("Pie charts", AUTHOR_POST)])
    pairs = build_pairs(DRAFT, passages, 4)
    assert pairs and all(p.author.text != p.draft for p in pairs)
    assert build_pairs(DRAFT, passages, 4)[0].draft_is_a == pairs[0].draft_is_a  # seeded by the text
    pair = Pair(1, "draft text", passages[0], "explain", draft_is_a=True)
    # Picked the author's passage (B) and was sure: caught, low score.
    assert pair_score(pair, TwinVerdict(pair=1, human="B", confidence=90, giveaway="tidy")) == (20, True, 90)
    # A coin flip: indistinguishable.
    assert pair_score(pair, TwinVerdict(pair=1, human="B", confidence=50, giveaway="")) == (100, False, 50)
    # Fooled: picked the draft as human.
    assert pair_score(pair, TwinVerdict(pair=1, human="A", confidence=80, giveaway=""))[0] == 100
    result = score_pairs([pair], TwinVerdicts(verdicts=[TwinVerdict(pair=1, human="B", confidence=90, giveaway="too tidy")]))
    assert result["caught"] == 1 and result["pairs"][0]["giveaway"] == "too tidy" and result["score"] == 20


def test_blend_shares_out_missing_weights() -> None:
    assert blend({"detectors": None, "judge": None, "scan": 80, "texture": 60}) == 70
    assert blend({"detectors": 100, "judge": 50, "scan": 50, "texture": 50}) == 70
    assert blend({}) == 100


def test_model_score_is_relative_to_the_author() -> None:
    assert model_score("curvature", 1.0, [0.8, 1.2, 1.0])[0] == 100
    assert model_score("curvature", 3.5, [0.8, 1.2, 1.0])[0] < 40
    # Without own posts the generic human range applies.
    assert model_score("classifier", 0.05, [])[0] == 100
    assert model_score("classifier", 0.9, [])[0] < 20


def test_detector_report_with_the_fake(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, _env_file=None)  # type: ignore[call-arg]
    detector = FakeDetector()
    found = asyncio.run(author_range(settings, detector, [AUTHOR_POST, AUTHOR_POST]))
    assert found is not None and len(found.posts["curvature"]) == 2
    result = asyncio.run(detector_report(settings=settings, detector=detector, markdown=DRAFT, author_texts=[AUTHOR_POST]))
    assert {m["id"] for m in result["models"]} == {"curvature", "classifier"}
    assert all(0 <= m["score"] <= 100 for m in result["models"]) and result["score"] is not None
    assert all(o["source"] == "detector" for o in result["outliers"])


def test_detectors_are_off_until_set_up(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, _env_file=None)  # type: ignore[call-arg]
    state = status(settings)
    assert not state["ready"] and not state["enabled"]
    assert status(Settings(data_dir=tmp_path, demo=True, _env_file=None))["enabled"]  # type: ignore[call-arg]


def test_worker_helpers_map_tokens_to_sentences() -> None:
    text, spans = join_spans(["One two.", "Three four five."])
    assert text == "One two. Three four five." and spans == [(0, 8), (9, 25)]
    offsets = [(0, 3), (4, 8), (9, 14), (15, 19), (20, 25)]
    assert assign_tokens(offsets, spans) == [[1], [2, 3, 4]]  # token 0 has no context
    assert ai_label_index({0: "Human", 1: "AI"}) == 1
    assert ai_label_index({0: "Fake", 1: "Real"}) == 0
    assert ai_label_index({0: "LABEL_0", 1: "LABEL_1"}) == 1


def test_analyze_uses_detectors_and_twin(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, _env_file=None)  # type: ignore[call-arg]
    profile = AuthorProfile(
        texts=[AUTHOR_POST], passages=author_passages([("Pie", AUTHOR_POST)]), texture=author_texture([AUTHOR_POST] * 6)
    )
    llm = FakeLLM()
    result = asyncio.run(analyze(llm=llm, settings=settings, markdown=DRAFT, voice_profile="", profile=profile, detector=FakeDetector()))
    assert result["judge_kind"] == "twin" and result["twin"]["total"] >= 1
    assert result["detectors"]["models"] and result["texture"]["gaps"] is not None
    assert "twin test" in llm.tasks() and "ai detection" not in llm.tasks()
    sources = {f["source"] for f in result["flagged"]}
    assert sources & {"detector", "twin", "texture"}


def test_humanize_rewrites_targets_and_keeps_the_better_version(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, demo=True, _env_file=None)  # type: ignore[call-arg]
    profile = AuthorProfile(
        texts=[AUTHOR_POST], passages=author_passages([("Pie", AUTHOR_POST)]), texture=author_texture([AUTHOR_POST] * 6)
    )
    llm = FakeLLM()
    text, checked = asyncio.run(
        humanize_post(llm=llm, settings=settings, system=[], markdown=DRAFT, voice_profile="", profile=profile, finish=lambda t: t)
    )
    assert checked is not None
    assert llm.tasks().count("humanize") <= settings.humanize_rounds
    if llm.tasks().count("humanize"):
        humanize_call = next(c for c in llm.calls if c["task"] == "humanize")
        assert "<targets>" in humanize_call["prompt"] and "<author_paragraph" in humanize_call["prompt"]
        assert DEMO_HUMANIZE in text or text == DRAFT  # a worse candidate is dropped
    # No rounds: nothing is checked or changed.
    off = Settings(data_dir=tmp_path, humanize_rounds=0, _env_file=None)  # type: ignore[call-arg]
    assert asyncio.run(
        humanize_post(llm=llm, settings=off, system=[], markdown=DRAFT, voice_profile="", profile=profile, finish=lambda t: t)
    ) == (DRAFT, None)
    assert (
        targets({"flagged": [{"quote": "a", "reason": "r", "source": "scan"}, {"quote": "b", "reason": "r", "source": "detector"}]})[0][
            "quote"
        ]
        == "b"
    )


def test_the_writer_may_invent_stories_but_not_facts() -> None:
    system = raw("writer_system")
    assert "invent what the author would bring" in system
    assert "never invent a quote or a source" in system
    assert "do not invent it: phrase it carefully or leave it out" not in system


def test_interview_answers_reach_the_prompts_and_skips_are_ignored() -> None:
    interview = [{"question": "Worst chart?", "answer": "A 3D exploding pie, 2019."}, {"question": "Who for?", "answer": "  "}]
    material = format_author_material(interview)
    assert "A 3D exploding pie" in material and "Who for?" not in material
    assert format_author_material([]) == "" and author_material_check(None) == ""
    assert "close to their wording" in author_material_check(interview)
