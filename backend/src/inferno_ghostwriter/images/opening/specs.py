"""Structured outputs for the opening room: pitches, a template build and a kit scene (judging is images/panel.py)."""

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
    reader_takeaway: str = Field(
        "",
        description="At a glance, a reader sees ___ and understands ___ (one sentence a stranger could confirm from the picture alone).",
    )


class OpeningIdeas(BaseModel):
    concepts: list[OpeningConcept] = Field(description="Distinct concepts, as many as asked for.")


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


class SceneCharacter(BaseModel):
    kind: str = Field(description="ghost, dog, cat, person or robot (the ghost is the house star).")
    expression: str = Field(description="An expression id from the kit.")
    pose: str = Field(description="A pose id from the kit.")
    slot: str = Field(description="far_left, left, center, right or far_right (see the layout).")
    facing: str = Field("", description="left or right; '' faces the picture's focal point.")
    size: str = Field("large", description="large, medium or small.")
    accessory: str = Field("none", description="An accessory id, or 'none'.")
    prop: str = Field("none", description="A hand prop id, or 'none'.")
    variant: int = Field(0, description="0-2: another coat for a second character of the same kind.")


class ScenePlacement(BaseModel):
    name: str = Field(description="A prop id from the kit's prop list.")
    slot: str = Field(description="far_left, left, center, right or far_right.")
    size: str = Field("medium", description="large, medium or small.")


class SceneLabel(BaseModel):
    text: str = Field(description="One to three words from the post. Never the title.")
    slot: str = Field(description="object, far_left, left, center, right or far_right: what it labels.")


class SceneSpec(BaseModel):
    """A visual-metaphor opener staged from the kit, plus at most one custom object Claude draws."""

    layout: str = Field(description="A layout id from the list.")
    backdrop: str = Field("plain", description="A backdrop id from the kit ('plain' is the scheme's own surface).")
    tone: str = Field("", description="'dark' or 'light' background; '' lets the scheme rotation decide.")
    characters: list[SceneCharacter] = Field(default_factory=list, description="Zero to three kit characters.")
    props: list[ScenePlacement] = Field(default_factory=list, description="Zero to three kit props.")
    object_svg: str = Field(
        "",
        description="The post-specific metaphor object, drawn as SVG elements in viewBox 0 0 600 500 on a transparent "
        "background (no outer <svg>); '' when the kit props carry the idea.",
    )
    labels: list[SceneLabel] = Field(default_factory=list, description="Zero to four short labels.")
    alt: str = Field(description="Alt text: what the picture shows.")
    caption: str = Field(description="Caption in the author's style; no credit line.")
