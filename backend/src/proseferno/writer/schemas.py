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


class Callback(BaseModel):
    """A thread the post comes back to: a running joke or a key concept the reader should keep hold of."""

    kind: Literal["running_joke", "key_concept"]
    idea: str = Field(description="The joke or concept in one line, specific to this post.")
    introduce_in: int = Field(description="Section index where it is set up (-1 = the opening hook).")
    revisit_in: list[int] = Field(description="Section indexes where it comes back, each time adding something new.")
    payoff: str = Field(description="How the closing (or the last revisit) lands it.")


class ArticlePlan(BaseModel):
    title_options: list[str] = Field(description="Five title options in the author's title style.")
    chosen_title: str
    subtitle: str
    hook: str = Field(description="How the post opens.")
    sections: list[SectionPlan]
    closing: str = Field(description="How the post lands its ending.")
    joke: str = Field(
        description="The closing meme idea: the moment or running joke it pays off, and a format that fits (e.g. a terrible pie chart)."
    )
    callbacks: list[Callback] = Field(
        description="One to three threads the post revisits: running jokes (if the humor level allows) and key concepts."
    )
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
    callbacks: int = Field(
        description="Every running joke and key concept in the plan is set up, revisited with something new, and paid off. Score 1-10."
    )
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


ReferencePlacement = Literal["inline", "blockquote", "go_deeper"]


class ReferenceSlot(BaseModel):
    kind: Literal["source", "quote", "social_post", "resource", "related_article"]
    placement: ReferencePlacement = Field(
        description="inline: a link worked into the anchor sentence. blockquote: a quote or post set off right after the anchor "
        "paragraph. go_deeper: one line in the short list of things to explore next (resources and related articles only)."
    )
    anchor: str = Field(
        description="One sentence copied exactly from the post that this reference backs up or extends; empty for go_deeper."
    )
    purpose: str = Field(description="The claim, concept or next step it supports, and why the reader is better off for it.")
    query: str = Field(description="A web search query that would find it.")


class ReferencePlan(BaseModel):
    slots: list[ReferenceSlot]


class ReferenceEdit(BaseModel):
    slot: str = Field(description="The slot id, e.g. 'r2'.")
    find: str = Field(description="The anchor text copied exactly from the post (empty for go_deeper).")
    replace: str = Field(
        description="The new text for that span with the reference worked in, or the single list line for go_deeper. "
        "Empty if the research does not support this slot."
    )
    url: str = Field(description="The URL linked, copied exactly from the slot's sources.")
    title: str = Field(description="A short name for what is linked: the page, paper, package, video or post.")
    speaker: str = Field(description="Who said or wrote it, for quotes and social posts; empty otherwise.")
    quote: str = Field(description="The exact words quoted, as found in the research; empty if nothing is quoted.")


class ReferenceEdits(BaseModel):
    go_deeper_heading: str = Field(description="A short heading, in the author's voice, for the list of things to explore next.")
    edits: list[ReferenceEdit]


class ImageTextEdits(BaseModel):
    summary: str = Field(description="One plain sentence on what changed in the text; empty when nothing needed to.")
    edits: list[TextEdit] = Field(description="Surgical edits to text that described the old image; empty when nothing refers to it.")


class ImagePlacement(BaseModel):
    kind: Literal["illustration", "diagram", "chart", "icon"] = Field(description="The image that adds the most value here.")
    purpose: str = Field(description="The value this image adds for the reader, in one sentence.")
    brief: str = Field(description="What the image should show, concretely enough to draw, mirroring the passage's own terms.")
    anchor_text: str = Field(
        description="The exact paragraph or sentence (copied from the post) the image goes right after: the nearest sensible break."
    )
    edits: list[TextEdit] = Field(description="Edits to adjacent text so it works with the image; usually empty or one small edit.")
    summary: str = Field(description="One or two plain sentences telling the author where the image went and what else changed.")
