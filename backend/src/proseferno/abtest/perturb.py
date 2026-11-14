"""Build the challenger of an A/B test: the control's settings, each nudged at random.

Pure and seeded (no model call), so a test can be replayed and unit-tested. Every change is recorded as a
*tweak* the author can later adopt into the persona, one by one:

- ``persona`` tweaks set a persona default (a dial, a formula part, the visual style);
- ``sample`` tweaks raise the weight of one of the author's own posts as a writing example;
- ``profile`` tweaks are sentences worked into a new voice profile version (see ``evolution.service``).

The post's length, platform, topic, audience and article type never change: the two posts answer the same brief.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Any

from proseferno.db import Persona, Sample, VoiceProfile
from proseferno.images.memes.generate import voice_section
from proseferno.images.service import DEFAULT_VISUAL_STYLE
from proseferno.voice.exemplars import rank_own, select_exemplars
from proseferno.writer.dials import STYLE_DIALS, Dials, ResolvedDials
from proseferno.writer.formulas import part_label, shuffle_part

EDUCATION_ORDER = ("beginner", "intermediate", "expert")
# How much an adopted example tweak favors a post when examples are chosen (see voice.exemplars).
LEAN_WEIGHT = 1.5
SWAP_WEIGHT = 1.25

# Best practices of technical writing the challenger can weigh heavier (research adds the author's own list).
PRINCIPLES: dict[str, str] = {
    "Titles": "Make the title and subtitle a specific, honest promise the post then keeps.",
    "Story": "Carry the ideas in a story with stakes: a setup, a complication and a payoff.",
    "Skim readers": "Serve the skim reader: headings that say something, short paragraphs, the takeaway easy to find.",
    "Humor": "Let the humor do work: jokes that make the point more memorable, never decoration.",
    "Insight": "Give the reader one insight they have not read elsewhere, earned from real experience.",
    "Credibility": "Build trust: show the work, give real numbers and admit what did not work.",
    "Teaching": "Teach by writing: one concrete worked example before any abstraction.",
}

TITLE_ANGLES: dict[str, str] = {
    "A question": "a title that asks the question the reader already has",
    "A number": "a title built on a specific number or count",
    "A bold claim": "a title that states a strong, defensible claim",
    "A how-to": "a title that promises a concrete skill or result",
    "A story hook": "a title that opens a story the reader wants finished",
    "A contrast": "a title that sets two things against each other",
}

IMAGE_STYLES: tuple[str, ...] = (
    "hand-drawn ink sketch lines with loose marker color",
    "bold geometric shapes with thick outlines",
    "isometric 3D scenes with soft shadows",
    "blueprint-style line art on a dark ground",
    "paper cut-out collage with layered textures",
    "minimal single-line drawings with one accent color",
)

_VOICE_SECTIONS = ("Signature Moves", "Voice & Tone", "Humor", "Teaching Style", "Structure")
_BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*\S)\s*$")


@dataclass
class Challenger:
    dials: Dials
    brand_kit: dict[str, Any]
    exemplar_ids: list[int]
    emphasis: str
    tweaks: list[dict[str, Any]] = field(default_factory=list)


def bullets(markdown: str, limit: int = 180) -> list[str]:
    """The bullet points of a Markdown block as plain one-line sentences (links and emphasis stripped)."""
    out: list[str] = []
    for line in markdown.splitlines():
        match = _BULLET_RE.match(line)
        if not match:
            continue
        text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", match.group(1))
        text = re.sub(r"[*_`]+", "", text).strip()
        # A habit's name and rule, without the verbatim example that usually follows.
        text = re.split(r"\s+(?:Example|e\.g\.|E\.g\.)[:\s]", text)[0].strip(" :;-")
        if len(text) > limit:
            text = text[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "..."
        if len(text.split()) >= 3 and text not in out:
            out.append(text)
    return out


def voice_habits(voice_profile: str) -> list[str]:
    """Habits the profile lists, from the sections that describe how the author writes."""
    found: list[str] = []
    for heading in _VOICE_SECTIONS:
        for habit in bullets(voice_section(voice_profile, re.escape(heading))):
            if habit not in found:
                found.append(habit)
    return found


def research_principles(best_practices: str | None) -> list[str]:
    """Bullets from the persona's best-practice research (its source list left out)."""
    body = re.split(r"^##\s+Sources\b", best_practices or "", flags=re.MULTILINE)[0]
    return bullets(body)


def _move(rng: random.Random, value: int, low: int = 0, high: int = 10, steps: tuple[int, ...] = (1, 2)) -> int:
    """A step or two up or down, turned around at the ends of the scale so the value always changes."""
    delta = rng.choice(steps) * rng.choice((-1, 1))
    moved = max(low, min(high, value + delta))
    if moved == value:
        moved = max(low, min(high, value - delta))
    return moved


def _tweak(tweaks: list[dict[str, Any]], group: str, label: str, before: Any, after: Any, target: str, **extra: Any) -> None:
    tweaks.append(
        {"id": f"t{len(tweaks) + 1}", "group": group, "label": label, "before": str(before), "after": str(after), "target": target, **extra}
    )


