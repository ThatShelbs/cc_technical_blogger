"""Application settings.

Every value has a smart default so Proseferno runs with zero configuration.
Values can be overridden with ``PROSEFERNO_*`` environment variables or a
``.env`` file at the repository root.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/src/proseferno/config.py -> repository root is three levels above the package.
REPO_ROOT = Path(__file__).resolve().parents[3]

Effort = Literal["low", "medium", "high", "xhigh", "max"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PROSEFERNO_",
        env_file=REPO_ROOT / ".env",
        extra="ignore",
    )

    # Where all user data lives (database, samples, voice souls, images, exports).
    data_dir: Path = REPO_ROOT / "data"
    host: str = "127.0.0.1"
    port: int = 8732
    # Optional folder of the user's own writing, offered for one-click import.
    seed_samples_dir: Path = REPO_ROOT / "my_writing_examples"
    frontend_dist: Path = REPO_ROOT / "frontend" / "dist"

    # Claude
    model: str = "claude-opus-5-5"
    use_fallbacks: bool = True
    effort_analyze: Effort = "low"
    effort_research: Effort = "medium"
    effort_synthesize: Effort = "high"
    effort_plan: Effort = "medium"
    effort_draft: Effort = "high"
    effort_critique: Effort = "medium"
    effort_images: Effort = "medium"
    effort_detect: Effort = "low"
    revision_passes: int = 1
    research_max_searches: int = 8

    # Score every generated post for AI-writing tells with a Claude judge (heuristics always run).
    ai_detection: bool = True

    # Demo mode: canned AI responses and images (no keys, no cost).
    demo: bool = False

    # OS keychain service name for stored secrets.
    keyring_service: str = "proseferno"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "proseferno.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
