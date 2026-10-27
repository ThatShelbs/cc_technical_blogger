"""Deterministic scan for the tells that make prose read as AI-generated.

Each signal costs points from 100. The scan is calibrated to the author: a word or
habit that appears in the author's own posts (em dashes, "robust", short sentences)
is not held against them. Fast, free, and explainable; the Claude judge in
:mod:`proseferno.authenticity.detector` adds a holistic read on top.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from proseferno.ingest.stylometrics import split_sentences

# Vocabulary and stock phrases that are far more common in model output than in human technical blogs.
AI_VOCABULARY = [
    "delve",
    "delves",
    "delving",
    "tapestry",
    "testament to",
    "realm",
    "ever-evolving",
    "ever-changing",
    "fast-paced",
    "game-changer",
    "game changer",
    "cutting-edge",
    "groundbreaking",
    "revolutionize",
    "unlock",
    "unlocking",
    "unleash",
    "harness the power",
    "elevate",
    "embark",
    "seamless",
    "seamlessly",
    "pivotal",
    "intricate",
    "multifaceted",
    "holistic",
    "paradigm shift",
    "synergy",
    "myriad",
    "plethora",
    "bustling",
    "meticulous",
    "meticulously",
    "commendable",
    "noteworthy",
    "invaluable",
    "foster",
    "fostering",
    "underscore",
    "underscores",
    "showcase",
    "showcasing",
    "navigate the complexities",
    "navigating the",
    "landscape of",
    "in the realm of",
    "a testament",
    "resonate",
    "resonates",
    "vibrant",
    "crucial role",
    "plays a crucial",
    "plays a vital",
    "vital role",
    "key takeaway",
    "dive deep",
    "deep dive",
    "dive into",
    "let's dive",
    "buckle up",
    "secret sauce",
    "at the end of the day",
    "in today's",
    "in this day and age",
    "it's important to note",
    "it is important to note",
    "it's worth noting",
    "it is worth noting",
    "worth noting that",
    "rest assured",
    "a nuanced",
    "nuanced understanding",
    "robust",
    "streamline",
    "empower",
    "empowers",
    "transformative",
    "journey",
]

# Formulaic constructions, each with a short reason shown to the user.
FORMULAS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"\b(?:it'?s|it is|this is|that'?s|that is) not (?:just |only |merely |simply )?[^.;:!?]{1,60}[.;,—–-]+\s*(?:it'?s|it is)\b",
            re.I,
        ),
        "“It's not X, it's Y” framing",
    ),
    (re.compile(r"\bnot (?:just|only|merely) [^.;:!?]{1,60},? but (?:also )?", re.I), "“Not just X, but Y” construction"),
    (
        re.compile(
            r"\b(?:isn'?t|aren'?t|wasn'?t) (?:just |only |merely )?about [^.;:!?]{1,50}[.;,—–-]+\s*(?:it'?s|they'?re|it was) about\b", re.I
        ),
        "“It isn't about X, it's about Y”",
    ),
    (re.compile(r"\bhere'?s the (?:thing|kicker|catch|twist|deal)\b", re.I), "“Here's the thing” setup"),
    (
        re.compile(r"(?:^|\n|\. )(?:The result|The kicker|The catch|The best part|The answer|The twist|The problem)\?\s", re.I),
        "Rhetorical question-then-answer beat",
    ),
    (re.compile(r"\blet that sink in\b", re.I), "“Let that sink in”"),
    (re.compile(r"\bin a world where\b", re.I), "“In a world where” opener"),
    (re.compile(r"\bwhether you'?re an? [^.;:!?]{1,40} or an? [^.;:!?]{1,40}\b", re.I), "“Whether you're a X or a Y” audience hedge"),
    (re.compile(r"\b(?:imagine|picture) this\b", re.I), "“Imagine this” opener"),
    (re.compile(r"\bthe (?:real )?magic happens\b", re.I), "“The magic happens” cliché"),
    (re.compile(r"\b(?:and that'?s|that'?s) (?:where|when) [^.;:!?]{1,40} comes? in\b", re.I), "“That's where X comes in” transition"),
]

TRANSITION_OPENERS = re.compile(
    r"^(?:Moreover|Furthermore|Additionally|In addition|Consequently|Ultimately|Overall|Notably|Importantly|Interestingly|"
    r"In conclusion|In summary|To summarize|To sum up|In essence|Essentially|Thus|Hence),",
    re.I,
)
GENERIC_ENDING = re.compile(
    r"\b(?:in conclusion|in summary|to sum up|ultimately|at the end of the day|the future (?:is|of)|remember,|"
    r"happy (?:coding|building|analyzing)|the possibilities are endless|exciting times|stay curious)\b",
    re.I,
)
TRIPLET = re.compile(r"\b[\w'’-]+(?: [\w'’-]+){0,2}, [\w'’-]+(?: [\w'’-]+){0,2},? and [\w'’-]+(?: [\w'’-]+){0,2}\b")
EMOJI = re.compile("[\U0001f300-\U0001faff☀-➿⭐✅]")
_WORD = re.compile(r"[A-Za-z][A-Za-z'’\-]*")


@dataclass
class Signal:
    id: str
    label: str
    penalty: float
    detail: str
    value: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id, "label": self.label, "penalty": round(self.penalty, 1), "detail": self.detail, "value": self.value}


@dataclass
class Flag:
    quote: str
    reason: str
    suggestion: str = ""
    source: str = "scan"

    def as_dict(self) -> dict[str, Any]:
        return {"quote": self.quote, "reason": self.reason, "suggestion": self.suggestion, "source": self.source}


@dataclass
class AuthorProfile:
    """What the author really does, so the scan does not punish their genuine habits."""

    vocabulary: set[str] = field(default_factory=set)
    sentence_cv: float | None = None
    em_dash_per_1k: float | None = None
    contractions_per_1k: float | None = None


@dataclass
class ScanResult:
    score: int
    signals: list[Signal]
    flags: list[Flag]
    word_count: int

    def tells_text(self) -> str:
        """Bullet list for the editor prompt."""
        lines = [f"- {s.label}: {s.detail}" for s in self.signals if s.penalty > 0]
        lines += [f'- "{f.quote}" ({f.reason})' for f in self.flags[:12]]
        return "\n".join(lines) or "- None found."


# -- text extraction -------------------------------------------------------------


@dataclass
class _Text:
    paragraphs: list[str]
    list_items: list[str]
    headings: list[str]

    @property
    def prose(self) -> str:
        return "\n\n".join(self.paragraphs + self.list_items)


def _extract(markdown: str) -> _Text:
    text = re.sub(r"```.*?```", "", markdown, flags=re.S)
    text = re.sub(r"\{\{image:[^}]+\}\}|!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    paragraphs: list[str] = []
    items: list[str] = []
    headings: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            paragraphs.append(" ".join(buffer).strip())
            buffer.clear()

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            flush()
        elif re.match(r"^\[(?:IMAGE|CAPTION)\]", line):
            flush()  # image and caption markers in imported samples are not prose
        elif line.startswith("#"):
            flush()
            headings.append(line.lstrip("# ").strip())
        elif re.match(r"^(?:[-*+]|\d+[.)])\s+", line):
            flush()
            items.append(re.sub(r"^(?:[-*+]|\d+[.)])\s+", "", line))
        elif line.startswith(">"):
            buffer.append(line.lstrip("> "))
        elif re.fullmatch(r"\*[^*].*\*", line) and not paragraphs:
            continue  # italic subtitle under the title
        else:
            buffer.append(line)
    flush()
    return _Text([p for p in paragraphs if p], items, headings)


def _plain(text: str) -> str:
    return re.sub(r"[*_`]", "", text)


def _cv(values: list[int]) -> float | None:
    values = [v for v in values if v > 0]
    if len(values) < 5:
        return None
    mean = statistics.fmean(values)
    return statistics.pstdev(values) / mean if mean else None


def _count_terms(lowered: str, terms: list[str]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for term in terms:
        hits = len(re.findall(rf"(?<![a-z]){re.escape(term)}(?![a-z])", lowered))
        if hits:
            counts[term] = hits
    return counts


def profile_author(texts: list[str], baseline: dict[str, Any] | None = None) -> AuthorProfile:
    """Learn which tells are really the author's own habits."""
    joined = "\n\n".join(texts)
    lowered = _plain(joined).lower()
    words = max(1, len(_WORD.findall(lowered)))
    used = _count_terms(lowered, AI_VOCABULARY)
    # A term counts as the author's own if they use it at least twice, or once per ~5k words.
    vocabulary = {t for t, c in used.items() if c >= 2 or c * 5000 >= words}
    sentence_lengths = [len(_WORD.findall(s)) for t in texts for s in split_sentences(_plain(_extract(t).prose))]
    baseline = baseline or {}
    return AuthorProfile(
        vocabulary=vocabulary,
        sentence_cv=_cv(sentence_lengths),
        em_dash_per_1k=baseline.get("em_dash_per_1k"),
        contractions_per_1k=baseline.get("contractions_per_1k"),
    )


