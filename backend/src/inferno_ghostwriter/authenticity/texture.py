"""Texture: how a post's sentences are distributed compared with the author's own, and which sentences stand out.

The tell scan (heuristics) looks for stock words. Texture looks at shape: the mix of sentence lengths, how sentences
start, the small function words, punctuation habits, first person, how specific the sentences are, and runs of
same-length sentences. Model prose is smooth and even on all of these; real writing is lumpy in the author's own way.
Everything here is measured in code, with no model call.
"""

from __future__ import annotations

import math
import re
import statistics
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from inferno_ghostwriter.ingest.stylometrics import split_sentences

_WORD = re.compile(r"[A-Za-z][A-Za-z'’\-]*")
# Sentence-length bins (words): fragments, short, medium, long, very long, sprawling.
BINS = (6, 12, 18, 25, 35)
BIN_LABELS = ("1-6", "7-12", "13-18", "19-25", "26-35", "36+")
FUNCTION_WORDS = [
    "the",
    "a",
    "an",
    "and",
    "but",
    "or",
    "so",
    "because",
    "if",
    "then",
    "that",
    "which",
    "who",
    "what",
    "when",
    "where",
    "how",
    "why",
    "this",
    "these",
    "those",
    "it",
    "its",
    "i",
    "you",
    "we",
    "they",
    "my",
    "your",
    "our",
    "their",
    "me",
    "us",
    "them",
    "is",
    "was",
    "are",
    "were",
    "be",
    "been",
    "have",
    "has",
    "had",
    "do",
    "did",
    "not",
    "no",
    "just",
    "really",
    "actually",
    "very",
    "also",
    "only",
    "even",
    "still",
    "too",
    "of",
    "to",
    "in",
    "on",
    "for",
    "with",
    "at",
    "by",
    "from",
    "about",
    "as",
    "like",
]
_FIRST_PERSON = re.compile(r"\b(I|I'm|I’m|I've|I’ve|I'd|I’d|I'll|I’ll|me|my|mine)\b")
_SPECIFIC = re.compile(r"\d|`[^`]+`|\b[a-z]+_[a-z_]+\b|\b[a-z]+[A-Z]\w+\b|\b[A-Z]{2,}\b|(?<=[a-z,;:] )[A-Z][a-z]+")
_ABSTRACT = re.compile(r"\b\w{4,}(?:tion|sion|ity|ment|ness|ance|ence|ism|ology)s?\b", re.IGNORECASE)
MONOTONE_RUN = 4  # this many sentences in a row within MONOTONE_SPREAD words of each other
MONOTONE_SPREAD = 3
MAX_OUTLIERS = 12


@dataclass
class Texture:
    """The measured texture of a body of prose."""

    sentences: int = 0
    length_hist: list[float] = field(default_factory=lambda: [0.0] * len(BIN_LABELS))
    length_cv: float = 0.0
    openers: dict[str, float] = field(default_factory=dict)
    function_words: dict[str, float] = field(default_factory=dict)
    per_1k: dict[str, float] = field(default_factory=dict)
    first_person: float = 0.0
    specificity: float = 0.0
    monotony: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "sentences": self.sentences,
            "length_hist": [round(v, 3) for v in self.length_hist],
            "length_cv": round(self.length_cv, 3),
            "openers": {k: round(v, 3) for k, v in self.openers.items()},
            "first_person": round(self.first_person, 3),
            "specificity": round(self.specificity, 3),
            "monotony": round(self.monotony, 3),
            "per_1k": {k: round(v, 2) for k, v in self.per_1k.items()},
        }


def prose_sentences(markdown: str) -> list[str]:
    """Sentences of the post's prose, as written (code, images, headings and list markers removed)."""
    from inferno_ghostwriter.authenticity.heuristics import _extract  # heuristics imports nothing from here

    text = _extract(markdown)
    out: list[str] = []
    for block in text.paragraphs + text.list_items:
        out.extend(s for s in split_sentences(block) if _WORD.search(s))
    return out


def _bin(length: int) -> int:
    return next((i for i, edge in enumerate(BINS) if length <= edge), len(BINS))


def _plain(sentence: str) -> str:
    return re.sub(r"[*_`]", "", sentence)


def _opener(sentence: str) -> str:
    words = _WORD.findall(_plain(sentence))
    return words[0].lower() if words else ""


def is_specific(sentence: str) -> bool:
    return bool(_SPECIFIC.search(sentence))


