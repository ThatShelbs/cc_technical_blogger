from __future__ import annotations

import itertools

from proseferno.db import Persona
from proseferno.evolution import diff_digest, diff_segments, edit_rate
from proseferno.evolution.service import add_rules
from proseferno.voice.playbook import MAX_PLAYBOOK, add_playbook, forget_playbook, format_playbook

BASE = "# Title\n\n{{image:hero}}\n\nFirst paragraph stays the same.\n\nIt is worth noting that this one changes.\n\nLast one."


def test_edit_rate_ignores_images_and_measures_change() -> None:
    assert edit_rate(BASE, BASE) == 0
    assert edit_rate(BASE, BASE.replace("{{image:hero}}", "")) == 0
    assert edit_rate("", "") == 0
    assert 0 < edit_rate(BASE, BASE.replace("It is worth noting that this one", "This one")) < 0.5
    assert edit_rate("one two three", "four five six") == 1


def test_diff_segments_rebuild_both_texts() -> None:
    after = BASE.replace("It is worth noting that this one", "This one")
    segments = diff_segments(BASE, after)
    old = "".join(s["text"] for s in segments if s["op"] != "insert")
    new = "".join(s["text"] for s in segments if s["op"] != "delete")
    assert old == BASE.replace("{{image:hero}}", "") and new == after.replace("{{image:hero}}", "")
    assert all(a["op"] != b["op"] for a, b in itertools.pairwise(segments))


def test_diff_digest_shows_only_changed_paragraphs() -> None:
    after = BASE.replace("It is worth noting that this one changes.", "This one changes.") + "\n\nA new closing line."
    digest = diff_digest(BASE, after)
    assert "GENERATED:\nIt is worth noting" in digest and "PUBLISHED:\nThis one changes." in digest
    assert "ADDED:\nA new closing line." in digest
    assert "First paragraph" not in digest
    assert "left out for length" in diff_digest("a\n\nb", "c " * 50 + "\n\nd " * 50, max_words=10)


def test_playbook_ranks_dedupes_and_caps() -> None:
    persona = Persona(name="P")
    add_playbook(persona, ["Small trick"], project_id=1, title="One", outcome="good")
    added = add_playbook(persona, ["Big trick", "small TRICK", ""], project_id=2, title="Two", outcome="viral")
    assert added == 1
    assert [e["text"] for e in persona.playbook] == ["Big trick", "Small trick"]
    assert format_playbook(persona.playbook).splitlines()[0] == '- Big trick (viral post: "Two")'
    add_playbook(persona, [f"Trick {i}" for i in range(30)], project_id=3, title="Three", outcome="good")
    assert len(persona.playbook) == MAX_PLAYBOOK and persona.playbook[0]["text"] == "Big trick"
    forget_playbook(persona, 0)
    assert persona.playbook[0]["text"] != "Big trick"
    forget_playbook(persona, None)
    assert persona.playbook == [] and format_playbook(persona.playbook) == ""


def test_add_rules_extends_or_creates_do_dont() -> None:
    profile = "# Voice\n\n## Do / Don't\n\n- Old rule\n\n## Voice Anchors\n\n> quote\n"
    out = add_rules(profile, ["New rule"])
    assert "- Old rule\n- New rule\n\n## Voice Anchors" in out
    out = add_rules("# Voice\n\n## Lexicon\nwords\n\n## Voice Anchors\n> q\n", ["Rule"])
    assert "## Do / Don't\n\n- Rule\n\n## Voice Anchors" in out
    assert add_rules("# Voice\n", ["Rule"]).endswith("## Do / Don't\n\n- Rule\n\n")
    assert add_rules(profile, []) == profile
