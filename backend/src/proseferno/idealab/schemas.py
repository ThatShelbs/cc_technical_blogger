"""What Claude returns to Idea Lab: the research digest, a batch of ideas, and the ranking."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

TrendKind = Literal["launch", "claim", "industry_pattern", "creator_wave", "question"]
ShelfLife = Literal["this_week", "this_month", "evergreen"]


class Trend(BaseModel):
    kind: TrendKind = Field(
        description="launch = a product, model or feature release; claim = a position someone notable is arguing; "
        "industry_pattern = many organisations building or adopting the same thing; creator_wave = several writers "
        "publishing on the same subject; question = something practitioners keep asking."
    )
    label: str = Field(description="A short specific name, 3-9 words, naming the product, person or practice.")
    summary: str = Field(description="2-3 sentences: what happened, who is involved, and why practitioners care.")
    heat: int = Field(ge=1, le=10, description="How much attention it is getting right now; 10 = everyone is talking about it.")
    industries: list[str] = Field(default_factory=list, description="Industries it matters to most, if any.")
    evidence_urls: list[str] = Field(description="1-5 URLs copied exactly from the signals or the search citations.")


class TrendDigest(BaseModel):
    trends: list[Trend]


class IdeaDraft(BaseModel):
    title: str = Field(description="The working title of the post, as the author would write it.")
    brief: str = Field(description="2-3 sentences: what the post argues or teaches and who it is for.")
    angle: str = Field(description="One sentence: what makes this the author's post and not the one everyone else writes.")
    outline: list[str] = Field(description="4-7 section bullets, in order, each a specific point (not 'Introduction').")
    why_now: str = Field(description="One sentence: why this is worth writing now.")
    shelf_life: ShelfLife
    article_type: str = Field(description="One id from the article types list, or 'auto'.")
    trend_labels: list[str] = Field(default_factory=list, description="Labels of the trends it rests on, copied exactly; empty if none.")
    builds_on: str = Field("", description="The title of the author's existing post it follows on from, copied exactly; empty if none.")
    tags: list[str] = Field(default_factory=list, description="Up to 3 short tags, e.g. 'sequel', 'calendar', 'tutorial'.")


class IdeaBatch(BaseModel):
    ideas: list[IdeaDraft]


class IdeaScore(BaseModel):
    index: int = Field(description="The idea's number from the list.")
    theme: str = Field(description="One of the themes, exactly as written in `themes`.")
    timeliness: int = Field(ge=1, le=10, description="10 = must be written this week to matter.")
    demand: int = Field(ge=1, le=10, description="10 = many readers are actively looking for this.")
    fit: int = Field(ge=1, le=10, description="10 = squarely what this author is credible and good at.")
    differentiation: int = Field(ge=1, le=10, description="10 = nobody else is writing this angle.")
    effort: int = Field(ge=1, le=10, description="10 = quick to write well; 1 = needs heavy original work.")
    note: str = Field(description="One short sentence: the main reason for its place in the ranking.")


class IdeaRanking(BaseModel):
    themes: list[str] = Field(description="6-10 theme names, 1-3 words each, that between them cover every idea.")
    items: list[IdeaScore]
