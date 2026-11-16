"""Application settings.

Every value has a smart default so Inferno Ghostwriter runs with zero configuration.
Values can be overridden with ``INFERNO_GHOSTWRITER_*`` environment variables or a
``.env`` file at the repository root.
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from inferno_ghostwriter.legacy import adopt_legacy_env, move_legacy_app_folder

# backend/src/inferno_ghostwriter/config.py -> repository root is three levels above the package.
REPO_ROOT = Path(__file__).resolve().parents[3]

# The Windows installer build (PyInstaller, see packaging/) has no repository: the web app ships
# inside the bundle and user data lives in %LOCALAPPDATA%\Inferno Ghostwriter.
FROZEN = bool(getattr(sys, "frozen", False))
adopt_legacy_env()  # PROSEFERNO_* from before the rename
if FROZEN:
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    HOME_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "Inferno Ghostwriter"
    FRONTEND_DIST = BUNDLE_DIR / "frontend_dist"
    move_legacy_app_folder(HOME_DIR)
else:
    HOME_DIR = REPO_ROOT
    FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"

Effort = Literal["low", "medium", "high", "xhigh", "max"]
# "api": Anthropic API (Console credits). "subscription": the user's Claude Pro/Max plan via Claude Code.
Connection = Literal["api", "subscription"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="INFERNO_GHOSTWRITER_",
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
    # An independent panel picks the funniest pitch, then a review looks at the drawn meme (one redraw if it reads badly).
    effort_meme_verdict: Effort = "medium"
    effort_meme_review: Effort = "medium"
    meme_review: bool = True
    # The opening image is the thumbnail: pitching across styles is worth the most thought, then an independent panel
    # judges the pitches, and a final review looks at the finished picture.
    effort_opening_ideas: Effort = "high"
    effort_opening_judge: Effort = "medium"
    effort_opening_review: Effort = "medium"
    # Web searches for the numbers behind a data opener (chart or big number).
    opening_max_searches: int = 4
    effort_detect: Effort = "low"
    effort_insights: Effort = "low"
    # Planning, researching and weaving references (sources, quotes, social posts, resources) into a post.
    effort_references: Effort = "medium"
    # Learning from published posts: what the author's edits and their hits say about the persona.
    effort_evolve: Effort = "medium"
    # Idea Lab: the web search scouts and the digest that groups what they found into trends; writing the ideas;
    # scoring and theming them.
    effort_idea_research: Effort = "medium"
    effort_idea_ideas: Effort = "high"
    effort_idea_rank: Effort = "medium"
    # Web searches per scout at standard depth (quick halves it, deep nearly doubles it); several scouts run per refresh.
    idea_max_searches: int = 8
    # How many days back the feeds and scouts look.
    idea_window_days: int = 14
    revision_passes: int = 1
    research_max_searches: int = 8
    # Web searches per reference; each reference is researched on its own.
    reference_max_searches: int = 3
    # Fetch every reference URL once and drop the ones that are gone (404/410/no such host).
    check_reference_links: bool = True

    # Score every generated post for AI-writing tells with a Claude judge (heuristics always run).
    ai_detection: bool = True
    # The twin test: Claude is shown passages of the post next to the author's real paragraphs and asked which is human.
    effort_twin: Effort = "low"
    twin_pairs: int = 4
    # Real AI-text detector models, run on this computer (see authenticity.local_detector). Off until set up in Settings.
    # Which detectors score a post (authenticity.local_detector.CATALOG): "light" is built in and needs no download;
    # "curvature" (Fast-DetectGPT) and "classifier" need the one-time setup. Any mix works; empty turns detection off.
    detector_models: list[str] = ["light"]
    detector_zero_shot_model: str = "openai-community/gpt2"
    detector_classifier_model: str = "fakespot-ai/roberta-base-ai-text-detection-v1"
    # Humanize rounds after the editor: rewrite only what the detectors and the twin test flag, keep the better version.
    humanize_rounds: int = 1

    # Demo mode: canned AI responses and images (no keys, no cost).
    demo: bool = False
    # In demo mode, start an empty database with the example persona and post so there is something to look at.
    demo_seed: bool = True

    # OS keychain service name for stored secrets.
    keyring_service: str = "inferno-ghostwriter"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "inferno_ghostwriter.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
