"""Learn from the author's edits: what they keep removing, replacing or asking for in generated posts.

A manual edit is diffed word by word against the generated text; short removals and swaps
become lessons (longer rewrites are content, not taste). Tweak feedback is kept verbatim.
Lessons live on the persona, most frequent first, and feed the writer and the next voice profile.
"""

from __future__ import annotations

import difflib
import re
from typing import Any, Literal

from proseferno.db import Persona, utcnow
from proseferno.images import PLACEHOLDER_RE

LessonKind = Literal["remove", "replace", "feedback"]
MAX_LESSONS = 40
# Longest removed or replaced span (in words) that still counts as a habit rather than a rewrite.
MAX_SPAN_WORDS = 8
MAX_PER_EDIT = 20
_WORD_RE = re.compile(r"\w")


def _words(markdown: str) -> list[str]:
    return PLACEHOLDER_RE.sub(" ", markdown).split()


def _meaningful(text: str) -> bool:
    return len(_WORD_RE.findall(text)) >= 2


def extract_lessons(before: str, after: str) -> list[dict[str, str]]:
    """Short removals and replacements between the generated text and the author's edit."""
    old, new = _words(before), _words(after)
    lessons: list[dict[str, str]] = []
    matcher = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op not in ("delete", "replace") or i2 - i1 > MAX_SPAN_WORDS or j2 - j1 > MAX_SPAN_WORDS:
            continue
        removed, added = " ".join(old[i1:i2]), " ".join(new[j1:j2])
        if not _meaningful(removed) or removed.strip(".,;:!?").casefold() == added.strip(".,;:!?").casefold():
            continue
        if op == "delete":
            lessons.append({"kind": "remove", "old": removed, "new": ""})
        else:
            lessons.append({"kind": "replace", "old": removed, "new": added})
        if len(lessons) >= MAX_PER_EDIT:
            break
    return lessons


def _key(lesson: dict[str, Any]) -> tuple[str, str, str]:
    return (str(lesson.get("kind")), str(lesson.get("old", "")).casefold(), str(lesson.get("new", "")).casefold())


def record_lessons(persona: Persona, new: list[dict[str, str]]) -> None:
    """Merge new lessons into the persona (counting repeats). The caller saves the persona."""
    if not new:
        return
    now = utcnow().isoformat()
    merged = {_key(lesson): dict(lesson) for lesson in (persona.edit_lessons or [])}
    for lesson in new:
        entry = merged.setdefault(_key(lesson), {**lesson, "count": 0})
        entry["count"] = int(entry.get("count", 0)) + 1
        entry["last_seen"] = now
    ranked = sorted(merged.values(), key=lambda e: (int(e.get("count", 1)), str(e.get("last_seen", ""))), reverse=True)
    # Reassign (not mutate) so SQLAlchemy notices the JSON change.
    persona.edit_lessons = ranked[:MAX_LESSONS]


def record_feedback(persona: Persona, feedback: str) -> None:
    text = " ".join(feedback.split())[:200]
    if text:
        record_lessons(persona, [{"kind": "feedback", "old": text, "new": ""}])


def format_lessons(lessons: list[dict[str, Any]] | None, limit: int = 15) -> str:
    """Markdown bullets for prompts; empty when there is nothing to learn yet."""
    lines = []
    for lesson in (lessons or [])[:limit]:
        times = int(lesson.get("count", 1))
        suffix = f" ({times} times)" if times > 1 else ""
        kind, old, new = lesson.get("kind"), lesson.get("old", ""), lesson.get("new", "")
        if kind == "remove":
            lines.append(f'- Cuts "{old}"{suffix}')
        elif kind == "replace":
            lines.append(f'- Changes "{old}" to "{new}"{suffix}')
        elif kind == "feedback":
            lines.append(f'- Asked: "{old}"{suffix}')
    return "\n".join(lines)
