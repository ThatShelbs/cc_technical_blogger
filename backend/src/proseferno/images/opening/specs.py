"""Structured outputs for the opening room: pitches, the panel's verdict, a template build and the render review."""

from __future__ import annotations

from pydantic import BaseModel, Field


class OpeningConcept(BaseModel):
    style: str = Field(description="Opening style id from the catalog.")
    template: str = Field(
        description="Template id for code-drawn styles (cheat_sheet, data_chart, big_number, versus, framework); '' otherwise."
    )
    hook: str = Field(description="Why a reader scrolling past stops and clicks, in one sentence.")
    concept: str = Field(description="What the picture shows, concretely enough for an illustrator to draw it.")
    content: str = Field(description="The key words, steps, rows or labels it needs, taken from the post; '' for wordless art.")
    data_claim: str = Field(
        description="For data styles: the one factual point and the numbers needed to show it, with where they come from. '' otherwise."
    )


class OpeningIdeas(BaseModel):
    concepts: list[OpeningConcept] = Field(description="Distinct concepts, as many as asked for.")


class JudgeScore(BaseModel):
    concept: int = Field(description="Index of the concept in the list, from 0.")
    scroller: int = Field(description="Would a reader scrolling a feed stop and click at 300px wide? 1-10.")
    art_director: int = Field(description="Crisp, professional, clearly designed by a person; no generic AI clichés. 1-10.")
    fact_checker: int = Field(description="Accurate, specific, and (for data) sourceable; implies nothing false. 1-10.")
    author: int = Field(description="Relevant to the title and the post's promise, and in the author's voice. 1-10.")
    note: str = Field(description="One line: the strongest point and the biggest risk.")


class OpeningVerdict(BaseModel):
    scores: list[JudgeScore] = Field(description="One entry per concept, in order.")
    summary: str = Field(description="One sentence on which concept the panel would publish and why.")


class OpeningItem(BaseModel):
    label: str = Field(description="Short label: a step, rule, row, quadrant, layer or date.")
    detail: str = Field("", description="One short line under or beside the label ('' if the template does not use it).")


class OpeningDatum(BaseModel):
    label: str = Field(description="Category or x value (a date, a name, a factor).")
    value: float
    series: str = Field("", description="Series name when the template has more than one ('' otherwise).")


class OpeningSource(BaseModel):
    title: str = Field(description="Short source name as printed on the image, e.g. the publisher and year.")
    url: str = Field("", description="The source URL, exactly as it appears in the research ('' when the number is from the post).")


class OpeningBuild(BaseModel):
    """The words and data a code template lays out. Each template uses only some fields (see its spec)."""

    headline: str = Field(description="The takeaway headline at the top of the image.")
    subhead: str = Field("", description="One short line of context under the headline.")
    items: list[OpeningItem] = Field(default_factory=list)
    data: list[OpeningDatum] = Field(default_factory=list)
    number: str = Field("", description="Big number templates: the figure as printed, e.g. '73%' or '$4.2M'.")
    unit: str = Field("", description="Charts: the unit of the values, e.g. '%', '$M', 'ms' ('' for plain counts).")
    left_label: str = Field("", description="Versus: left column title. Matrix: x-axis label. Charts: first series name.")
    right_label: str = Field("", description="Versus: right column title. Matrix: y-axis label. Charts: second series name.")
    annotation: str = Field("", description="Charts: one short callout pointing at the key point ('' for none).")
    sources: list[OpeningSource] = Field(default_factory=list, description="Data templates: where every number comes from.")
    alt: str = Field(description="Alt text describing the image for a reader who cannot see it.")
    caption: str = Field(description="Caption in the author's style; no credit line.")


class RenderReview(BaseModel):
    passes: bool = Field(description="True if this image is ready to publish as the post's thumbnail and opening image.")
    clickability: int = Field(description="Would it make someone click at 300px wide? 1-10.")
    craft: int = Field(description="Crisp, balanced, legible, professional; nothing broken, cramped or generic. 1-10.")
    problems: list[str] = Field(default_factory=list, description="Specific visible problems, worst first.")
    fix: str = Field("", description="Concrete instructions for a redraw that fixes them ('' when it passes).")
