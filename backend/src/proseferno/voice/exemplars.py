"""Pick which of the author's own posts to show the writer as full-length examples.

A small TF-IDF cosine similarity is plenty for a handful of posts and needs no
extra model call or dependency.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence

from proseferno.db import Sample
from proseferno.ingest.stylometrics import STOPWORDS

_TOKEN = re.compile(r"[a-z][a-z0-9\-]+")


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in STOPWORDS and len(t) > 2]


def rank_by_similarity(query: str, docs: Sequence[str]) -> list[tuple[int, float]]:
    """Return (index, score) pairs, most similar first."""
    tokenized = [_tokens(d) for d in docs]
    n = len(docs)
    df: Counter[str] = Counter()
    for toks in tokenized:
        df.update(set(toks))

    def vector(toks: list[str]) -> dict[str, float]:
        tf = Counter(toks)
        return {t: (c / max(1, len(toks))) * (math.log((1 + n) / (1 + df[t])) + 1) for t, c in tf.items()}

    def cosine(a: dict[str, float], b: dict[str, float]) -> float:
        dot = sum(v * b.get(k, 0.0) for k, v in a.items())
        na = math.sqrt(sum(v * v for v in a.values()))
        nb = math.sqrt(sum(v * v for v in b.values()))
        return dot / (na * nb) if na and nb else 0.0

    q = vector(_tokens(query))
    scores = [(i, cosine(q, vector(toks))) for i, toks in enumerate(tokenized)]
    return sorted(scores, key=lambda pair: pair[1], reverse=True)


def select_exemplars(query: str, samples: Sequence[Sample], *, max_posts: int = 3, max_words: int = 9000) -> list[Sample]:
    """Most topically similar own posts, within a word budget (whole posts, never truncated)."""
    own = [s for s in samples if s.kind == "own" and s.markdown]
    if not own:
        return []
    ranked = rank_by_similarity(query, [s.title + "\n" + s.markdown for s in own])
    chosen: list[Sample] = []
    words = 0
    for index, _score in ranked:
        sample = own[index]
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
