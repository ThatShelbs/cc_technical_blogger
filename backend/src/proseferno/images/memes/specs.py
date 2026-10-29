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


class MemeConcept(BaseModel):
    format: str = Field(description="A format id from the menu.")
    premise: str = Field(description="The joke in one sentence.")
    callback: str = Field(description="The moment, term or running gag in the post this pays off.")
    texts: list[MemeText] = Field(description="Draft words for every text slot of the format.")
    scores: ConceptScores


class MemeIdeas(BaseModel):
    concepts: list[MemeConcept] = Field(description="Five distinct concepts, at least three format families.")
    chosen: int = Field(description="Index of the strongest concept.")
    why: str = Field(description="One sentence on why the chosen concept wins.")


class MemeArt(BaseModel):
    region: str = Field(description="Art region name from the format spec.")
    svg: str = Field(description="SVG elements for this region, drawn in the region's own viewBox (no outer <svg> needed).")


class MemeDatum(BaseModel):
    label: str = Field(description="Category, slice or x value.")
    value: float
    series: str = Field(description="Series name for multi-series charts; empty otherwise.")


class MemeBuild(BaseModel):
    texts: list[MemeText] = Field(description="Final words for every text slot.")
    cast_defs: str = Field(
        description="SVG <symbol> elements (each with an id and viewBox) for characters reused across regions; empty if unused."
    )
    art: list[MemeArt] = Field(description="Art for every art region of the format (empty list for formats with no regions).")
    data: list[MemeDatum] = Field(description="Chart data for chart formats; empty list otherwise.")
    alt: str = Field(description="Alt text: what the image shows, including every word in it.")
    caption: str = Field(description="Caption in the author's style, without the credit.")
