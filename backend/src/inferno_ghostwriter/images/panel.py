"""The judging panel for opening images and closing memes: many small, independent judges, run at once.

Each ``Seat`` is one judge with one question, on its own model and effort (Haiku, Sonnet or Opus; low to high), so the
panel is wider than one call role-playing four judges, yet faster: every seat runs in parallel and most are small.
Code adds up the votes (a weighted mean, with vetoes), so no judge grades its own pitch and no single judge decides.

Two panels use it: the **pitch panel** scores the pitched ideas as text, and the **render panel** looks at the drawn
pictures (a blind reader who sees only the image says what it means, and that reading is matched against what the
pitch meant it to say). A final pick on Opus then chooses between the top renders and may ask for one fix.

A seat that fails is dropped; the panel stands while at least half of its seats answered. Seats live in Settings
(``image_panel_pitch`` / ``image_panel_render``) as ``role:model:effort`` strings, so they can be tuned.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from inferno_ghostwriter.llm import LLM, LLMError, SystemBlock
from inferno_ghostwriter.llm.base import LLMImagesUnsupportedError, UsageSink
from inferno_ghostwriter.prompts import raw, render

log = logging.getLogger(__name__)

MODELS = {"opus": "claude-opus-5-5", "sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-5-5"}

# role: (weight, veto below, sees the pictures)
ROLES: dict[str, tuple[float, int, bool]] = {
    "scroller": (1.5, 0, False),
    "gets_it": (1.0, 5, False),
    "comedy_editor": (1.25, 0, False),
    "format_fan": (1.0, 0, False),
    "art_director": (1.25, 0, False),
    "fact_checker": (1.0, 5, False),
    "author": (1.25, 4, False),
    "blind_reader": (1.5, 0, True),
    "craft": (1.25, 4, True),
    "appeal": (1.25, 0, True),
}

DEFAULT_MEME_PITCH = (
    "scroller:haiku:low",
    "scroller:sonnet:low",
    "gets_it:haiku:low",
    "comedy_editor:sonnet:medium",
    "format_fan:sonnet:low",
    "author:opus:medium",
)
DEFAULT_OPENING_PITCH = (
    "scroller:haiku:low",
    "scroller:sonnet:low",
    "gets_it:haiku:low",
    "art_director:sonnet:medium",
    "fact_checker:sonnet:medium",
    "author:opus:medium",
)
DEFAULT_RENDER = ("blind_reader:haiku:low", "blind_reader:sonnet:low", "craft:sonnet:medium", "appeal:sonnet:low")
FINAL_PICK = "opus:medium"


@dataclass(frozen=True)
class Seat:
    role: str
    model: str  # an alias (opus, sonnet, haiku) or a model id
    effort: str

    @property
    def model_id(self) -> str:
        return MODELS.get(self.model, self.model)

    @property
    def weight(self) -> float:
        return ROLES.get(self.role, (1.0, 0, False))[0]

    @property
    def veto(self) -> int:
        return ROLES.get(self.role, (1.0, 0, False))[1]

    @property
    def sees(self) -> bool:
        return ROLES.get(self.role, (1.0, 0, False))[2]

    @property
    def label(self) -> str:
        return f"{self.role} ({self.model}, {self.effort})"


def parse_seats(specs: Sequence[str]) -> list[Seat]:
    """``role:model:effort`` strings to seats; unknown roles or efforts are skipped."""
    seats = []
    for spec in specs:
        parts = [p.strip() for p in str(spec).split(":")]
        if len(parts) != 3 or parts[0] not in ROLES or parts[2] not in ("low", "medium", "high", "xhigh", "max"):
            log.warning("Ignoring panel seat %r (want role:model:effort)", spec)
            continue
        seats.append(Seat(*parts))
    return seats


class SlotWords(BaseModel):
    slot: str
    text: str


class CandidateScore(BaseModel):
    candidate: int = Field(description="Index of the candidate, from 0.")
    score: int = Field(description="1-10 from your seat's question alone. Most are 4-6; 9+ is rare.")
    note: str = Field(description="One line: the strongest point and the biggest risk.")
    reading: str = Field("", description="Blind reader only: in one sentence, what the picture says to you. '' otherwise.")


class SeatVerdict(BaseModel):
    scores: list[CandidateScore] = Field(description="One entry per candidate, in order.")
    punch_up: list[SlotWords] = Field(
        default_factory=list,
        description="Comedy editor only: sharper final words for the candidate you rate highest (every slot). Empty otherwise.",
    )
    punch_for: int = Field(-1, description="Comedy editor only: the candidate the punch-up is for; -1 if none.")


class MatchScores(BaseModel):
    scores: list[CandidateScore] = Field(description="One entry per candidate: how well the reading matches the intent, 1-10.")


class FinalPick(BaseModel):
    chosen: int = Field(description="Index of the picture to publish.")
    fix: str = Field("", description="Only if one concrete change would clearly lift the chosen picture: the instruction. Else ''.")
    why: str = Field(description="One sentence on why it wins, naming it by its idea.")


@dataclass
class PanelResult:
    totals: list[float]  # weighted mean per candidate, 1-10; a vetoed candidate is pushed below 0
    notes: list[list[str]]
    raw: list[float] = field(default_factory=list)  # the same means before any veto, for display
    seats: dict[str, list[int]] = field(default_factory=dict)
    vetoed: set[int] = field(default_factory=set)
    readings: list[list[str]] = field(default_factory=list)
    match: list[int] = field(default_factory=list)
    punch_up: list[SlotWords] = field(default_factory=list)
    punch_for: int = -1
    asked: int = 0
    answered: int = 0
    seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return self.answered > 0 and self.answered * 2 >= self.asked

    def best(self, among: Sequence[int] | None = None) -> int | None:
        pool = list(among) if among is not None else list(range(len(self.totals)))
        pool = [i for i in pool if 0 <= i < len(self.totals)]
        return max(pool, key=lambda i: self.totals[i], default=None)

    def ranking(self) -> list[int]:
        return sorted(range(len(self.totals)), key=lambda i: self.totals[i], reverse=True)

    def summary(self) -> dict[str, object]:
        """What is stored on the image (and shown as 'Why this one')."""
        return {
            "scores": [round(t * 4) for t in self.totals],  # on the old 4-judge scale (4-40) so older readers still rank
            "totals": [round(t, 2) for t in (self.raw or self.totals)],
            "notes": [" | ".join(n[:3]) for n in self.notes],
            "seats": self.seats,
            "vetoed": sorted(self.vetoed),
            "readings": [r[:2] for r in self.readings],
            "match": self.match,
            "answered": f"{self.answered}/{self.asked}",
            "seconds": round(self.seconds, 1),
        }


SYSTEM = [SystemBlock(raw("panel_system"), cache=True)]


async def _seat(
    llm: LLM, seat: Seat, prompt: str, images: list[bytes] | None, usage: UsageSink | None, count: int
) -> tuple[Seat, SeatVerdict | None]:
    try:
        verdict = await llm.structured(
            task=f"panel {seat.role}",
            system=SYSTEM,
            prompt=prompt,
            schema=SeatVerdict,
            effort=seat.effort,
            max_tokens=12000 if not seat.sees else 8000,
            usage=usage,
            images=images if seat.sees else None,
            model=seat.model_id,
        )
    except LLMImagesUnsupportedError:
        return seat, None
    except LLMError as exc:
        log.info("Panel seat %s failed: %s", seat.label, exc)
        return seat, None
    by = {s.candidate: s for s in verdict.scores if 0 <= s.candidate < count}
    if len(by) != count:
        log.info("Panel seat %s scored %d of %d candidates; dropped", seat.label, len(by), count)
        return seat, None
    return seat, verdict


async def convene(
    llm: LLM,
    seats: Sequence[Seat],
    *,
    context: str,
    candidates: Sequence[str],
    images: list[bytes] | None = None,
    intents: Sequence[str] | None = None,
    usage: UsageSink | None = None,
    match_seat: Seat | None = None,
) -> PanelResult:
    """Ask every seat at once and add up their votes.

    ``images`` (one PNG per candidate, in order) are shown only to seats that look at pictures, and those seats are
    skipped when there are none or the connection cannot send them. ``intents`` (what each candidate was meant to say)
    are matched against the blind readings by ``match_seat`` (a Sonnet call by default)."""
    started = time.monotonic()
    count = len(candidates)
    usable = [s for s in seats if not s.sees or images]
    listed = "\n".join(f"{i}. {c}" for i, c in enumerate(candidates))

    def prompt_for(seat: Seat) -> str:
        shown = (
            f"The {count} pictures are attached in order (picture 1 is candidate 0)."
            if seat.sees
            else "You judge the pitches as written; nothing is drawn yet."
        )
        return render(
            "panel_seat",
            role=raw(f"panel_{seat.role}"),
            context=context if seat.role != "blind_reader" else "(You get no context: judge the pictures as a stranger in a feed would.)",
            candidates=listed if seat.role != "blind_reader" else "\n".join(f"{i}. (picture {i + 1})" for i in range(count)),
            shown=shown,
            count=count,
        )

    results = await asyncio.gather(*(_seat(llm, s, prompt_for(s), images, usage, count) for s in usable))
    answered = [(s, v) for s, v in results if v is not None]
    totals_w = [0.0] * count
    weights = [0.0] * count
    notes: list[list[str]] = [[] for _ in range(count)]
    readings: list[list[str]] = [[] for _ in range(count)]
    per_seat: dict[str, list[int]] = {}
    vetoed: set[int] = set()
    punch: list[SlotWords] = []
    punch_for = -1
    for seat, verdict in answered:
        by = {s.candidate: s for s in verdict.scores}
        label = seat.label
        n = 2
        while label in per_seat:  # the same seat listed twice keeps both scores
            label, n = f"{seat.label} #{n}", n + 1
        per_seat[label] = [max(1, min(10, by[i].score)) for i in range(count)]
        for i in range(count):
            score = max(1, min(10, by[i].score))
            totals_w[i] += score * seat.weight
            weights[i] += seat.weight
            if by[i].note:
                notes[i].append(f"{seat.role}: {by[i].note.strip()}")
            if by[i].reading:
                readings[i].append(by[i].reading.strip())
            if seat.veto and score < seat.veto:
                vetoed.add(i)
        if seat.role == "comedy_editor" and verdict.punch_up and 0 <= verdict.punch_for < count:
            punch, punch_for = verdict.punch_up, verdict.punch_for

    match: list[int] = []
    if intents and any(readings) and len(intents) == count:
        match = await _match(llm, match_seat or Seat("blind_reader", "sonnet", "low"), intents, readings, usage)
        for i, m in enumerate(match):
            # The blind read is the strongest signal that a picture makes sense to a stranger.
            totals_w[i] += m * 2.0
            weights[i] += 2.0
            if m < 4:
                vetoed.add(i)
                notes[i].append(f"blind read missed the idea ({m}/10)")

    means = [(totals_w[i] / weights[i]) if weights[i] else 5.0 for i in range(count)]
    totals = [t - 100 if i in vetoed else t for i, t in enumerate(means)]
    result = PanelResult(
        totals=totals,
        raw=means,
        notes=notes,
        seats=per_seat,
        vetoed=vetoed,
        readings=readings,
        match=match,
        punch_up=punch,
        punch_for=punch_for,
        asked=len(usable),
        answered=len(answered),
        seconds=time.monotonic() - started,
    )
    log.info("Panel: %d/%d seats in %.1fs, totals %s", result.answered, result.asked, result.seconds, [round(t, 1) for t in totals])
    return result


async def _match(llm: LLM, seat: Seat, intents: Sequence[str], readings: list[list[str]], usage: UsageSink | None) -> list[int]:
    pairs = "\n".join(
        f"{i}. Meant to say: {intent}\n   Strangers read it as: {' / '.join(readings[i]) or '(no reading)'}"
        for i, intent in enumerate(intents)
    )
    try:
        scores = await llm.structured(
            task="panel match",
            system=SYSTEM,
            prompt=render("panel_match", pairs=pairs),
            schema=MatchScores,
            effort=seat.effort,
            max_tokens=2000,
            usage=usage,
            model=seat.model_id,
        )
    except LLMError as exc:
        log.info("Panel match failed: %s", exc)
        return []
    by = {s.candidate: max(1, min(10, s.score)) for s in scores.scores}
    return [by.get(i, 5) for i in range(len(intents))]


async def final_pick(
    llm: LLM,
    *,
    context: str,
    candidates: Sequence[str],
    images: list[bytes],
    panel: PanelResult | None,
    spec: str = FINAL_PICK,
    usage: UsageSink | None = None,
) -> FinalPick | None:
    """Opus looks at the finished candidates (as feed cards) with the panel's notes and picks one; None on failure or
    when images cannot be sent (the panel's ranking then decides)."""
    model, _, effort = spec.partition(":")
    notes = ""
    if panel is not None:
        notes = "\n".join(
            f"{i}. panel {(panel.raw or panel.totals)[i]:.1f}/10{' (ruled out)' if i in panel.vetoed else ''}: "
            + " | ".join(panel.notes[i][:4])
            for i in range(len(candidates))
        )
    try:
        pick = await llm.structured(
            task="panel final pick",
            system=SYSTEM,
            prompt=render(
                "panel_final",
                context=context,
                candidates="\n".join(f"{i}. {c}" for i, c in enumerate(candidates)),
                notes=notes or "(no panel notes)",
                count=len(candidates),
            ),
            schema=FinalPick,
            effort=effort or "medium",
            max_tokens=3000,
            usage=usage,
            images=images,
            model=MODELS.get(model, model) if model else None,
        )
    except LLMImagesUnsupportedError:
        return None
    except LLMError as exc:
        log.info("Final pick failed: %s", exc)
        return None
    if not 0 <= pick.chosen < len(candidates):
        return None
    return pick
