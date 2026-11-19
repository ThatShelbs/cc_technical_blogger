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


class CastPick(BaseModel):
    role: str = Field(description="A role name from the format's cast list.")
    kind: str = Field(description="Who plays it: ghost, dog, cat, person or robot.")
    expression: str = Field("", description="Only for roles whose expression is open (classic caption): an expression id; else ''.")
    accessory: str = Field("", description="Optional accessory id that adds to the joke (e.g. 'glasses', 'crown'); '' for the default.")


class PanelCharacter(BaseModel):
    role: str = Field(description="A stable name for this character; reuse it in every panel it appears in.")
    kind: str = Field(description="ghost, dog, cat, person or robot.")
    expression: str = Field(description="An expression id from the kit.")
    pose: str = Field(description="A pose id from the kit.")
    position: str = Field("center", description="left, center or right (far_left / far_right also work).")
    facing: str = Field("", description="left or right; '' faces the panel's middle.")
    accessory: str = Field("none", description="An accessory id, or 'none'.")
    prop: str = Field("none", description="A hand prop id, or 'none'.")
    variant: int = Field(0, description="0-2: a different coat for a second character of the same kind.")


class PanelProp(BaseModel):
    name: str = Field(description="A prop id from the kit's prop list.")
    position: str = Field("center", description="left, center or right.")


class PanelPick(BaseModel):
    backdrop: str = Field(description="A backdrop id from the kit.")
    shot: str = Field("wide", description="'wide', or 'close_up' for one character's face filling the panel.")
    characters: list[PanelCharacter] = Field(description="One to three characters.")
    props: list[PanelProp] = Field(default_factory=list, description="Up to two set props.")


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
    cast: list[CastPick] = Field(
        default_factory=list,
        description="Staged formats: who plays each role (the roles the format lists). Empty keeps the format's default cast.",
    )
    panels: list[PanelPick] = Field(
        default_factory=list, description="Comic formats only: one entry per panel, in order. Empty list otherwise."
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
    cast: list[CastPick] = Field(default_factory=list, description="Staged formats: who plays each role.")
    panels: list[PanelPick] = Field(default_factory=list, description="Comic formats: the panel picks.")


class MemeStagingEdit(BaseModel):
    """An edit to a code-staged meme: new words, recasting and (comics) new panel picks; never drawing."""

    texts: list[MemeText] = Field(description="Final words for every text slot (unchanged ones repeated as they are).")
    cast: list[CastPick] = Field(default_factory=list, description="Who plays each role after the edit.")
    panels: list[PanelPick] = Field(default_factory=list, description="Comic formats: every panel after the edit; empty otherwise.")
    note: str = Field("", description="If the request cannot be done with the kit, one sentence on what was done instead.")
