"""Voices for authors with little or no writing of their own.

A persona normally learns its voice from the author's own posts. ``Persona.source`` lets it start
from something else instead, or as well (own posts always win on identity when there are any):

- ``archetype``: one of the bundled voices (``sample_content/archetypes.json``)
- ``random``: a random archetype with a second one folded in, a quick way to get going
- ``blend``: public writers the author names, studied for style traits with a web search
- ``interview``: the author's answers to a handful of questions

Each source turns into a *persona brief*, text that goes into voice synthesis next to the analyses of any
samples. Archetype, random and interview briefs need no model call; the blend runs one research call.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from functools import cache
from importlib import resources
from typing import Any

from inferno_ghostwriter.config import Settings
from inferno_ghostwriter.db import Persona
from inferno_ghostwriter.jobs import JobContext
from inferno_ghostwriter.llm import LLM, SystemBlock
from inferno_ghostwriter.prompts import raw, render

SOURCES = ("samples", "archetype", "random", "blend", "interview")
DIAL_KEYS = ("humor", "storytelling", "opinion", "formality", "technical_depth", "skimmability")
MAX_WRITERS = 4

INTERVIEW_QUESTIONS: list[dict[str, str]] = [
    {
        "id": "audience",
        "question": "Who do you write for, and what do they want from you?",
        "hint": "e.g. data scientists a few years in, who want to ship things that matter",
    },
    {
        "id": "explain",
        "question": "Explain something you know well to a smart friend, the way you would out loud.",
        "hint": "A few sentences, exactly as you would say it. Typos welcome.",
    },
    {
        "id": "heroes",
        "question": "Which writers, blogs or newsletters do you love reading, and what do they do well?",
        "hint": "Names are optional; 'writers who are funny but never mean' counts.",
    },
    {
        "id": "annoyances",
        "question": "What bugs you in other people's technical writing?",
        "hint": "Jargon, listicles, fake enthusiasm, burying the answer...",
    },
    {
        "id": "humor",
        "question": "How funny are you in writing: never, a dry aside, or all in?",
        "hint": "Describe your sense of humor in a sentence.",
    },
    {
        "id": "stance",
        "question": "What do you believe about your field that most people disagree with?",
        "hint": "This is where your point of view lives.",
    },
    {
        "id": "never",
        "question": "Anything you never want to sound like, or never want to write about?",
        "hint": "Optional: 'a LinkedIn guru', 'a press release'.",
    },
]


class SourceError(ValueError):
    pass


@cache
def _archetypes() -> tuple[dict[str, Any], ...]:
    text = resources.files("inferno_ghostwriter.sample_content").joinpath("archetypes.json").read_text(encoding="utf-8")
    return tuple(json.loads(text))


def archetypes() -> list[dict[str, Any]]:
    return [dict(a) for a in _archetypes()]


def get_archetype(archetype_id: str) -> dict[str, Any]:
    for archetype in _archetypes():
        if archetype["id"] == archetype_id:
            return dict(archetype)
    raise SourceError(f"Unknown voice archetype: {archetype_id!r}.")


def random_spec(seed: int | None = None) -> dict[str, Any]:
    """A random primary archetype with a different one folded in, and dials nudged around the primary's."""
    rng = random.Random(seed)
    primary, secondary = rng.sample(list(_archetypes()), 2)
    dials = {k: max(0, min(10, int(primary["dials"][k]) + rng.choice((-1, 0, 0, 1)))) for k in DIAL_KEYS}
    return {"archetype": primary["id"], "secondary": secondary["id"], "dials": dials, "seed": seed}


