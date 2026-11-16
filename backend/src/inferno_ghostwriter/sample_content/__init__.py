"""Bundled sample writing, so a first run works without any files of your own.

Three short posts by a fictional "Sample Author" teach a voice profile something to
learn from, and ``voice_profile.md`` is what a finished profile looks like. They ship
as package data next to the code, like the prompts.
"""

from __future__ import annotations

from importlib import resources

SAMPLE_AUTHOR = "Sample Author"
SAMPLE_POSTS = ("dashboards-nobody-opens.md", "peeking-at-your-ab-test.md", "notebook-to-production.md")


def sample_posts() -> list[tuple[str, bytes]]:
    """(file name, Markdown bytes) for each bundled sample post."""
    root = resources.files(__package__)
    return [(name, root.joinpath(name).read_bytes()) for name in SAMPLE_POSTS]


def example_voice_profile() -> str:
    return resources.files(__package__).joinpath("voice_profile.md").read_text(encoding="utf-8")
