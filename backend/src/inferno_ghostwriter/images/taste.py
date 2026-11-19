"""The author's image taste, learned from their thumbs up and down on opening images and closing memes.

A rating is stored on the image (``ProjectImage.rating``: 1 liked, -1 passed, 0 none). ``taste_of`` reads a persona's
rated images and counts what they liked and passed on (meme formats, looks, opening styles, casts, color ramps). The
meme room gets a note and look weights; the opening room gets a note. No model call: it is counting.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Taste:
    liked: Counter[str] = field(default_factory=Counter)
    passed: Counter[str] = field(default_factory=Counter)

    @property
    def empty(self) -> bool:
        return not self.liked and not self.passed

    def look_weights(self) -> dict[str, float]:
        """Look id -> multiplier for the random look pick (liked looks come up more, passed ones less)."""
        looks = {k.split(":", 1)[1] for k in (*self.liked, *self.passed) if k.startswith("look:")}
        return {look: max(0.15, min(3.0, 1.0 + 0.5 * self.liked[f"look:{look}"] - 0.6 * self.passed[f"look:{look}"])) for look in looks}

    def note(self, prefixes: tuple[str, ...]) -> str:
        """One or two lines for a pitch prompt about the given kinds of choice (e.g. ("format", "cast"))."""

        def names(counter: Counter[str]) -> str:
            items = [(k, n) for k, n in counter.most_common() if k.split(":", 1)[0] in prefixes]
            return ", ".join(f"{k.split(':', 1)[1].replace('_', ' ')} ({k.split(':', 1)[0]})" for k, _ in items[:6])

        liked, passed = names(self.liked), names(self.passed)
        lines = []
        if liked:
            lines.append(f"The author has liked images with: {liked}. Lean toward these when they fit.")
        if passed:
            lines.append(f"The author has turned down images with: {passed}. Avoid these unless one is clearly the best fit.")
        return "\n".join(lines)


def features(kind: str, spec: str) -> list[str]:
    """What a stored image was made of, as 'dimension:value' keys."""
    try:
        state: dict[str, Any] = json.loads(spec) if spec else {}
    except json.JSONDecodeError:
        return []
    if not isinstance(state, dict):
        return []
    keys: list[str] = []
    if kind == "hero" and state.get("room") == "opening":
        if state.get("style"):
            keys.append(f"style:{state['style']}")
        if isinstance(state.get("meme"), str):
            keys += features("meme", state["meme"])
        for c in (state.get("scene") or {}).get("characters") or []:
            if isinstance(c, dict) and c.get("kind"):
                keys.append(f"cast:{c['kind']}")
    elif kind == "meme":
        if state.get("format"):
            keys.append(f"format:{state['format']}")
        if state.get("look"):
            keys.append(f"look:{state['look']}")
        for c in (state.get("build") or {}).get("cast") or []:
            if isinstance(c, dict) and c.get("kind"):
                keys.append(f"cast:{c['kind']}")
    scheme = str(state.get("scheme") or "")
    if ":" in scheme:
        keys.append(f"ramp:{scheme.split(':', 1)[0]}")
    return list(dict.fromkeys(keys))


def taste_of(rows: Iterable[tuple[str, str, int]]) -> Taste:
    """``rows`` are (kind, spec, rating) for a persona's rated images."""
    taste = Taste()
    for kind, spec, rating in rows:
        if not rating:
            continue
        target = taste.liked if rating > 0 else taste.passed
        for key in features(kind, spec):
            target[key] += 1
    return taste
