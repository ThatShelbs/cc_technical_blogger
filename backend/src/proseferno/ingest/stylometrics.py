"""Deterministic writing-style measurements.

These numbers ground the voice synthesis in fact (the model is told the real
average sentence length rather than guessing it) and let us score how close
a generated draft is to the author's baseline.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from typing import Any

from proseferno.ingest.document import ParsedDocument

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])[\"”’)]*\s+(?=[\"“‘(]?[A-Z0-9])")
_WORD = re.compile(r"[A-Za-z][A-Za-z'’\-]*")
STOPWORDS = set(
    [
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "if",
        "then",
        "so",
        "of",
        "to",
        "in",
        "on",
        "at",
        "by",
        "for",
        "with",
        "from",
        "as",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "there",
        "here",
        "i",
        "you",
        "he",
        "she",
        "we",
        "they",
        "me",
        "my",
        "your",
        "our",
        "their",
        "his",
        "her",
        "them",
        "us",
        "not",
        "no",
        "yes",
        "do",
        "does",
        "did",
        "done",
        "have",
        "has",
        "had",
        "will",
        "would",
        "can",
        "could",
        "should",
        "may",
        "might",
        "must",
        "just",
        "also",
        "very",
        "than",
        "too",
        "into",
        "over",
        "about",
        "out",
        "up",
        "down",
        "more",
        "most",
        "some",
        "any",
        "all",
        "each",
        "other",
        "such",
        "only",
        "own",
        "same",
        "what",
        "which",
        "who",
        "whom",
        "when",
        "where",
        "why",
        "how",
        "s",
        "t",
        "don",
        "isn",
        "aren",
        "wasn",
        "weren",
        "won",
        "ll",
        "ve",
        "re",
        "d",
        "m",
    ]
)

# Features compared when scoring a draft against the persona baseline, with tolerance scale.
FIDELITY_FEATURES: dict[str, float] = {
    "avg_sentence_words": 6.0,
    "avg_paragraph_words": 30.0,
    "short_paragraph_ratio": 0.25,
    "question_per_100_sentences": 8.0,
    "exclamation_per_100_sentences": 6.0,
    "first_person_singular_per_1k": 15.0,
    "second_person_per_1k": 15.0,
    "contractions_per_1k": 10.0,
    "flesch_reading_ease": 15.0,
    "words_per_heading": 250.0,
    "words_per_image": 250.0,
}


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


def _syllables(word: str) -> int:
    word = word.lower().strip("'’-")
    if len(word) <= 3:
        return 1
    word = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", word)
    word = re.sub(r"^y", "", word)
    return max(1, len(re.findall(r"[aeiouy]{1,2}", word)))


def compute(doc: ParsedDocument) -> dict[str, Any]:
    paragraphs = [b.text for b in doc.blocks if b.kind in ("paragraph", "quote")]
    body = " ".join(paragraphs)
    sentences = split_sentences(body)
    words = _WORD.findall(body)
    n_words = max(1, len(words))
    n_sentences = max(1, len(sentences))
    sentence_lengths = [len(_WORD.findall(s)) for s in sentences] or [0]
    para_sentence_counts = [len(split_sentences(p)) for p in paragraphs] or [0]
    syllables = sum(_syllables(w) for w in words)
    lower = [w.lower() for w in words]
    counts = Counter(lower)
    all_words = doc.word_count
    headings = sum(1 for b in doc.blocks if b.kind == "heading")
    list_items = sum(1 for b in doc.blocks if b.kind == "list_item")
    images = doc.image_count

    def per_1k(n: int) -> float:
        return round(1000 * n / n_words, 2)

    fre = 206.835 - 1.015 * (len(words) / n_sentences) - 84.6 * (syllables / n_words)
    fk = 0.39 * (len(words) / n_sentences) + 11.8 * (syllables / n_words) - 15.59

    return {
        "word_count": all_words,
        "sentence_count": len(sentences),
        "paragraph_count": len(paragraphs),
        "avg_sentence_words": round(statistics.fmean(sentence_lengths), 2),
        "median_sentence_words": statistics.median(sentence_lengths),
        "p90_sentence_words": _percentile(sentence_lengths, 0.9),
        "avg_paragraph_words": round(len(words) / max(1, len(paragraphs)), 2),
        "avg_paragraph_sentences": round(statistics.fmean(para_sentence_counts), 2),
        "short_paragraph_ratio": round(sum(1 for c in para_sentence_counts if c <= 1) / max(1, len(paragraphs)), 3),
        "flesch_reading_ease": round(fre, 1),
        "flesch_kincaid_grade": round(fk, 1),
        "question_per_100_sentences": round(100 * sum(1 for s in sentences if s.endswith("?")) / n_sentences, 2),
        "exclamation_per_100_sentences": round(100 * sum(1 for s in sentences if s.endswith("!")) / n_sentences, 2),
        "first_person_singular_per_1k": per_1k(
            sum(counts[w] for w in ("i", "me", "my", "mine", "i'm", "i’m", "i've", "i’ve", "i'd", "i’d"))
        ),
        "first_person_plural_per_1k": per_1k(sum(counts[w] for w in ("we", "us", "our", "ours", "we're", "we’re"))),
        "second_person_per_1k": per_1k(sum(counts[w] for w in ("you", "your", "yours", "you're", "you’re", "you'll", "you’ll"))),
        "contractions_per_1k": per_1k(sum(1 for w in lower if "'" in w or "’" in w)),
        "em_dash_per_1k": per_1k(body.count("—") + body.count(" - ") + body.count("--")),
        "parentheticals_per_1k": per_1k(body.count("(")),
        "heading_count": headings,
        "words_per_heading": round(all_words / headings, 1) if headings else None,
        "list_item_count": list_items,
        "code_block_count": sum(1 for b in doc.blocks if b.kind == "code"),
        "image_count": images,
        "words_per_image": round(all_words / images, 1) if images else None,
        "caption_count": len(doc.captions),
        "opening_style": _opening_style(paragraphs[0] if paragraphs else ""),
        "top_phrases": _top_phrases(lower),
    }


def aggregate(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    """Average numeric features across samples; merge phrase lists."""
    if not metrics:
        return {}
    out: dict[str, Any] = {"samples": len(metrics)}
    keys = {k for m in metrics for k, v in m.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    for key in sorted(keys):
        values = [m[key] for m in metrics if isinstance(m.get(key), (int, float))]
        if values:
            out[key] = round(statistics.fmean(values), 2)
    openings = Counter(m.get("opening_style") for m in metrics if m.get("opening_style"))
    out["opening_styles"] = dict(openings.most_common())
    phrases = Counter(p for m in metrics for p in m.get("top_phrases", []))
    out["recurring_phrases"] = [p for p, c in phrases.most_common(15) if c > 1]
    return out


def fidelity(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Score 0–100 for how closely a draft's measurable style matches the baseline."""
    scores: dict[str, float] = {}
    for feature, tolerance in FIDELITY_FEATURES.items():
        base, cand = baseline.get(feature), candidate.get(feature)
        if not isinstance(base, (int, float)) or not isinstance(cand, (int, float)):
            continue
        scores[feature] = round(max(0.0, 1.0 - abs(base - cand) / (2 * tolerance)) * 100, 1)
    overall = round(statistics.fmean(scores.values()), 1) if scores else None
    return {"score": overall, "features": scores}


def _percentile(values: list[int], q: float) -> float:
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))
    return float(ordered[idx])


def _opening_style(first: str) -> str:
    text = first.strip()
    if not text:
        return "none"
    first_sentence = split_sentences(text)[0] if split_sentences(text) else text
    if first_sentence.endswith("?"):
        return "question"
    if re.search(r"\d", first_sentence):
        return "fact_or_statistic"
    if re.match(r"^(I|My|When I|Last|Recently|A few|Yesterday|Years ago)\b", first_sentence):
        return "personal_anecdote"
    if re.search(r"\b(you|your)\b", first_sentence, re.IGNORECASE):
        return "direct_address"
    return "statement"


def _top_phrases(words: list[str], n: int = 12) -> list[str]:
    grams: Counter[str] = Counter()
    for size in (2, 3):
        for i in range(len(words) - size + 1):
            gram = words[i : i + size]
            if gram[0] in STOPWORDS or gram[-1] in STOPWORDS:
                continue
            grams[" ".join(gram)] += 1
    return [g for g, c in grams.most_common(n) if c >= 2]
