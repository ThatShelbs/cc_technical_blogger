"""Pick which of the author's own posts to show the writer as full-length examples.

Topical similarity is a small TF-IDF cosine (see ingest.similarity).
"""

from __future__ import annotations

from collections.abc import Sequence

from inferno_ghostwriter.db import Sample
from inferno_ghostwriter.ingest.similarity import rank_by_similarity

__all__ = ["format_exemplars", "rank_by_similarity", "rank_own", "select_exemplars"]


def rank_own(query: str, samples: Sequence[Sample]) -> list[Sample]:
    """The author's own posts, most useful as an example first: topical similarity times the post's ``weight``."""
    own = [s for s in samples if s.kind == "own" and s.markdown]
    ranked = rank_by_similarity(query, [s.title + "\n" + s.markdown for s in own])
    scored = [(score * (own[index].weight or 1.0), -position, own[index]) for position, (index, score) in enumerate(ranked)]
    return [row[2] for row in sorted(scored, key=lambda row: (row[0], row[1]), reverse=True)]


def select_exemplars(query: str, samples: Sequence[Sample], *, max_posts: int = 3, max_words: int = 9000) -> list[Sample]:
    """Most topically similar own posts, within a word budget (whole posts, never truncated)."""
    chosen: list[Sample] = []
    words = 0
    for sample in rank_own(query, samples):
        if chosen and words + sample.word_count > max_words:
            continue
        chosen.append(sample)
        words += sample.word_count
        if len(chosen) >= max_posts:
            break
    return chosen


def format_exemplars(samples: Sequence[Sample]) -> str:
    parts = [
        "# Example posts by this author",
        "These are complete posts the author actually wrote. Match their voice, rhythm, humor and structure; "
        "never copy their sentences or reuse their specific jokes. `[IMAGE]` marks image positions and "
        "`[CAPTION]` lines show the author's caption/credit format.",
    ]
    for sample in samples:
        parts.append(f'<example_post title="{sample.title}">\n{sample.markdown}\n</example_post>')
    return "\n\n".join(parts)
