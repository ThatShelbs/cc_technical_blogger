"""The twin test: can Claude tell a passage of the post from a real paragraph by the author?

Passages from the post are paired with the author's own paragraphs that do the same job (an opening with an opening,
a story with a story) and are about as long. Claude sees each pair blind, in shuffled order, and says which one a
human wrote, how sure it is, and what gave the other away. A pair it cannot tell apart is the goal; a giveaway it names
is exactly what the humanize pass fixes. Unlike asking "does this read as AI?", the bar is the author's real writing.
"""

from __future__ import annotations

import hashlib
import random
import statistics
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field

from inferno_ghostwriter.authenticity.passages import ROLE_LABEL, Passage, anchor_passages, tagged
from inferno_ghostwriter.config import Settings
from inferno_ghostwriter.llm import LLM, SystemBlock
from inferno_ghostwriter.llm.base import UsageSink
from inferno_ghostwriter.prompts import raw, render

MIN_WORDS = 30
CAUGHT = 65  # a correct pick at least this sure counts as caught


class TwinVerdict(BaseModel):
    pair: int = Field(description="The pair number.")
    human: Literal["A", "B"] = Field(description="The passage a human wrote.")
    confidence: int = Field(description="50 (a coin flip) to 100 (certain).")
    giveaway: str = Field(
        description="What gave the machine-written passage away, quoting a few of its words; empty if you could not tell."
    )


class TwinVerdicts(BaseModel):
    verdicts: list[TwinVerdict]


@dataclass
class Pair:
    number: int
    draft: str
    author: Passage
    role: str
    draft_is_a: bool


def build_pairs(markdown: str, passages: list[Passage], count: int) -> list[Pair]:
    """Up to ``count`` passages spread through the post, each with the author's closest paragraph of the same role."""
    candidates = [(p, role) for p, role in tagged(markdown) if p.words >= MIN_WORDS]
    if not candidates or not passages or count <= 0:
        return []
    if len(candidates) > count:
        step = len(candidates) / count
        candidates = [candidates[int(i * step + step / 2)] for i in range(count)]
    # Seeded by the text, so checking the same post twice asks the same question.
    rng = random.Random(int(hashlib.sha256(markdown.encode()).hexdigest()[:12], 16))
    pairs: list[Pair] = []
    used: set[str] = set()
    for paragraph, role in candidates:
        found = anchor_passages(paragraph.text, passages, (role,), k=1, exclude=used, near_words=paragraph.words)
        if not found:
            continue
        used.add(found[0].text)
        pairs.append(Pair(len(pairs) + 1, paragraph.text, found[0], role, rng.random() < 0.5))
    return pairs


def format_pairs(pairs: list[Pair]) -> str:
    blocks = []
    for pair in pairs:
        a, b = (pair.draft, pair.author.text) if pair.draft_is_a else (pair.author.text, pair.draft)
        blocks.append(f'<pair number="{pair.number}">\n<A>\n{a}\n</A>\n<B>\n{b}\n</B>\n</pair>')
    return "\n\n".join(blocks)


def pair_score(pair: Pair, verdict: TwinVerdict | None) -> tuple[int, bool, int]:
    """(0-100 where 100 = indistinguishable, caught, the judge's certainty that the post's passage is the AI one)."""
    if verdict is None:
        return 100, False, 50
    confidence = max(50, min(100, verdict.confidence))
    author_label = "B" if pair.draft_is_a else "A"
    correct = verdict.human == author_label
    p_ai = confidence / 100 if correct else 1 - confidence / 100
    return round(100 * min(1.0, 2 * (1 - p_ai))), correct and confidence >= CAUGHT, round(100 * p_ai)


def score_pairs(pairs: list[Pair], verdicts: TwinVerdicts) -> dict[str, Any]:
    by_number = {v.pair: v for v in verdicts.verdicts}
    rows: list[dict[str, Any]] = []
    scores: list[int] = []
    for pair in pairs:
        verdict = by_number.get(pair.number)
        score, caught, p_ai = pair_score(pair, verdict)
        scores.append(score)
        rows.append(
            {
                "quote": pair.draft,
                "role": pair.role,
                "role_label": ROLE_LABEL.get(pair.role, pair.role),
                "score": score,
                "caught": caught,
                "ai_certainty": p_ai,
                "giveaway": (verdict.giveaway.strip() if verdict and caught else ""),
                "anchor": pair.author.text,
            }
        )
    return {
        "score": round(statistics.fmean(scores)) if scores else None,
        "caught": sum(1 for r in rows if r["caught"]),
        "total": len(rows),
        "pairs": rows,
    }


async def twin_test(
    *, llm: LLM, settings: Settings, markdown: str, passages: list[Passage], usage: UsageSink | None = None, count: int | None = None
) -> dict[str, Any] | None:
    """Run the blind test; None when the author has no paragraphs to compare with or the post is too short."""
    pairs = build_pairs(markdown, passages, settings.twin_pairs if count is None else count)
    if not pairs:
        return None
    verdicts = await llm.structured(
        task="twin test",
        system=[SystemBlock(raw("twin_system"), cache=True)],
        prompt=render("twin", pairs=format_pairs(pairs), count=len(pairs)),
        schema=TwinVerdicts,
        effort=settings.effort_twin,
        usage=usage,
    )
    return score_pairs(pairs, verdicts)
