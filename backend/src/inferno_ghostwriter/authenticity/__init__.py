"""AI-generation detection, calibrated to the author: detector models, the twin test, a tell scan and texture (100 reads as human)."""

from inferno_ghostwriter.authenticity.detector import AIDetectionJudgement, analyze, author_profile, band, blend, report, run_detectors
from inferno_ghostwriter.authenticity.heuristics import AuthorProfile, ScanResult, profile_author, scan

__all__ = [
    "AIDetectionJudgement",
    "AuthorProfile",
    "ScanResult",
    "analyze",
    "author_profile",
    "band",
    "blend",
    "profile_author",
    "report",
    "run_detectors",
    "scan",
]
