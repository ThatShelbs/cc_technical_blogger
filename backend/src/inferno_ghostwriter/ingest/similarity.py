"""A small TF-IDF cosine similarity: plenty for a handful of posts or paragraphs, with no model call or dependency."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence

from inferno_ghostwriter.ingest.stylometrics import STOPWORDS

_TOKEN = re.compile(r"[a-z][a-z0-9\-]+")


def tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in STOPWORDS and len(t) > 2]


def rank_by_similarity(query: str, docs: Sequence[str]) -> list[tuple[int, float]]:
    """Return (index, score) pairs, most similar first."""
    tokenized = [tokens(d) for d in docs]
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

    q = vector(tokens(query))
    scores = [(i, cosine(q, vector(toks))) for i, toks in enumerate(tokenized)]
    return sorted(scores, key=lambda pair: pair[1], reverse=True)