# -- the scan -------------------------------------------------------------------------


def scan(markdown: str, author: AuthorProfile | None = None) -> ScanResult:
    author = author or AuthorProfile()
    extracted = _extract(markdown)
    prose = _plain(extracted.prose)
    lowered = prose.lower()
    words = _WORD.findall(prose)
    n_words = max(1, len(words))
    per_1k = 1000 / n_words
    sentences = split_sentences(prose)
    n_sentences = max(1, len(sentences))
    signals: list[Signal] = []
    flags: list[Flag] = []

    def flag_sentence(pattern: re.Pattern[str] | str, reason: str, limit: int = 3) -> None:
        found = 0
        for sentence in sentences:
            if (pattern.search(sentence) if isinstance(pattern, re.Pattern) else pattern in sentence.lower()) and found < limit:
                if not any(f.quote == sentence for f in flags):
                    flags.append(Flag(quote=sentence.strip()[:400], reason=reason))
                found += 1

    # 1. Stock AI vocabulary the author does not use themselves.
    terms = _count_terms(lowered, [t for t in AI_VOCABULARY if t not in author.vocabulary])
    hits = sum(terms.values())
    rate = hits * per_1k
    signals.append(
        Signal(
            "ai_vocabulary",
            "Stock AI vocabulary",
            min(28.0, rate * 7),
            ", ".join(f"“{t}” ×{c}" if c > 1 else f"“{t}”" for t, c in terms.most_common(8)) or "None found.",
            round(rate, 2),
        )
    )
    for term, _ in terms.most_common(6):
        flag_sentence(re.compile(rf"(?<![a-z]){re.escape(term)}(?![a-z])", re.I), f"Stock AI phrasing: “{term}”", limit=1)

    # 2. Formulaic constructions.
    formula_hits: Counter[str] = Counter()
    for pattern, reason in FORMULAS:
        count = len(pattern.findall(prose))
        if count:
            formula_hits[reason] += count
            flag_sentence(pattern, reason, limit=2)
    total = sum(formula_hits.values())
    signals.append(
        Signal(
            "formulas",
            "Formulaic constructions",
            min(22.0, total * per_1k * 6),
            ", ".join(f"{r} ×{c}" if c > 1 else r for r, c in formula_hits.most_common()) or "None found.",
            total,
        )
    )

    # 3. Uniform sentence lengths (low "burstiness").
    cv = _cv([len(_WORD.findall(s)) for s in sentences])
    if cv is not None:
        target = min(0.55, (author.sentence_cv or 0.6) * 0.85)
        penalty = 0.0 if cv >= target else min(16.0, (target - cv) / target * 32)
        signals.append(
            Signal(
                "burstiness",
                "Sentence rhythm variety",
                penalty,
                f"Sentence-length variation {cv:.2f} (yours ≈ {author.sentence_cv:.2f})."
                if author.sentence_cv
                else f"Sentence-length variation {cv:.2f}.",
                round(cv, 3),
            )
        )

    # 4. Uniform paragraph sizes.
    pcv = _cv([len(_WORD.findall(p)) for p in extracted.paragraphs])
    if pcv is not None:
        signals.append(
            Signal(
                "paragraphs",
                "Paragraph shape variety",
                0.0 if pcv >= 0.4 else min(8.0, (0.4 - pcv) * 30),
                f"Paragraph-length variation {pcv:.2f}.",
                round(pcv, 3),
            )
        )

    # 5. Em dashes beyond the author's own rate.
    dashes = prose.count("—") + prose.count(" – ") + prose.count(" -- ")
    dash_rate = dashes * per_1k
    allowed = max(2.0, (author.em_dash_per_1k or 0) * 1.5)
    signals.append(
        Signal(
            "em_dashes",
            "Em-dash density",
            min(14.0, max(0.0, dash_rate - allowed) * 2.5),
            f"{dash_rate:.1f} per 1,000 words (yours ≈ {author.em_dash_per_1k:.1f})."
            if author.em_dash_per_1k is not None
            else f"{dash_rate:.1f} per 1,000 words.",
            round(dash_rate, 2),
        )
    )

    # 6. Essay-style transition openers.
    openers = [s for s in sentences if TRANSITION_OPENERS.match(s.strip())]
    opener_rate = 100 * len(openers) / n_sentences
    signals.append(
        Signal(
            "transitions",
            "Essay transitions (Moreover, Furthermore…)",
            min(12.0, opener_rate * 3),
            f"{len(openers)} sentence(s) open with a stock transition." if openers else "None found.",
            round(opener_rate, 2),
        )
    )
    for sentence in openers[:2]:
        flags.append(Flag(quote=sentence.strip()[:400], reason="Stock transition opener"))

    # 7. Reflexive rule-of-three lists in prose.
    triplets = len(TRIPLET.findall(_plain("\n\n".join(extracted.paragraphs))))
    triplet_rate = triplets * per_1k
    signals.append(
        Signal(
            "triplets",
            "Rule-of-three lists",
            min(10.0, max(0.0, triplet_rate - 3) * 3),
            f"{triplets} “X, Y, and Z” list(s) in prose.",
            round(triplet_rate, 2),
        )
    )

    # 8. Bulleted "**Term:** explanation" lists.
    bold_lead = sum(1 for item in extracted.list_items if re.match(r"^\*\*[^*]{1,60}\*\*\s*[:—–-]", item))
    share = bold_lead / len(extracted.list_items) if extracted.list_items else 0.0
    signals.append(
        Signal(
            "bold_bullets",
            "“**Term:** explanation” bullets",
            8.0 if bold_lead >= 3 and share >= 0.4 else 0.0,
            f"{bold_lead} of {len(extracted.list_items)} list items." if extracted.list_items else "No lists.",
            bold_lead,
        )
    )

    # 9. Emoji in headings and bullets.
    emoji = sum(len(EMOJI.findall(t)) for t in extracted.headings + extracted.list_items)
    signals.append(
        Signal("emoji", "Emoji in headings or bullets", min(8.0, emoji * 2.0), f"{emoji} emoji." if emoji else "None found.", emoji)
    )

    # 10. A generic, tidy ending.
    last = extracted.paragraphs[-1] if extracted.paragraphs else ""
    generic = bool(GENERIC_ENDING.search(last))
    signals.append(
        Signal(
            "ending",
            "Generic wrap-up ending",
            8.0 if generic else 0.0,
            "The last paragraph reads like a stock summary." if generic else "Ending looks specific.",
            int(generic),
        )
    )
    if generic:
        flags.append(
            Flag(
                quote=split_sentences(_plain(last))[0][:400] if split_sentences(_plain(last)) else last[:400], reason="Stock summary ending"
            )
        )

    # 11. Too few contractions compared with the author.
    contractions = sum(1 for w in words if "'" in w or "’" in w) * per_1k
    if author.contractions_per_1k:
        low = contractions < author.contractions_per_1k * 0.5
        signals.append(
            Signal(
                "contractions",
                "Contractions vs. your usual rate",
                8.0 if low else 0.0,
                f"{contractions:.1f} per 1,000 words (yours ≈ {author.contractions_per_1k:.1f}).",
                round(contractions, 2),
            )
        )

    score = round(max(0.0, min(100.0, 100 - sum(s.penalty for s in signals))))
    return ScanResult(score=score, signals=signals, flags=flags[:15], word_count=len(words))