def clean_writers(writers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Up to four distinct named writers with weights 1-10."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in writers:
        name = str(item.get("name", "")).strip()[:80]
        if not name or name.casefold() in seen:
            continue
        seen.add(name.casefold())
        weight = item.get("weight", 5)
        out.append({"name": name, "weight": max(1, min(10, int(weight if isinstance(weight, int | float) else 5)))})
    return out[:MAX_WRITERS]


def clean_spec(source: str, spec: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a source choice; raises ``SourceError`` when it is unusable."""
    if source not in SOURCES or source == "samples":
        raise SourceError(f"Unknown voice source: {source!r}.")
    note = str(spec.get("note", "")).strip()[:1000]
    if source == "archetype":
        return {"archetype": get_archetype(str(spec.get("archetype", "")))["id"], "note": note}
    if source == "random":
        primary = get_archetype(str(spec.get("archetype", "")))
        secondary = get_archetype(str(spec.get("secondary", ""))) if spec.get("secondary") else None
        dials = {k: max(0, min(10, int(spec.get("dials", {}).get(k, primary["dials"][k])))) for k in DIAL_KEYS}
        return {"archetype": primary["id"], "secondary": secondary["id"] if secondary else "", "dials": dials, "note": note}
    if source == "blend":
        writers = clean_writers(list(spec.get("writers", [])))
        if not writers:
            raise SourceError("Name at least one writer to be inspired by.")
        return {"writers": writers, "topics": str(spec.get("topics", "")).strip()[:300], "note": note}
    known = {q["id"]: q["question"] for q in INTERVIEW_QUESTIONS}
    answers = [
        {"id": a["id"], "question": known[a["id"]], "answer": str(a.get("answer", "")).strip()[:2000]}
        for a in spec.get("answers", [])
        if a.get("id") in known and str(a.get("answer", "")).strip()
    ]
    if not answers:
        raise SourceError("Answer at least one question.")
    return {"answers": answers, "note": note}


def dials_for(source: str, spec: dict[str, Any]) -> dict[str, int]:
    """The default dials a source starts the persona with (archetype and random only)."""
    if source == "random" and spec.get("dials"):
        return {k: int(v) for k, v in spec["dials"].items() if k in DIAL_KEYS}
    if source == "archetype":
        return {k: int(v) for k, v in get_archetype(spec["archetype"])["dials"].items() if k in DIAL_KEYS}
    return {}


def apply_source(persona: Persona, source: str, spec: dict[str, Any]) -> None:
    """Store a validated source on the persona and start its default dials from it."""
    persona.source = source
    persona.source_spec = spec
    for key, value in dials_for(source, spec).items():
        setattr(persona, f"default_{key}", value)


def label_for(source: str, spec: dict[str, Any]) -> str:
    if source == "archetype":
        return f"Archetype: {get_archetype(spec['archetype'])['name']}"[:80]
    if source == "random":
        return f"Surprise: {get_archetype(spec['archetype'])['name']}"[:80]
    if source == "blend":
        return ("Inspired by " + ", ".join(w["name"] for w in spec.get("writers", [])))[:80]
    return "From my interview"


def _archetype_brief(archetype: dict[str, Any]) -> str:
    return f"**{archetype['name']}**: {archetype['tagline']}\n\n{archetype['brief']}\n\nExample of the voice: {archetype['preview']}"


@dataclass
class Brief:
    text: str = ""
    # Research sources as Markdown links (blend only).
    sources: str | None = None
    # Fresh research to keep on the persona so it is not repeated (blend only).
    researched: dict[str, Any] | None = None


async def build_brief(llm: LLM, settings: Settings, persona: Persona, ctx: JobContext | None = None) -> Brief:
    """The persona brief for the persona's source (empty for ``samples``)."""
    source, spec = persona.source, persona.source_spec or {}
    if source == "samples" or not spec:
        return Brief()
    note = f"\n\nThe author adds: {spec['note']}" if spec.get("note") else ""
    if source == "archetype":
        return Brief(_archetype_brief(get_archetype(spec["archetype"])) + note)
    if source == "random":
        text = "Primary voice:\n\n" + _archetype_brief(get_archetype(spec["archetype"]))
        if spec.get("secondary"):
            text += "\n\nFold in, lightly, this second voice:\n\n" + _archetype_brief(get_archetype(spec["secondary"]))
        return Brief(text + note)
    if source == "interview":
        qa = "\n\n".join(f"**{a['question']}**\n{a['answer']}" for a in spec.get("answers", []))
        return Brief(
            "The author answered a short interview. Their own words below are the closest thing to their real voice: "
            "keep their word choices, rhythm and attitude, and infer the rest.\n\n" + qa + note
        )
    if source == "blend":
        cached = spec.get("researched")
        if cached and cached.get("text"):  # the research is kept on the persona until the writers change
            return Brief(cached["text"] + note, cached.get("sources") or None)
        writers = spec.get("writers", [])
        result = await llm.research(
            system=[SystemBlock(raw("persona_research_system"))],
            prompt=render(
                "persona_research",
                writers="\n".join(f"- {w['name']} [{w['weight']}]" for w in writers),
                topics=spec.get("topics") or "technical topics: data science, AI and machine learning",
            ),
            effort=settings.effort_research,
            max_searches=settings.research_max_searches,
            usage=ctx.add_usage if ctx else None,
        )
        text = result.text.strip()
        sources = ""
        if result.citations:
            sources = "\n".join(f"- [{c.title or c.url}]({c.url})" for c in result.citations)
        return Brief(text + note, sources or None, {"text": text, "sources": sources or None})
    raise SourceError(f"Unknown voice source: {source!r}.")
