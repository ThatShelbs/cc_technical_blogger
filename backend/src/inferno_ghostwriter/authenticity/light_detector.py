"""The light detector: a quick, built-in read of machine rhythm. No model, no download, standard library only.

It is the default detector because it costs nothing: it scores a post in milliseconds, runs in the app's own process and
works on a fresh install. It looks at what language models smooth out:

- **even sentence lengths** (low variation, and little change from one sentence to the next),
- **few human markers** (contractions, "I" and "you", questions, asides, dashes, semicolons),
- **concrete detail** (numbers, names, code, quotes) and
- **repeated openings** ("This ...", "This ...", "It ...").

Like the heavier models it is compared with the author's own posts (``local_detector.model_score``), so the number
means "how much more machine-like than you", not an absolute probability. It is a rougher signal than the trained
models, which can be selected next to it in Settings; use more than one for a firmer read.

Scores run from 0 (varied, personal, concrete) to 1 (even, impersonal, generic).
"""

from __future__ import annotations

import itertools
import re
import statistics
from collections.abc import Sequence

from inferno_ghostwriter.authenticity.texture import is_specific

# Words that make a sentence sound like a person talking.
_MARKERS = re.compile(
    r"(?:\b\w+'\w+\b)|(?:\b(?:I|me|my|mine|we|our|you|your|yours)\b)|\?|!|\(|\)|;|—|–| - |\.\.\.",
    re.IGNORECASE,
)
_WORD = re.compile(r"[A-Za-z0-9']+")

# Human blog prose sits below these on each signal; the machine-like end of each scale is 1.
EVEN_CV = 0.8  # sentence-length variation (stdev / mean) of varied prose
EVEN_STEP = 0.7  # mean change between neighbouring sentences, relative to the mean length
MARKERS_PER_SENTENCE = 0.6
OPENER_REPEAT = 0.1
MIN_SENTENCES = 6


def _clip(value: float) -> float:
    return max(0.0, min(1.0, value))


def _lengths(sentences: Sequence[str]) -> list[int]:
    return [len(_WORD.findall(s)) for s in sentences]


def _opener(sentence: str) -> str:
    words = _WORD.findall(sentence)
    return words[0].lower() if words else ""


def _repeated_openers(sentences: Sequence[str]) -> list[bool]:
    """True where a sentence starts with the same word as one of the three before it."""
    openers = [_opener(s) for s in sentences]
    return [bool(o) and o in openers[max(0, i - 3) : i] for i, o in enumerate(openers)]


def _marker_count(sentence: str) -> int:
    return len(_MARKERS.findall(sentence))


def score_sentences(sentences: Sequence[str]) -> list[float | None]:
    """Per sentence: 0-1 machine-likeness from its length against the post's, its markers, its detail and its opening."""
    lengths = _lengths(sentences)
    if len(sentences) < MIN_SENTENCES:
        return [None] * len(sentences)
    median = statistics.median(lengths) or 1
    repeated = _repeated_openers(sentences)
    out: list[float | None] = []
    for sentence, length, again in zip(sentences, lengths, repeated, strict=True):
        typical = _clip(1 - abs(length - median) / median)  # close to the post's usual length reads even
        voiceless = 0.0 if _marker_count(sentence) else 1.0
        generic = 0.0 if is_specific(sentence) else 1.0
        out.append(round(0.3 * typical + 0.3 * voiceless + 0.25 * generic + 0.15 * (1.0 if again else 0.0), 3))
    return out


def score_text(sentences: Sequence[str]) -> float | None:
    """The post's 0-1 machine-likeness, or None when there is too little prose to judge."""
    if len(sentences) < MIN_SENTENCES:
        return None
    lengths = _lengths(sentences)
    mean = statistics.fmean(lengths)
    if mean <= 0:
        return None
    variation = statistics.pstdev(lengths) / mean
    step = statistics.fmean(abs(a - b) for a, b in itertools.pairwise(lengths)) / mean
    markers = statistics.fmean(_marker_count(s) for s in sentences)
    specific = statistics.fmean(1.0 if is_specific(s) else 0.0 for s in sentences)
    repeats = statistics.fmean(1.0 if r else 0.0 for r in _repeated_openers(sentences))
    signals = (
        _clip((EVEN_CV - variation) / 0.4),
        _clip((EVEN_STEP - step) / 0.45),
        _clip(1 - markers / MARKERS_PER_SENTENCE),
        _clip(1 - specific / 0.35),
        _clip((repeats - OPENER_REPEAT) / 0.3),
    )
    return round(statistics.fmean(signals), 3)


def light_result(sentences: Sequence[str]) -> dict[str, object]:
    """One text's result in the shape the other detectors use: ``{"score": float | None, "sentences": [...]}``."""
    return {"score": score_text(sentences), "sentences": score_sentences(sentences)}
