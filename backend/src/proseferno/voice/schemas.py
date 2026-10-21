from __future__ import annotations

from pydantic import BaseModel, Field


class SampleAnalysis(BaseModel):
    summary: str = Field(description="One sentence: what the post is about and its angle.")
    topic: str
    title_pattern: str = Field(description="The formula behind the title and subtitle.")
    hook: str = Field(description="How the post opens and why it works, with a short quote.")
    structure: str = Field(description="How sections flow from hook to close.")
    voice_traits: list[str] = Field(description="Distinct traits, each with a verbatim example.")
    tone: str
    sentence_rhythm: str
    reader_relationship: str = Field(description="How the author addresses and treats the reader.")
    humor_devices: list[str] = Field(description="Humor techniques with verbatim examples.")
    storytelling: str
    teaching_moves: list[str]
    credibility_moves: list[str]
    image_usage: str = Field(description="Image types, placement, and the exact caption/credit format.")
    closing: str = Field(description="How the post ends.")
    signature_phrases: list[str] = Field(description="Verbatim recurring or characteristic phrases.")
    notable_quotes: list[str] = Field(description="2-4 verbatim passages that sound most like the author.")
    techniques_to_borrow: list[str] = Field(description="Transferable craft worth reusing.")
