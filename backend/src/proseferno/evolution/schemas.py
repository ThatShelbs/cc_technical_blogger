from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Target = Literal["profile", "playbook"]


class EvolutionItem(BaseModel):
    area: str = Field(
        description="The voice profile section this belongs to, e.g. 'Voice & Tone', 'Structure Blueprint', 'Humor', 'Lexicon', 'Titles'."
    )
    change: str = Field(description="One imperative sentence: the small change to how this persona writes. Specific, not generic.")
    evidence: str = Field(description="What in the post shows it: a short before/after or a quote, under 40 words.")
    target: Target = Field(
        description="'profile' to change the voice profile itself (how the author always writes); "
        "'playbook' for a move that made a post land with readers, used where it fits."
    )


class EvolutionPlan(BaseModel):
    """Small persona changes learned from how the author edited a generated post."""

    summary: str = Field(description="Two plain sentences for the author: what their edits had in common.")
    items: list[EvolutionItem] = Field(description="At most six changes, most important first; empty if the edits were only content.")


class SecretSauce(BaseModel):
    """What made a well-received post work, as playbook entries."""

    summary: str = Field(description="Two plain sentences for the author: why this post landed.")
    items: list[EvolutionItem] = Field(description="Three to six traits, most important first.")


class ProfileEdit(BaseModel):
    item: str = Field(description="The id of the change this edit makes, e.g. 'c1'.")
    find: str = Field(description="Text copied exactly from the voice profile, long enough to appear only once.")
    replace: str = Field(description="The new text for that span.")


class ProfileEdits(BaseModel):
    summary: str = Field(description="One sentence: what changed in the voice profile.")
    edits: list[ProfileEdit] = Field(description="Small, surgical edits; keep every section heading.")
