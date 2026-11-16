"""Learn a voice: sample analysis, best-practice research, voice profile synthesis and example selection."""

from inferno_ghostwriter.voice.exemplars import format_exemplars, rank_by_similarity, select_exemplars
from inferno_ghostwriter.voice.pipeline import (
    VoiceError,
    current_voice_profile,
    generate_voice_profile,
    latest_voice_profile,
    unpin,
    voice_profile_version,
)
from inferno_ghostwriter.voice.schemas import SampleAnalysis

__all__ = [
    "SampleAnalysis",
    "VoiceError",
    "current_voice_profile",
    "format_exemplars",
    "generate_voice_profile",
    "latest_voice_profile",
    "rank_by_similarity",
    "select_exemplars",
    "unpin",
    "voice_profile_version",
]
