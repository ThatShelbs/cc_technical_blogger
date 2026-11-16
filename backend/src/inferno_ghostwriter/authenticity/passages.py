"""The author's real paragraphs, tagged by the job they do, so a draft can be written (and tested) against them.

A paragraph's role comes from cheap rules, never a model call: where it sits in the post, first person and past
tense (a story), opinion words, a colon at the end (it introduces a list or example), or its length.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from inferno_ghostwriter.ingest.similarity import rank_by_similarity

Role = Literal["opener", "story", "explain", "opinion", "transition", "list_intro", "closer"]
ROLES: tuple[Role, ...] = ("opener", "story", "explain", "opinion", "transition", "list_intro", "closer")
ROLE_LABEL: dict[str, str] = {
    "opener": "an opening",
    "story": "a story or first-hand experience",
    "explain": "an explanation",
    "opinion": "an opinion",
    "transition": "a short bridge",
    "list_intro": "a lead-in to a list or example",
    "closer": "a closing",
}
# A paragraph short enough to be a bridge, and the range worth showing as an example.
TRANSITION_WORDS = 25
MIN_WORDS, MAX_WORDS = 20, 220

_WORD = re.compile(r"[A-Za-z][A-Za-z'’\-]*")
_FIRST_PERSON = re.compile(r"\b(I|I'm|I’m|I've|I’ve|I'd|I’d|me|my|we|our)\b")
_PAST = re.compile(
    r"\b(was|were|had|did|got|went|made|took|found|tried|spent|built|broke|learned|realized|asked|told|said|"
    r"yesterday|last (?:week|month|year|time)|years? ago|once|back when|at the time)\b|\b\w{3,}ed\b",
    re.IGNORECASE,
)
_OPINION = re.compile(
    r"\b(I think|I believe|I'd argue|I’d argue|honestly|frankly|in my (?:view|opinion|experience)|my take|the truth is|"
    r"should|shouldn't|shouldn’t|never|always|overrated|underrated|stop|please|wrong|best|worst|hate|love)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Paragraph:
    """One prose paragraph as written (Markdown kept), with where it sits."""

    text: str
    section: int  # -1 before the first ## heading
    heading: str
    index: int  # among the post's prose paragraphs

    @property
    def words(self) -> int:
        return len(_WORD.findall(self.text))


@dataclass(frozen=True)
class Passage:
    text: str
    role: Role
    words: int
    title: str = ""


def split_paragraphs(markdown: str) -> list[Paragraph]:
    """Prose paragraphs only: code, images, captions, headings, lists, tables and the title block are left out."""
    paragraphs: list[Paragraph] = []
    buffer: list[str] = []
    section, heading, in_code = -1, "", False

    def flush() -> None:
        text = "\n".join(buffer).strip()
        buffer.clear()
        if text and _WORD.search(text):
            paragraphs.append(Paragraph(text=text, section=section, heading=heading, index=len(paragraphs)))

    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            flush()
            in_code = not in_code
            continue
        if in_code:
            continue
        if not line:
            flush()
        elif line.startswith("## ") or line.startswith("### "):
            flush()
            if line.startswith("## "):
                section += 1
                heading = line[3:].strip()
        elif (
            line.startswith(("#", "|", "{{image:", "![", "[IMAGE]", "[CAPTION]"))
            or re.match(r"^(?:[-*+]|\d+[.)])\s+", line)
            or (re.fullmatch(r"[*_][^*_].*[*_]", line) and not paragraphs and not buffer)
        ):
            flush()  # structure, not prose (an italic line before any prose is the subtitle)
        else:
            buffer.append(raw_line.rstrip())
    flush()
    return paragraphs


def tag_role(paragraph: Paragraph, total: int) -> Role:
    text = paragraph.text
    if paragraph.index == 0:
        return "opener"
    if paragraph.index >= total - 1 and total > 2:
        return "closer"
    if text.rstrip(" *_").endswith(":"):
        return "list_intro"
    words = paragraph.words
    first_person = len(_FIRST_PERSON.findall(text))
    past = len(_PAST.findall(text))
    if first_person >= 1 and past >= 2:
        return "story"
    if len(_OPINION.findall(text)) >= 2 or (first_person and _OPINION.search(text)):
        return "opinion"
    if words <= TRANSITION_WORDS:
        return "transition"
    return "explain"


def tagged(markdown: str) -> list[tuple[Paragraph, Role]]:
    paragraphs = split_paragraphs(markdown)
    return [(p, tag_role(p, len(paragraphs))) for p in paragraphs]


def author_passages(posts: Sequence[tuple[str, str]]) -> list[Passage]:
    """Every usable paragraph from the author's own posts, given as (title, markdown) pairs."""
    out: list[Passage] = []
    for title, markdown in posts:
        for paragraph, role in tagged(markdown):
            if MIN_WORDS <= paragraph.words <= MAX_WORDS or (role in ("transition", "opener", "closer") and paragraph.words >= 6):
                out.append(Passage(text=paragraph.text, role=role, words=paragraph.words, title=title))
    return out


def anchor_passages(
    query: str,
    passages: Sequence[Passage],
    roles: Sequence[str] | None = None,
    *,
    k: int = 2,
    exclude: set[str] | None = None,
    near_words: int | None = None,
) -> list[Passage]:
    """The author's paragraphs most like ``query`` among ``roles`` (any role when none match), from different posts first."""
    exclude = exclude or set()
    pool = [p for p in passages if p.text not in exclude and (not roles or p.role in roles)]
    if not pool:
        pool = [p for p in passages if p.text not in exclude]
    if not pool:
        return []
    ranked = rank_by_similarity(query, [p.text for p in pool])

    def closeness(index: int) -> float:
        return 1.0 if near_words is None else 1.0 / (1.0 + abs(pool[index].words - near_words) / max(20, near_words))

    order = sorted(ranked, key=lambda pair: (pair[1] + 0.05) * closeness(pair[0]), reverse=True)
    chosen: list[Passage] = []
    titles: set[str] = set()
    for second_pass in (False, True):
        for index, _score in order:
            passage = pool[index]
            if passage in chosen or (not second_pass and passage.title in titles):
                continue
            chosen.append(passage)
            titles.add(passage.title)
            if len(chosen) >= k:
                return chosen
    return chosen


def format_anchors(passages: Sequence[Passage]) -> str:
    return "\n".join(f'<author_paragraph role="{p.role}">\n{p.text}\n</author_paragraph>' for p in passages)


def section_anchors(hook: str, sections: Sequence[tuple[str, str]], closing: str, passages: Sequence[Passage], *, per_part: int = 2) -> str:
    """Real paragraphs to write each part of the plan next to: openers for the hook, the closest body paragraphs for
    each section, closers for the ending. Empty when the author has no posts of their own."""
    if not passages:
        return ""
    used: set[str] = set()
    blocks: list[str] = []

    def add(label: str, query: str, roles: Sequence[str]) -> None:
        found = anchor_passages(query, passages, roles, k=per_part, exclude=used)
        used.update(p.text for p in found)
        if found:
            blocks.append(f'<part name="{label}">\n{format_anchors(found)}\n</part>')

    add("opening", hook, ("opener",))
    for heading, points in sections:
        add(f"section: {heading}", f"{heading}\n{points}", ("story", "explain", "opinion", "list_intro"))
    add("closing", closing, ("closer",))
    return "\n\n".join(blocks)
