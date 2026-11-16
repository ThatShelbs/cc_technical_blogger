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


class MixCategory(BaseModel):
    name: str = Field(description="One or two words, e.g. 'Chatty', 'Data', 'Jokes', 'How-to'.")
    description: str = Field(description="What a sentence in this category does, in under 10 words.")


class SentenceLabel(BaseModel):
    index: int = Field(description="The sentence number from the numbered list.")
    category: str = Field(description="The name of one of mix_categories, exactly as written there.")


class VoiceInsights(BaseModel):
    """A short, quotable digest of a voice profile for the persona's Insights page."""

    headline: str = Field(description="One short verdict on the voice mix, under 8 words, e.g. 'Mostly chatty, backed up by data.'")
    tone: list[str] = Field(description="4-6 tone and voice traits, each under 8 words.")
    signature_phrases: list[str] = Field(description="4-8 phrases quoted verbatim from the author's writing.")
    steer_clear: list[str] = Field(description="2-5 things this author avoids, each under 8 words.")
    mix_categories: list[MixCategory] = Field(description="3-5 kinds of sentence that make up this voice.")
    sentence_categories: list[SentenceLabel] = Field(description="One label for every numbered sentence.")
    image_habits: list[str] = Field(description="3-4 short lines on how the author uses images and captions.")
    caption_example: str = Field(description="The author's caption or credit format, verbatim, or an empty string.")