def monotone_runs(lengths: Sequence[int]) -> list[tuple[int, int]]:
    """(start, end) of every run of at least MONOTONE_RUN sentences whose lengths stay within MONOTONE_SPREAD words."""
    runs: list[tuple[int, int]] = []
    if not lengths:
        return runs
    start, low, high = 0, lengths[0], lengths[0]
    for i in range(1, len(lengths)):
        new_low, new_high = min(low, lengths[i]), max(high, lengths[i])
        if new_high - new_low <= MONOTONE_SPREAD:
            low, high = new_low, new_high
            continue
        if i - start >= MONOTONE_RUN:
            runs.append((start, i))
        start, low, high = i, lengths[i], lengths[i]
    if len(lengths) - start >= MONOTONE_RUN:
        runs.append((start, len(lengths)))
    return runs


def measure_texture(sentences: Sequence[str]) -> Texture:
    if not sentences:
        return Texture()
    lengths = [len(_WORD.findall(s)) for s in sentences]
    words = [w.lower() for s in sentences for w in _WORD.findall(_plain(s))]
    n_words = max(1, len(words))
    n = len(sentences)
    hist = [0.0] * len(BIN_LABELS)
    for length in lengths:
        hist[_bin(length)] += 1 / n
    counts = Counter(words)
    joined = " ".join(sentences)
    openers = Counter(_opener(s) for s in sentences)
    mean = statistics.fmean(lengths)
    in_runs = sum(end - start for start, end in monotone_runs(lengths))
    return Texture(
        sentences=n,
        length_hist=hist,
        length_cv=statistics.pstdev(lengths) / mean if mean else 0.0,
        openers={w: c / n for w, c in openers.most_common(25) if w},
        function_words={w: 1000 * counts[w] / n_words for w in FUNCTION_WORDS},
        per_1k={
            "parentheses": 1000 * joined.count("(") / n_words,
            "colons": 1000 * joined.count(":") / n_words,
            "semicolons": 1000 * joined.count(";") / n_words,
            "questions": 100 * sum(1 for s in sentences if s.rstrip("*_ ").endswith("?")) / n,
            "exclamations": 100 * sum(1 for s in sentences if s.rstrip("*_ ").endswith("!")) / n,
        },
        first_person=sum(1 for s in sentences if _FIRST_PERSON.search(s)) / n,
        specificity=sum(1 for s in sentences if is_specific(s)) / n,
        monotony=in_runs / n,
    )


def author_texture(texts: Sequence[str]) -> Texture | None:
    """The author's texture over all their own posts; None when there is too little to go on."""
    sentences = [s for t in texts for s in prose_sentences(t)]
    return measure_texture(sentences) if len(sentences) >= 40 else None


def _cosine_distance(a: dict[str, float], b: dict[str, float]) -> float:
    keys = set(a) | set(b)
    dot = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return 1.0 - dot / (na * nb) if na and nb else 0.0


@dataclass
class Gap:
    id: str
    label: str
    detail: str
    penalty: float

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id, "label": self.label, "detail": self.detail, "penalty": round(self.penalty, 1)}


@dataclass
class TextureReport:
    score: int
    gaps: list[Gap]
    outliers: list[dict[str, str]]
    draft: Texture
    author: Texture | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "gaps": [g.as_dict() for g in self.gaps],
            "outliers": self.outliers,
            "draft": self.draft.as_dict(),
            "author": self.author.as_dict() if self.author else None,
        }

    def text(self) -> str:
        """Bullet list for the editor prompt."""
        lines = [f"- {g.label}: {g.detail}" for g in self.gaps if g.penalty > 0]
        lines += [f'- "{o["quote"]}" ({o["reason"]})' for o in self.outliers]
        return "\n".join(lines) or "- The texture already matches the author's."


def _pct(value: float) -> str:
    return f"{round(100 * value)}%"


