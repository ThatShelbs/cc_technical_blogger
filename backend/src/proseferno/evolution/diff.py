"""Compare the generated baseline with the text the author published."""

from __future__ import annotations

import difflib
import hashlib
import re
from typing import Any

from proseferno.images import PLACEHOLDER_RE
from proseferno.voice.lessons import words

_TOKEN_RE = re.compile(r"\s+|[^\s]+")


def baseline_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def edit_rate(baseline: str, final: str) -> float:
    """Share of the text the author changed, 0 (untouched) to 1 (rewritten). Image placeholders are ignored."""
    before, after = words(baseline), words(final)
    if not before and not after:
        return 0.0
    return round(1.0 - difflib.SequenceMatcher(a=before, b=after, autojunk=False).ratio(), 4)


def diff_segments(baseline: str, final: str) -> list[dict[str, Any]]:
    """Word-level segments for a side-by-side reading: [{op: equal|insert|delete, text}], whitespace kept."""
    before = _TOKEN_RE.findall(PLACEHOLDER_RE.sub("", baseline))
    after = _TOKEN_RE.findall(PLACEHOLDER_RE.sub("", final))
    segments: list[dict[str, Any]] = []

    def push(op: str, text: str) -> None:
        if not text:
            return
        if segments and segments[-1]["op"] == op:
            segments[-1]["text"] += text
        else:
            segments.append({"op": op, "text": text})

    matcher = difflib.SequenceMatcher(a=before, b=after, autojunk=False)
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            push("equal", "".join(before[i1:i2]))
            continue
        if op in ("delete", "replace"):
            push("delete", "".join(before[i1:i2]))
        if op in ("insert", "replace"):
            push("insert", "".join(after[j1:j2]))
    return segments


def _paragraphs(markdown: str) -> list[str]:
    text = PLACEHOLDER_RE.sub("", markdown)
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def diff_digest(baseline: str, final: str, max_words: int = 6000) -> str:
    """The changed paragraphs, before and after, for a prompt. Unchanged paragraphs are left out."""
    before, after = _paragraphs(baseline), _paragraphs(final)
    blocks: list[str] = []
    used = 0
    matcher = difflib.SequenceMatcher(a=before, b=after, autojunk=False)
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            continue
        old, new = "\n\n".join(before[i1:i2]), "\n\n".join(after[j1:j2])
        if op == "delete":
            block = f"REMOVED:\n{old}"
        elif op == "insert":
            block = f"ADDED:\n{new}"
        else:
            block = f"GENERATED:\n{old}\n\nPUBLISHED:\n{new}"
        size = len(block.split())
        if used + size > max_words:
            blocks.append("[More changes left out for length.]")
            break
        blocks.append(block)
        used += size
    return "\n\n---\n\n".join(blocks)
