"""Take a part of one post into another: the title, the opener or the closer (pure text; no model call).

A post reads: title block (``# title``, italic subtitle, hero image), opener (everything before the first ``##``),
sections, an optional "Go deeper" list, the meme. Image placeholders inside a part travel with its text: they get
a free ``imgN`` id in the receiving post, and the caller moves the image rows to match (``Splice.moved``); images
that sat in the replaced text are reported in ``Splice.dropped``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from proseferno.images import PLACEHOLDER_RE

# Parts the author can take from the other post of an A/B test.
PARTS = ("title", "opener", "closer", "hero", "meme", "image_style")
_FIXED_SLOTS = ("hero", "meme")
_GO_DEEPER_RE = re.compile(r"^##\s+(go deeper|further reading|read more|keep reading|resources)\b", re.IGNORECASE)


@dataclass
class Splice:
    markdown: str
    # Image slots that came with the text: {slot id in the other post: new slot id in this post}.
    moved: dict[str, str] = field(default_factory=dict)
    # Slots of this post whose placeholder was in the replaced text.
    dropped: list[str] = field(default_factory=list)


def _is_placeholder(line: str, slot: str | None = None) -> bool:
    match = PLACEHOLDER_RE.fullmatch(line.strip())
    return match is not None and (slot is None or match.group(1) == slot)


def _is_subtitle(line: str) -> bool:
    stripped = line.strip()
    return len(stripped) > 2 and stripped[0] in "*_" and stripped[-1] in "*_" and not stripped.startswith("**")


def _header_end(lines: list[str]) -> int:
    """Index of the first line after the title block (title, subtitle, hero image)."""
    end = 0
    seen_title = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# ") and not seen_title:
            seen_title = True
        elif seen_title and (_is_subtitle(stripped) or _is_placeholder(stripped, "hero")):
            pass
        else:
            break
        end = i + 1
    return end


def _first_heading(lines: list[str], start: int = 0) -> int:
    return next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))


def opener_span(markdown: str) -> tuple[int, int]:
    """Line span of the opener: after the title block, up to the first ``##`` (or the meme when there are no sections)."""
    lines = markdown.splitlines()
    start = _header_end(lines)
    end = _first_heading(lines, start)
    if end == len(lines):
        end = next((i for i in range(start, len(lines)) if _is_placeholder(lines[i], "meme")), len(lines))
    return start, end


def closer_span(markdown: str) -> tuple[int, int] | None:
    """Line span of the last real section (heading included), ending before a "Go deeper" list or the meme."""
    lines = markdown.splitlines()
    headings = [i for i, line in enumerate(lines) if line.startswith("## ") and not _GO_DEEPER_RE.match(line)]
    if not headings:
        return None
    start = headings[-1]
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## ") or _is_placeholder(lines[i], "meme"):
            end = i
            break
    return start, end


def _slots(lines: list[str]) -> list[str]:
    return [m.group(1) for line in lines for m in PLACEHOLDER_RE.finditer(line)]


def _free_slot(taken: set[str]) -> str:
    number = max((int(m.group(1)) for s in taken if (m := re.fullmatch(r"img(\d+)", s))), default=1) + 1
    while f"img{number}" in taken:
        number += 1
    return f"img{number}"


def _replace(base: str, span: tuple[int, int], incoming: list[str]) -> Splice:
    lines = base.splitlines()
    start, end = span
    dropped = [s for s in _slots(lines[start:end]) if s not in _FIXED_SLOTS]
    kept = lines[:start] + lines[end:]
    taken = set(_slots(kept)) | set(_FIXED_SLOTS)
    moved: dict[str, str] = {}
    out: list[str] = []
    for line in incoming:
        match = PLACEHOLDER_RE.fullmatch(line.strip())
        if match:
            slot = match.group(1)
            if slot in _FIXED_SLOTS:
                continue  # the hero and the meme keep their own places
            if slot not in moved:
                moved[slot] = _free_slot(taken)
                taken.add(moved[slot])
            line = f"{{{{image:{moved[slot]}}}}}"
        out.append(line)
    body = "\n".join(out).strip("\n")
    merged = lines[:start] + ([""] if start and lines[start - 1].strip() else []) + ([body, ""] if body else []) + lines[end:]
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(merged)).strip("\n") + "\n"
    return Splice(markdown=text, moved=moved, dropped=dropped)


def take_opener(base: str, other: str) -> Splice:
    """``base`` with its opener replaced by the other post's."""
    lines = other.splitlines()
    start, end = opener_span(other)
    return _replace(base, opener_span(base), lines[start:end])


def take_closer(base: str, other: str) -> Splice:
    """``base`` with its last section replaced by the other post's last section (unchanged if either has none)."""
    mine, theirs = closer_span(base), closer_span(other)
    if mine is None or theirs is None:
        return Splice(markdown=base)
    lines = other.splitlines()
    return _replace(base, mine, lines[theirs[0] : theirs[1]])


def take_title(base: str, other: str) -> str:
    """``base`` with the other post's title and subtitle lines."""

    def head(markdown: str) -> tuple[list[str], list[str]]:
        lines = markdown.splitlines()
        end = _header_end(lines)
        return lines[:end], lines[end:]

    theirs, _ = head(other)
    mine, rest = head(base)
    block = [line for line in theirs if line.strip() and not _is_placeholder(line)]
    if not block:
        return base
    hero = [line for line in mine if _is_placeholder(line, "hero")]
    out: list[str] = []
    for line in [*block, *hero]:
        out += [line, ""]
    text = "\n".join(out + rest)
    return re.sub(r"\n{3,}", "\n\n", text).strip("\n") + "\n"