def texture_report(markdown: str, author: Texture | None) -> TextureReport:
    """Where the draft's texture differs most from the author's, and the sentences that cause it."""
    sentences = prose_sentences(markdown)
    draft = measure_texture(sentences)
    gaps: list[Gap] = []
    reference = author or Texture(
        # Without the author's own posts, compare with plain human writing: lumpy lengths, some specifics, few long runs.
        length_hist=[0.14, 0.24, 0.24, 0.19, 0.13, 0.06],
        length_cv=0.6,
        specificity=0.35,
        monotony=0.12,
        first_person=0.2,
    )
    if draft.sentences < 8:
        return TextureReport(score=100, gaps=[], outliers=[], draft=draft, author=author)

    # 1. Sentence-length mix (L1 distance between the histograms: 0 = identical, 2 = disjoint).
    l1 = sum(abs(a - b) for a, b in zip(draft.length_hist, reference.length_hist, strict=True))
    worst = max(range(len(BIN_LABELS)), key=lambda i: abs(draft.length_hist[i] - reference.length_hist[i]))
    direction = "too many" if draft.length_hist[worst] > reference.length_hist[worst] else "too few"
    gaps.append(
        Gap(
            "length_mix",
            "Sentence-length mix",
            f"{direction} {BIN_LABELS[worst]}-word sentences ({_pct(draft.length_hist[worst])} vs the author's "
            f"{_pct(reference.length_hist[worst])}); vary lengths the way the author does",
            min(30.0, 40 * max(0.0, l1 - 0.2)),
        )
    )
    # 2. Runs of same-length sentences.
    extra_runs = draft.monotony - max(reference.monotony, 0.05)
    gaps.append(
        Gap(
            "monotony",
            "Even rhythm",
            f"{_pct(draft.monotony)} of sentences sit in runs of {MONOTONE_RUN}+ similar-length sentences "
            f"(author: {_pct(reference.monotony)}); break the runs",
            min(20.0, 60 * max(0.0, extra_runs)),
        )
    )
    # 3. Specificity: numbers, names, code identifiers.
    short = reference.specificity - draft.specificity
    gaps.append(
        Gap(
            "specificity",
            "Generic sentences",
            f"{_pct(draft.specificity)} of sentences carry a number, name or identifier (author: {_pct(reference.specificity)}); "
            "swap abstractions for the brief's real specifics",
            min(20.0, 60 * max(0.0, short - 0.05)),
        )
    )
    # 4. First person.
    fp_gap = reference.first_person - draft.first_person
    gaps.append(
        Gap(
            "first_person",
            "Missing first person",
            f'{_pct(draft.first_person)} of sentences speak as "I" (author: {_pct(reference.first_person)})',
            min(12.0, 40 * max(0.0, fp_gap - 0.06)) if author else 0.0,
        )
    )
    # 5. Function words (the classic stylometric fingerprint) and openers.
    if author:
        fw = _cosine_distance(draft.function_words, author.function_words)
        gaps.append(
            Gap(
                "function_words",
                "Small-word fingerprint",
                f"the mix of small words (the, and, just, really, so...) is {round(100 * fw)}% off the author's",
                min(10.0, 200 * max(0.0, fw - 0.03)),
            )
        )
    overused = [
        (w, share)
        for w, share in draft.openers.items()
        if share >= 0.06 and share > 2.5 * (reference.openers.get(w, 0.0) + 0.01) and author is not None
    ]
    if overused:
        listed = ", ".join(f'"{w.capitalize()}" ({_pct(s)})' for w, s in overused[:4])
        gaps.append(
            Gap(
                "openers",
                "Sentence openers",
                f"{listed} start far more sentences than in the author's posts; start them the way the author does",
                min(10.0, 5.0 * len(overused)),
            )
        )
    gaps = sorted(gaps, key=lambda g: g.penalty, reverse=True)
    score = max(0, min(100, round(100 - sum(g.penalty for g in gaps))))

    outliers = _outliers(sentences, reference, {w for w, _ in overused})
    return TextureReport(score=score, gaps=gaps, outliers=outliers, draft=draft, author=author)


def _outliers(sentences: Sequence[str], reference: Texture, overused_openers: set[str]) -> list[dict[str, str]]:
    lengths = [len(_WORD.findall(s)) for s in sentences]
    found: dict[int, str] = {}
    for start, end in monotone_runs(lengths):
        found.setdefault(start + 1, f"one of {end - start} sentences in a row of the same length")
    for i, sentence in enumerate(sentences):
        if i in found:
            continue
        if not is_specific(sentence) and len(_ABSTRACT.findall(sentence)) >= 2 and reference.specificity >= 0.2:
            found[i] = "abstract and generic; say the specific thing"
        elif _opener(sentence) in overused_openers:
            found[i] = f'another sentence opening with "{_opener(sentence).capitalize()}"'
    picked = sorted(found.items())[:MAX_OUTLIERS]
    return [{"quote": sentences[i].strip(), "reason": reason} for i, reason in picked]
