"""Application settings.

Every value has a smart default so Proseferno runs with zero configuration.
Values can be overridden with ``PROSEFERNO_*`` environment variables or a
``.env`` file at the repository root.
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/src/proseferno/config.py -> repository root is three levels above the package.
REPO_ROOT = Path(__file__).resolve().parents[3]

# The Windows installer build (PyInstaller, see packaging/) has no repository: the web app ships
# inside the bundle and user data lives in %LOCALAPPDATA%\Proseferno.
FROZEN = bool(getattr(sys, "frozen", False))
if FROZEN:
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    HOME_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "Proseferno"
    FRONTEND_DIST = BUNDLE_DIR / "frontend_dist"
else:
    HOME_DIR = REPO_ROOT
    FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"

Effort = Literal["low", "medium", "high", "xhigh", "max"]
# "api": Anthropic API (Console credits). "subscription": the user's Claude Pro/Max plan via Claude Code.
Connection = Literal["api", "subscription"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PROSEFERNO_",
        env_file=HOME_DIR / ".env",
        extra="ignore",
    )

    # Where all user data lives (database, samples, voice profiles, images, exports).
    data_dir: Path = HOME_DIR / "data"
    host: str = "127.0.0.1"
    port: int = 8732
    # Optional folder of the user's own writing, offered for one-click import.
    seed_samples_dir: Path = HOME_DIR / "my_writing_examples"
    frontend_dist: Path = FRONTEND_DIST

    # Claude
    claude_connection: Connection = "api"
    model: str = "claude-opus-5-5"
    use_fallbacks: bool = True
    effort_analyze: Effort = "low"
    effort_research: Effort = "medium"
    effort_synthesize: Effort = "high"
    effort_plan: Effort = "medium"
    effort_draft: Effort = "high"
    effort_critique: Effort = "medium"
    effort_images: Effort = "medium"
    # The meme writers' room: pitching and judging five jokes is worth more thought than drawing one.
    effort_meme_ideas: Effort = "high"
    effort_detect: Effort = "low"
    revision_passes: int = 1
    research_max_searches: int = 8

    # Score every generated post for AI-writing tells with a Claude judge (heuristics always run).
    ai_detection: bool = True

    # Demo mode: canned AI responses and images (no keys, no cost).
    demo: bool = False
    # In demo mode, start an empty database with the example persona and post so there is something to look at.
    demo_seed: bool = True

    # OS keychain service name for stored secrets.
    keyring_service: str = "proseferno"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "proseferno.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
