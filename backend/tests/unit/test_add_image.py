"""Where an added image may go, and how its slot id is chosen."""

from __future__ import annotations

from proseferno.writer.add_image import next_slot_id, place_placeholder

TAG = "{{image:img9}}"


def _place(markdown: str, after: str) -> str:
    return place_placeholder(markdown, markdown.index(after) + len(after), TAG)


def test_goes_after_the_paragraph_it_follows() -> None:
    post = "# T\n\n## One\n\nFirst point here. It matters.\n\nSecond paragraph.\n\n{{image:meme}}\n"
    out = _place(post, "It matters.")
    assert "First point here. It matters.\n\n" + TAG + "\n\nSecond paragraph." in out


def test_a_sentence_break_inside_a_long_paragraph_splits_it() -> None:
    post = "## One\n\nAlpha beta. Gamma delta. Epsilon zeta.\n\n{{image:meme}}\n"
    out = _place(post, "Alpha beta.")
    assert "Alpha beta.\n\n" + TAG + "\n\nGamma delta. Epsilon zeta." in out


def test_never_inside_a_code_block_list_or_quote() -> None:
    post = "Intro text.\n\n```python\nx = 1\n\ny = 2\n```\n\nAfter code.\n\n- one\n- two\n\n> quoted\n\n{{image:meme}}\n"
    assert "y = 2\n```\n\n" + TAG in _place(post, "x = 1")
    assert "- two\n\n" + TAG in _place(post, "- one")
    assert "> quoted\n\n" + TAG in _place(post, "quoted")


def test_a_lead_in_keeps_its_example_and_a_heading_moves_on() -> None:
    post = "## A\n\nHere is the file:\n\n```yaml\na: 1\n```\n\nAfterwards.\n\n{{image:meme}}\n"
    assert "```\n\n" + TAG + "\n\nAfterwards." in _place(post, "Here is the file:")
    assert "## A\n\nHere is the file:" in _place(post, "## A")  # the heading's own spot is skipped, not split


def test_never_after_the_closing_meme() -> None:
    post = "Body paragraph.\n\n{{image:meme}}\n\n## Go deeper\n\n- [a link](https://example.com)\n"
    out = _place(post, "a link")
    assert out.index(TAG) < out.index("{{image:meme}}")


def test_slot_ids_continue_the_numbering() -> None:
    assert next_slot_id({"hero", "img2", "img5", "meme"}) == "img6"
    assert next_slot_id({"hero", "meme"}) == "img2"
    assert next_slot_id({"x1", "x2"}) == "img2"
