"""X: a teaser post that announces the X Article.

Posts on X are limited to 280 characters (links count as 23), and X Article headers are 5:2.
"""

from __future__ import annotations

from proseferno.export.linkedin import sections
from proseferno.ingest.stylometrics import split_sentences
from proseferno.writer import split_title

POST_LIMIT = 280
HEADER_SIZE = (1500, 600)


def teaser_post(markdown: str) -> str:
    """A ready-to-edit post that shares the article: its hook, then the title."""
    title, subtitle = split_title(markdown)
    intro, _ = sections(markdown)
    closer = f"New article: “{title}”" if title else "New article on my profile."
    room = POST_LIMIT - len(closer) - 2
    hook = ""
    for sentence in split_sentences(intro[0]) if intro else []:
        candidate = f"{hook} {sentence}".strip()
        if len(candidate) > room:
            break
        hook = candidate
    if not hook and subtitle and len(subtitle) <= room:
        hook = subtitle
    text = f"{hook}\n\n{closer}" if hook else closer
    return text if len(text) <= POST_LIMIT else text[: POST_LIMIT - 1].rstrip() + "…"