def build_challenger(
    *,
    seed: int,
    control: ResolvedDials,
    dials: Dials,
    persona: Persona,
    voice_profile: VoiceProfile,
    samples: list[Sample],
    prompt: str,
    brand_kit: dict[str, Any] | None = None,
) -> Challenger:
    """``control`` is the post's resolved settings as they are; ``dials`` the raw ones the challenger's are built on."""
    rng = random.Random(seed)
    tweaks: list[dict[str, Any]] = []
    changed: dict[str, Any] = {}

    # 1. Dials: every 0-10 dial moves a step or two.
    for key, label in (("humor", "Humor"), *((k, v[0]) for k, v in STYLE_DIALS.items())):
        before = getattr(control, key)
        changed[key] = _move(rng, before)
        _tweak(tweaks, "Settings", label, f"{before}/10", f"{changed[key]}/10", "persona", field=f"default_{key}", value=changed[key])
    if rng.random() < 1 / 3:
        index = EDUCATION_ORDER.index(control.education)
        after = EDUCATION_ORDER[1 if index != 1 else rng.choice((0, 2))]
        changed["education"] = after
        _tweak(tweaks, "Settings", "Education level", control.education, after, "persona", field="default_education", value=after)
    images = _move(rng, control.image_count, 2, 12, steps=(1,))
    changed["image_count"] = images
    _tweak(tweaks, "Settings", "Images", control.image_count, images, "persona", field="default_image_count", value=images)
    if control.reference_count > 0:
        references = _move(rng, control.reference_count, 1, 12)
        changed["reference_count"] = references
        _tweak(
            tweaks,
            "Settings",
            "References",
            control.reference_count,
            references,
            "persona",
            field="default_reference_count",
            value=references,
        )

    # 2. Formula: two of the three parts get another style that suits the article type.
    parts = ["opener", "body", "closer"]
    rng.shuffle(parts)
    swapped = 0
    for part in parts:
        if swapped == 2:
            break
        current = getattr(control, part)
        fresh = shuffle_part(part, current, control.article_type, humor=changed["humor"], rng=rng)
        if fresh is None or fresh == current:
            continue
        changed[part] = fresh
        swapped += 1
        _tweak(tweaks, "Formula", part.capitalize(), part_label(part, current), part_label(part, fresh), "persona", field=part, value=fresh)

    notes: list[str] = []

    # 3. Examples: another mix of the author's own posts, and one to lean on.
    exemplar_ids = _exemplars(rng, prompt, samples, tweaks, notes)

    # 4. Voice: habits from the profile to lean into and one to ease off.
    habits = voice_habits(voice_profile.markdown)
    rng.shuffle(habits)
    for habit in habits[:2]:
        notes.append(f"Lean harder than usual on this habit of the author: {habit}")
        _tweak(
            tweaks,
            "Voice",
            "Lean into",
            "As usual",
            habit,
            "profile",
            change=f"Lean harder on this habit; it is one of the author's strongest: {habit}",
        )
    for habit in habits[2:3]:
        notes.append(f"Use this habit more sparingly than usual: {habit}")
        _tweak(
            tweaks,
            "Voice",
            "Ease off",
            "As usual",
            habit,
            "profile",
            change=f"Use this habit more sparingly than the samples suggest: {habit}",
        )

    # 5. Principles: a few best practices weighed heavier (the persona's research first, then the built-in list).
    researched = research_principles(voice_profile.best_practices)
    rng.shuffle(researched)
    chosen = [("From your research", text) for text in researched[:2]]
    builtin = list(PRINCIPLES.items())
    rng.shuffle(builtin)
    chosen += builtin[: 3 - len(chosen)]
    for name, text in chosen:
        notes.append(f"Weigh this writing principle more heavily than usual: {text}")
        _tweak(
            tweaks, "Principles", name, "Normal weight", text, "profile", change=f"Give this principle extra weight in every post: {text}"
        )

    # 6. Title: one angle to favor.
    angle, angle_text = rng.choice(list(TITLE_ANGLES.items()))
    notes.append(f"For the title and the title options, favor {angle_text} (still in the author's title style).")
    _tweak(tweaks, "Title", "Title angle", "The author's usual", angle, "profile", change=f"Titles: favor {angle_text}.")

    # 7. Images: the same look with one style twist; palette, font and motif stay.
    kit = dict(brand_kit or {})
    base = str(kit.get("style") or "").strip() or persona.visual_style or DEFAULT_VISUAL_STYLE
    style = f"{base.rstrip('. ')}, {rng.choice(IMAGE_STYLES)}"[:300]
    kit["style"] = style
    _tweak(tweaks, "Images", "Image style", base, style, "persona", field="visual_style", value=style)

    emphasis = (
        "# Emphasis for this post\n\n"
        "Same author, same voice profile. For this post only, shift the emphasis as follows; "
        "where a point conflicts with the voice profile's hard rules, the profile wins.\n\n" + "\n".join(f"- {n}" for n in notes)
    )
    return Challenger(dials=dials.model_copy(update=changed), brand_kit=kit, exemplar_ids=exemplar_ids, emphasis=emphasis, tweaks=tweaks)


def _exemplars(rng: random.Random, prompt: str, samples: list[Sample], tweaks: list[dict[str, Any]], notes: list[str]) -> list[int]:
    usual = select_exemplars(prompt, samples)
    if not usual:
        return []
    chosen = list(usual)
    others = [s for s in rank_own(prompt, samples) if s not in usual][:4]
    if others:
        out, into = rng.choice(chosen), rng.choice(others)
        chosen[chosen.index(out)] = into
        _tweak(
            tweaks,
            "Examples",
            "Example post shown to the writer",
            out.title or out.source_name,
            into.title or into.source_name,
            "sample",
            field="weight",
            sample_id=into.id,
            value=SWAP_WEIGHT,
        )
    lean = rng.choice(chosen)
    name = lean.title or lean.source_name
    notes.append(f'Of the example posts, lean most on "{name}" for rhythm, structure and tone.')
    _tweak(tweaks, "Examples", "Lean most on", "All examples equally", name, "sample", field="weight", sample_id=lean.id, value=LEAN_WEIGHT)
    return [s.id for s in chosen if s.id is not None]
