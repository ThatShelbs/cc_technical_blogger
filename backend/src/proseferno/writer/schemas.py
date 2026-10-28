from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ImageKind = Literal["hero", "illustration", "icon", "diagram", "chart", "meme", "screenshot"]


class SectionPlan(BaseModel):
    heading: str
    key_points: list[str]
    approx_words: int
    include_code: bool = Field(description="True if this section needs a code snippet or LLM prompt.")


class ImageSlot(BaseModel):
    slot_id: str = Field(description="Short id like 'hero', 'img2', 'meme'.")
    kind: ImageKind
    section_index: int = Field(description="-1 for the hero (before the first section), otherwise the section it belongs to.")
    purpose: str = Field(description="The value this image adds for the reader.")
    brief: str = Field(description="What the image should show.")


class ArticlePlan(BaseModel):
    title_options: list[str] = Field(description="Five title options in the author's title style.")
    chosen_title: str
    subtitle: str
    hook: str = Field(description="How the post opens.")
    sections: list[SectionPlan]
    closing: str = Field(description="How the post lands its ending.")
    joke: str = Field(description="The closing joke or meme idea.")
    image_slots: list[ImageSlot]
    tags: list[str] = Field(description="Up to five platform tags.")


class TitleOptions(BaseModel):
    title_options: list[str] = Field(description="New title options in the author's title style.")


class Critique(BaseModel):
    voice: int = Field(description="Sounds exactly like the author. Score 1-10.")
    tone: int = Field(description="Score 1-10.")
    structure: int = Field(description="Score 1-10.")
    humor_match: int = Field(description="Matches the requested humor level. Score 1-10.")
    education_match: int = Field(description="Matches the requested education level. Score 1-10.")
    skimmability: int = Field(description="Score 1-10.")
    image_placement: int = Field(description="Score 1-10.")
    overall: int = Field(description="Score 1-10.")
    strengths: list[str]
    issues: list[str] = Field(description="Specific problems, quoting the offending text.")
    revision_instructions: list[str] = Field(description="Concrete edits to make, most important first.")


class TextEdit(BaseModel):
    find: str = Field(description="Text copied exactly from the post, long enough to appear only once.")
    replace: str = Field(description="The new text for that span (empty to delete it).")


class ImageChange(BaseModel):
    slot_id: str = Field(description="The image to redraw, e.g. 'img2'.")
    brief: str = Field(description="What the redrawn image should show.")


class PostEdits(BaseModel):
    summary: str = Field(description="One or two plain sentences telling the author what changed.")
    edits: list[TextEdit] = Field(description="Surgical text edits, in order; only what the feedback asks for.")
    image_changes: list[ImageChange] = Field(description="Images to redraw because the feedback is about them; usually empty.")
