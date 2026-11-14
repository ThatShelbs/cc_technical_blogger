from __future__ import annotations

from proseferno.writer import ensure_placeholders, normalize_slots
from proseferno.writer.dials import auto_image_count
from proseferno.writer.examples import add_example_slots, find_dangling_leadins, format_missing_examples
from proseferno.writer.pipeline import strip_image_captions
from proseferno.writer.schemas import ImageSlot

POST = """# Title

*Subtitle*

{{image:hero}}

## Building it

Here is the top of the actual file:

Most of it is house rules.

Here is what I will cover:

- One
- Two

Here is the config:

```toml
name = "x"   # a colon inside code: is fine
```

**Memes:** The first jokes fell flat. Here is one of the early ones:

## Next section

Here is the loop:

{{image:img2}}

Here is how it works:

> A quote.

And here is how that felt:

{{image:meme}}
"""


def slots() -> list[ImageSlot]:
    return normalize_slots([ImageSlot(slot_id="a", kind="diagram", section_index=1, purpose="p", brief="b")], 3, 2)


def test_finds_lead_ins_with_nothing_after_them() -> None:
    found = find_dangling_leadins(POST)
    assert found == [
        "Here is the top of the actual file:",
        "**Memes:** The first jokes fell flat. Here is one of the early ones:",
    ]
    assert '- "Here is one of the early ones:"' in format_missing_examples(POST)
    assert format_missing_examples("# T\n\nNothing promised here.\n") == "- None found."


def test_dangling_lead_ins_get_drawn_examples_without_changing_the_text() -> None:
    markdown, new = add_example_slots(POST, slots())

    # Reading order: the two new examples come before the planned loop diagram.
    assert [s.slot_id for s in new] == ["hero", "img3", "img4", "img2", "meme"]
    added = {s.slot_id: s for s in new}
    assert added["img3"].kind == "screenshot" and added["img3"].purpose == "Here is the top of the actual file:"
    assert "Most of it is house rules." in added["img3"].brief
    assert markdown.index("Here is the top of the actual file:") < markdown.index("{{image:img3}}") < markdown.index("house rules")
    assert markdown.index("early ones:") < markdown.index("{{image:img4}}") < markdown.index("## Next section")
    assert find_dangling_leadins(markdown) == []
    # Only placeholder lines were added.
    added_lines = ("{{image:img3}}", "{{image:img4}}")
    assert [line for line in markdown.splitlines() if line and line not in added_lines] == [line for line in POST.splitlines() if line]

    # The finished post keeps them (and the lead-in is not mistaken for an image caption).
    final = ensure_placeholders(markdown, new)
    assert "{{image:img4}}" in final and "Here is one of the early ones:" in final


def test_an_introduced_made_up_placeholder_becomes_a_slot() -> None:
    markdown = "# T\n\n## One\n\n{{image:img2}}\n\nHere is the chart of signups:\n\n{{image:signup_chart}}\n\n{{image:extra}}\n\nMore.\n"
    fixed, new = add_example_slots(markdown, slots(), fill_dangling=False)

    assert [s.slot_id for s in new] == ["hero", "img2", "img3", "meme"]
    assert new[2].kind == "chart" and new[2].purpose == "Here is the chart of signups:"
    assert "{{image:img3}}" in fixed and "signup_chart" not in fixed
    # Nobody introduced the second one, so it is still dropped and the chosen image count holds.
    assert "{{image:extra}}" not in ensure_placeholders(fixed, new)


def test_nothing_to_add_leaves_the_post_alone() -> None:
    markdown = "# T\n\nHere is the list:\n\n- a\n"
    original = slots()
    assert add_example_slots(markdown, original) == (markdown, original)


def test_lead_in_next_to_an_image_is_not_a_caption() -> None:
    markdown = "**Memes:** The jokes fell flat. Here is one:\n\n{{image:img2}}\n\nImage: a robot\n"
    assert strip_image_captions(markdown) == "**Memes:** The jokes fell flat. Here is one:\n\n{{image:img2}}\n\n"


def test_image_count_follows_the_authors_cadence() -> None:
    assert auto_image_count(1600) == 5
    assert auto_image_count(1600, 175) == 9
    assert auto_image_count(1600, 40) == 11  # never denser than one per 150 words
    assert auto_image_count(5000, 175) == 12
