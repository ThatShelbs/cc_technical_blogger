"""Where an idea is in its life, from a brainstorm card to a published post and how it did.

Only ``Idea.state`` (new | saved | dismissed | used) is stored. Once an idea becomes a post, its stage is read from
that post (``Project.stage`` and ``Project.outcome``), so marking a post ready, published or a hit moves the idea
along with no extra bookkeeping.
"""

from __future__ import annotations

from proseferno.db import Idea, Project

# In lifecycle order. ``dismissed`` sits outside the line.
STAGES: dict[str, str] = {
    "prospective": "Prospective",
    "serious": "Serious",
    "generated": "Generated",
    "ready": "Ready",
    "published": "Published",
    # The same words as a post's outcome (frontend lib/stages.ts).
    "too_early": "Too early",
    "small_hit": "Small hit",
    "medium_hit": "Medium hit",
    "big_hit": "Big hit",
    "dismissed": "Dismissed",
}

OUTCOME_STAGES: dict[str, str] = {"too_early": "too_early", "small": "small_hit", "good": "medium_hit", "viral": "big_hit"}

# Ideas the author has kept: everything in the bank.
BANK_STATES = ("saved", "used")


def stage_of(idea: Idea, project: Project | None) -> str:
    if idea.state == "dismissed":
        return "dismissed"
    if idea.state == "new":
        return "prospective"
    if idea.state == "saved" or project is None:
        return "serious"
    if project.outcome in OUTCOME_STAGES:
        return OUTCOME_STAGES[project.outcome]
    if project.stage == "published":
        return "published"
    if project.stage == "ready":
        return "ready"
    return "generated"


def stage_label(stage: str) -> str:
    return STAGES.get(stage, stage)
