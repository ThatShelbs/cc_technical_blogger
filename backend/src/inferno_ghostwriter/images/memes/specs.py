"""Structured outputs for the two meme calls: the writers' room (ideas) and production (build)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MemeText(BaseModel):
    slot: str = Field(description="Text slot name from the format spec.")
    text: str = Field(description="The words for this slot (empty to leave an optional slot blank).")
    speaker: str = Field(description="Comic bubbles only: 'left', 'right' or 'center' (where the tail points). Empty otherwise.")


class ConceptScores(BaseModel):
    relevance: int = Field(description="Tied to a specific idea, moment or term in this post. 1-5.")
    recognizability: int = Field(description="Reads as the format instantly, in under 5 seconds. 1-5.")
    surprise: int = Field(description="The twist is unexpected yet obviously true. 1-5.")
    clarity: int = Field(description="Gets the joke without reading the post twice. 1-5.")
    voice_fit: int = Field(description="Sounds like the author's own sense of humor. 1-5.")
    standalone: int = Field(description="Still funny shared on its own, without the article. 1-5.")


class MemeDatum(BaseModel):
    label: str = Field(description="Category, slice or x value.")
    value: float
    series: str = Field(description="Series name for multi-series charts; empty otherwise.")


class MemeConcept(BaseModel):
    format: str = Field(description="A format id from the menu.")
    premise: str = Field(description="The joke in one sentence.")
    callback: str = Field(description="The moment, term or running gag in the post this pays off.")
    texts: list[MemeText] = Field(description="Final words for every text slot of the format.")
    data: list[MemeDatum] = Field(description="Chart data, only for formats whose menu entry asks for it; empty list otherwise.")
    caption: str = Field(description="A short caption to sit under the image, in the author's style. Never repeats the meme's words.")
    look: str = Field(
        default="",
        description="The look id from the looks menu that serves this joke best (it also varies from the author's recent memes).",
    )
    scores: ConceptScores


class MemeIdeas(BaseModel):
    angles: list[str] = Field(
        default_factory=list, description="About 12 one-line raw comedy angles found in the post, written before the concepts."
    )
    concepts: list[MemeConcept] = Field(description="Five distinct concepts, at least three format families.")
    chosen: int = Field(description="Index of the strongest concept.")
    why: str = Field(description="One sentence on why the chosen concept wins.")


class MemeArt(BaseModel):
    region: str = Field(description="Art region name from the format spec.")
    svg: str = Field(description="SVG elements for this region, drawn in the region's own viewBox (no outer <svg> needed).")


class MemeBuild(BaseModel):
    texts: list[MemeText] = Field(description="Final words for every text slot.")
    cast_defs: str = Field(
        description="SVG <symbol> elements (each with an id and viewBox) for characters reused across regions; empty if unused."
    )
    art: list[MemeArt] = Field(description="Art for every art region of the format (empty list for formats with no regions).")
    data: list[MemeDatum] = Field(description="Chart data for chart formats; empty list otherwise.")
    alt: str = Field(description="Alt text: what the image shows, including every word in it.")
    caption: str = Field(description="Caption in the author's style, without the credit.")


class MemeJudge(BaseModel):
    concept: int = Field(description="Index of the concept in the list, from 0.")
    feed_reader: int = Field(description="A tired senior practitioner scrolling a feed: would they laugh and share it? 1-10.")
    comedy_editor: int = Field(description="A comedy editor: a real twist, economy of words, the punch word last, no explaining. 1-10.")
    author: int = Field(description="The author: pays off this post and sounds like their humor. 1-10.")
    gets_it: int = Field(description="Does a reader who has not read the post understand the joke in five seconds? 1-10.")
    note: str = Field(description="One line: what makes it land and the biggest risk.")


class MemeVerdict(BaseModel):
    scores: list[MemeJudge] = Field(description="One entry per concept, in order.")
    chosen: int = Field(description="Index of the concept the panel would publish.")
    punch_up: list[MemeText] = Field(
        default_factory=list,
        description="Sharper final words for the chosen concept, one entry per text slot (same names and limits). Empty if already tight.",
    )
    summary: str = Field(description="One sentence on why the chosen concept wins.")


class MemeReview(BaseModel):
    passes: bool = Field(description="True if this meme is ready to publish as it is.")
    funny: int = Field(description="Would it get a laugh and a share at thumbnail size? 1-10.")
    craft: int = Field(description="Legible, balanced, on-look, the ghost on-model; nothing covered, cramped or broken. 1-10.")
    problems: list[str] = Field(default_factory=list, description="Specific visible problems, worst first.")
    fix: str = Field("", description="Concrete instructions for a redraw that fixes them ('' when it passes).")
