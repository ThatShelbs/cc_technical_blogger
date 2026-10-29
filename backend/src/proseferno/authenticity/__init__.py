"""AI-generation detection: a scan calibrated to the author's own samples plus a Claude judge, scored 0-100 (100 reads as human)."""

from proseferno.authenticity.detector import AIDetectionJudgement, analyze, author_profile, band, report
from proseferno.authenticity.heuristics import AuthorProfile, ScanResult, profile_author, scan

__all__ = [
    "AIDetectionJudgement",
    "AuthorProfile",
    "ScanResult",
    "analyze",
    "author_profile",
    "band",
    "profile_author",
    "report",
    "scan",
]
