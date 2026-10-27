"""Project dials: everything is optional and resolves to a smart default."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from proseferno.db import Persona

Education = Literal["beginner", "intermediate", "expert"]
Platform = Literal["medium", "substack", "linkedin", "gumroad", "markdown"]
IncludeCode = Literal["auto", "yes", "no"]

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


# 0-10 style dials. They are relative to the author: 4-6 means "as the author naturally writes",
# so the voice soul stays in charge unless the user deliberately pushes a dial.
STYLE_DIALS: dict[str, tuple[str, dict[range, str]]] = {
    "storytelling": (
        "Storytelling",
        {
            range(0, 2): "Straight explainer: no narrative arc, at most a one-line example of lived experience.",
            range(2, 4): "Lighter on story than the author usually is: a brief anecdote at most, then get to the point.",
            range(4, 7): "Match the author's usual balance of story and explanation.",
            range(7, 9): "More story than usual: open with a concrete personal anecdote and return to it as a thread.",
            range(9, 11): "Story-driven: a personal narrative arc (setup, tension, payoff) carries the whole post.",
        },
    ),
    "opinion": (
        "Opinion strength",
        {
            range(0, 2): "Neutral and balanced: present options and trade-offs, avoid taking sides.",
            range(2, 4): "Measured: share a view but give the other side real airtime.",
            range(4, 7): "Match how strongly the author usually states opinions.",
            range(7, 9): "Opinionated: take a clear stance early and defend it with evidence.",
            range(9, 11): "Bold hot take: a contrarian thesis stated plainly and defended confidently (still fair and accurate).",
        },
    ),
    "formality": (
        "Formality",
        {
            range(0, 2): "Very casual: chatty and loose, like talking to a friend over coffee.",
            range(2, 4): "More relaxed and conversational than the author's usual register.",
            range(4, 7): "Match the author's usual register.",
            range(7, 9): "More polished than usual: tighter sentences, fewer asides, professional tone.",
            range(9, 11): "Formal and authoritative: executive-ready, precise, minimal slang.",
        },
    ),
    "technical_depth": (
        "Technical depth",
        {
            range(0, 2): "Conceptual only: no math, minimal jargon, ideas and implications.",
            range(2, 4): "Light technical detail: name the methods, skip derivations.",
            range(4, 7): "Match the author's usual technical depth.",
            range(7, 9): "Deep: implementation details, parameters, pitfalls and a worked example.",
            range(9, 11): "Very deep: math, benchmarks, edge cases and production-grade detail.",
        },
    ),
    "skimmability": (
        "Skimmability",
        {
            range(0, 2): "Flowing essay: few headings, prose over lists.",
            range(2, 4): "Mostly prose with occasional headings and lists.",
            range(4, 7): "Match the author's usual heading, list and paragraph cadence.",
            range(7, 9): "Highly scannable: frequent descriptive headings, short paragraphs, bolded key takeaways.",
            range(9, 11): "Built for skimmers: a TL;DR up top, headings every few paragraphs, bullets, bold takeaways, a recap.",
        },
    ),
}

PLATFORM_GUIDE: dict[str, str] = {
    "medium": "Medium story: a strong title and subtitle, a hero image, two heading levels, and a satisfying close.",
    "substack": "Substack newsletter: a personal, direct-to-reader opening and a sign-off that fits a newsletter.",
    "linkedin": (
        "LinkedIn article: the first two lines must hook (they show in the feed preview); keep paragraphs to one to three "
        "sentences; use descriptive `##` headings only (LinkedIn articles have two heading levels and drop tables, so use lists "
        "instead of tables); bold one key takeaway per section; speak to practitioners and leaders; end with a question that "
        "invites comments."
    ),
    "gumroad": "Gumroad: a polished, self-contained piece that reads well as a PDF.",
    "markdown": "Developer blogs (dev.to, Hashnode, Ghost): practical, code-friendly, with clear headings.",
}


class Dials(BaseModel):
    """What the user can set. Every field is optional and falls back to the persona's defaults."""

    target_words: int | None = Field(None, ge=300, le=6000)
    image_count: int | None = Field(None, ge=2, le=15)
    humor: int | None = Field(None, ge=0, le=10)
    education: Education | None = None
    storytelling: int | None = Field(None, ge=0, le=10)
    opinion: int | None = Field(None, ge=0, le=10)
    formality: int | None = Field(None, ge=0, le=10)
    technical_depth: int | None = Field(None, ge=0, le=10)
    skimmability: int | None = Field(None, ge=0, le=10)
    topic: str | None = None
    platform: Platform | None = None
    include_code: IncludeCode | None = None
    revision_passes: int | None = Field(None, ge=0, le=2)


class ResolvedDials(BaseModel):
    target_words: int
    image_count: int
    humor: int
    humor_guide: str
    education: Education
    education_guide: str
    storytelling: int
    opinion: int
    formality: int
    technical_depth: int
    skimmability: int
    style_guide: str
    topic: str
    platform: Platform
    platform_guide: str
    include_code: IncludeCode
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


def _guide(guides: dict[range, str], value: int) -> str:
    return next(text for span, text in guides.items() if value in span)


def style_guide(values: dict[str, int]) -> str:
    """One bullet per style dial, for the plan, draft and critique prompts."""
    return "\n".join(f"- {label} {values[key]}/10: {_guide(guides, values[key])}" for key, (label, guides) in STYLE_DIALS.items())


def resolve(dials: Dials, persona: Persona, prompt: str, *, default_revisions: int) -> ResolvedDials:
    humor = dials.humor if dials.humor is not None else persona.default_humor
    education: Education = dials.education or persona.default_education  # type: ignore[assignment]
    if education not in EDUCATION_GUIDE:
        education = "intermediate"
    target_words = dials.target_words or persona.default_target_words or 1500
    platform: Platform = dials.platform or persona.default_platform  # type: ignore[assignment]
    if platform not in PLATFORM_GUIDE:
        platform = "medium"
    include_code: IncludeCode = dials.include_code or persona.default_include_code  # type: ignore[assignment]
    if include_code not in ("auto", "yes", "no"):
        include_code = "auto"
    styles: dict[str, int] = {}
    for key in STYLE_DIALS:
        value = getattr(dials, key)
        styles[key] = max(0, min(10, value if value is not None else getattr(persona, f"default_{key}", 5)))
    return ResolvedDials(
        target_words=target_words,
        image_count=dials.image_count or persona.default_image_count or auto_image_count(target_words),
        humor=humor,
        humor_guide=_guide(HUMOR_GUIDE, humor),
        education=education,
        education_guide=EDUCATION_GUIDE[education],
        **styles,
        style_guide=style_guide(styles),
        topic=dials.topic or classify_topic(prompt),
        platform=platform,
        platform_guide=PLATFORM_GUIDE[platform],
        include_code=include_code,
        revision_passes=dials.revision_passes if dials.revision_passes is not None else default_revisions,
    )
