"""Project dials: everything is optional and resolves to a smart default."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from proseferno.db import Persona

Education = Literal["beginner", "intermediate", "expert"]
Platform = Literal["medium", "substack", "gumroad", "markdown"]

TOPICS: dict[str, list[str]] = {
    "Data Science": ["data science", "data scientist", "analysis", "dataset", "statistics", "eda", "sql"],
    "Python Programming": ["python", "pandas", "numpy", "polars", "uv", "pip", "decorator", "asyncio", "notebook", "jupyter"],
    "Data Visualization": [
        "visualization",
        "visualisation",
        "chart",
        "plot",
        "tableau",
        "dashboard",
        "matplotlib",
        "viz",
        "pie",
        "map",
        "color",
    ],
    "Machine Learning": [
        "machine learning",
        "model",
        "training",
        "classifier",
        "regression",
        "xgboost",
        "neural",
        "feature engineering",
        "ml",
    ],
    "Causality, Experimentation & Causal Inference": [
        "causal",
        "experiment",
        "a/b",
        "ab test",
        "uplift",
        "counterfactual",
        "treatment effect",
        "randomized",
        "diff-in-diff",
        "synthetic control",
    ],
    "Leading Analytics & Data Science Teams": [
        "team",
        "leader",
        "leadership",
        "manager",
        "hiring",
        "stakeholder",
        "career",
        "mentor",
        "org",
    ],
    "Advanced Analytics at Large Companies": ["enterprise", "at scale", "large company", "fortune", "governance", "operating model"],
    "AI, LLMs & Agents": ["llm", "agent", "agents", "gpt", "claude", "prompt", "rag", "embedding", "genai", "generative ai", "ai"],
    "AI/ML Platforms (AWS, Snowflake)": ["aws", "sagemaker", "snowflake", "cortex", "bedrock", "databricks", "cloud", "platform"],
    "Building with Agentic Coding Tools": [
        "claude code",
        "cursor",
        "antigravity",
        "anti-gravity",
        "copilot",
        "agentic coding",
        "vibe coding",
        "coding agent",
    ],
}

HUMOR_GUIDE = {
    range(0, 3): "Serious and precise; at most one light touch in the whole post.",
    range(3, 6): "Mostly substantive with a few well-placed jokes or wry asides.",
    range(6, 9): "Playful throughout: frequent asides, witty headings, a running gag if it fits.",
    range(9, 11): "Maximum fun while still teaching: jokes in most sections, absurd examples, memorable callbacks.",
}

EDUCATION_GUIDE = {
    "beginner": "Assume no prior knowledge: define every term, use analogies, build up step by step, keep math optional.",
    "intermediate": "Assume working familiarity: define niche terms briefly, focus on practical how and why, include one deeper dive.",
    "expert": "Assume deep expertise: skip basics, go into trade-offs, edge cases, math or implementation details, and cite sources.",
}


class Dials(BaseModel):
    """What the user can set. Every field is optional."""

    target_words: int = Field(1500, ge=300, le=6000)
    image_count: int | None = Field(None, ge=2, le=15)
    humor: int | None = Field(None, ge=0, le=10)
    education: Education | None = None
    topic: str | None = None
    platform: Platform = "medium"
    include_code: Literal["auto", "yes", "no"] = "auto"
    revision_passes: int | None = Field(None, ge=0, le=2)


class ResolvedDials(BaseModel):
    target_words: int
    image_count: int
    humor: int
    humor_guide: str
    education: Education
    education_guide: str
    topic: str
    platform: Platform
    include_code: Literal["auto", "yes", "no"]
    revision_passes: int


def classify_topic(text: str) -> str:
    lowered = f" {text.lower()} "
    scores = {
        topic: sum(len(re.findall(rf"(?<![a-z]){re.escape(word)}(?![a-z])", lowered)) * (2 if " " in word else 1) for word in words)
        for topic, words in TOPICS.items()
    }
    best = max(scores, key=lambda t: scores[t])
    return best if scores[best] > 0 else "Data Science"


def auto_image_count(target_words: int) -> int:
    return max(2, min(12, round(target_words / 350)))


def resolve(dials: Dials, persona: Persona, prompt: str, *, default_revisions: int) -> ResolvedDials:
    humor = dials.humor if dials.humor is not None else persona.default_humor
    education: Education = dials.education or persona.default_education  # type: ignore[assignment]
    if education not in EDUCATION_GUIDE:
        education = "intermediate"
    return ResolvedDials(
        target_words=dials.target_words,
        image_count=dials.image_count or auto_image_count(dials.target_words),
        humor=humor,
        humor_guide=next(text for span, text in HUMOR_GUIDE.items() if humor in span),
        education=education,
        education_guide=EDUCATION_GUIDE[education],
        topic=dials.topic or classify_topic(prompt),
        platform=dials.platform,
        include_code=dials.include_code,
        revision_passes=dials.revision_passes if dials.revision_passes is not None else default_revisions,
    )
