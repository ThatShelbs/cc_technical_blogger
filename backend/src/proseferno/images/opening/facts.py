"""The fact check for data openers: every number the image prints must come from the research or the post.

A number counts as verified when it appears in the research text, a citation's quoted text or the post itself
(allowing for rounding and forms like 1,234 / 1.2k / 12% / $3.4M), or is the difference or sum of two such numbers
(a waterfall's steps, a "+22 points" change). Every source URL must be one the research actually cited. This cannot
judge whether a number means what the image says (the panel and the render review look at that); it guarantees no
figure is invented.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from itertools import combinations

from proseferno.images.opening.specs import OpeningBuild
from proseferno.llm.base import Citation

_NUMBER_RE = re.compile(
    r"(?<![\w.])[-−]?[$€£]?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(k|m|bn|b|thousand|million|billion|trillion|%|x)?(?![\w])",
    re.IGNORECASE,
)
_SCALE = {
    "k": 1e3,
    "thousand": 1e3,
    "m": 1e6,
    "million": 1e6,
    "b": 1e9,
    "bn": 1e9,
    "billion": 1e9,
    "trillion": 1e12,
}
# At most this many known numbers are paired up for sums and differences (pairs grow with the square).
_PAIR_LIMIT = 150


def numbers_in(text: str) -> set[float]:
    """Every number written in ``text``, both as written and with its scale word applied (1.2k -> 1.2 and 1200)."""
    found: set[float] = set()
    for match in _NUMBER_RE.finditer(text or ""):
        value = float(match.group(1).replace(",", ""))
        found.add(value)
        scale = (match.group(2) or "").lower()
        if scale in _SCALE:
            found.add(value * _SCALE[scale])
    return found


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= max(0.051, abs(b) * 0.01)


def is_known(value: float, known: set[float], pairs: Iterable[float] = ()) -> bool:
    target = abs(value)
    return any(_close(target, k) for k in known) or any(_close(target, p) for p in pairs)


def derived(known: set[float]) -> set[float]:
    """Differences and sums of pairs of known numbers."""
    values = sorted(known)[:_PAIR_LIMIT]
    out: set[float] = set()
    for a, b in combinations(values, 2):
        out.add(abs(a - b))
        out.add(a + b)
    return out


def printed_numbers(build: OpeningBuild) -> list[tuple[str, float]]:
    """(where, value) for every figure the image shows: data values, the big number and digits in its words."""
    out: list[tuple[str, float]] = [(f"data `{d.label}`{f' ({d.series})' if d.series else ''}", d.value) for d in build.data]
    texts = {"number": build.number, "headline": build.headline, "subhead": build.subhead, "annotation": build.annotation}
    texts.update({f"items[{i}]": f"{item.label} {item.detail}" for i, item in enumerate(build.items)})
    for where, text in texts.items():
        # Years are dates, not claims (a chart's x labels are not checked either).
        for value in numbers_in(text):
            if not (1900 <= value <= 2100 and value == int(value)):
                out.append((where, value))
    return out


def check(
    build: OpeningBuild, *, research: str, citations: list[Citation], post: str, steps: bool = False, percent: bool = False
) -> list[str]:
    """Problems that block publishing: invented numbers and sources the research never cited.

    ``steps`` lets data values be the difference of two known numbers (a waterfall's changes); words never get that
    allowance, so a claim in the headline must be written as it was found."""
    known = numbers_in(research) | numbers_in(post) | {n for c in citations for n in numbers_in(c.cited_text)}
    if percent:
        known.add(100.0)
    pairs = derived(known) if steps else set()
    problems = []
    seen: set[tuple[str, float]] = set()
    for where, value in printed_numbers(build):
        if (where, value) in seen:
            continue
        seen.add((where, value))
        if not is_known(value, known, pairs if where.startswith("data") else ()):
            problems.append(f"{where}: {value:g} is not in the research or the post. Use only numbers you were given.")
    cited = {c.url.rstrip("/") for c in citations}
    for source in build.sources:
        url = source.url.strip().rstrip("/")
        if url and url not in cited:
            problems.append(f"Source `{source.title}` has a URL the research did not cite ({source.url}). Use a cited URL or ''.")
    if not build.sources:
        problems.append("`sources` is empty: name where the numbers come from.")
    return problems
