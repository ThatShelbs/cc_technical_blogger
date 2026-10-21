"""Filesystem layout under the data directory."""

from __future__ import annotations

import re
from pathlib import Path


class Storage:
    def __init__(self, data_dir: Path) -> None:
        self.root = data_dir
        self.root.mkdir(parents=True, exist_ok=True)

    def persona_dir(self, persona_id: int) -> Path:
        return self._ensure(self.root / "personas" / str(persona_id))

    def sample_dir(self, persona_id: int) -> Path:
        return self._ensure(self.persona_dir(persona_id) / "samples")

    def voice_soul_path(self, persona_id: int, version: int) -> Path:
        return self._ensure(self.persona_dir(persona_id) / "voice_soul") / f"voice_soul.v{version}.md"

    def project_dir(self, project_id: int) -> Path:
        return self._ensure(self.root / "projects" / str(project_id))

    def image_dir(self, project_id: int) -> Path:
        return self._ensure(self.project_dir(project_id) / "images")

    def export_dir(self, project_id: int) -> Path:
        return self._ensure(self.project_dir(project_id) / "exports")

    @staticmethod
    def _ensure(path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        return path


def safe_filename(name: str, default: str = "file") -> str:
    """Strip path separators and unsafe characters from a user-supplied file name."""
    name = Path(name).name
    name = re.sub(r"[^\w.\- ]+", "_", name).strip(" .")
    return name or default


def slugify(text: str, max_len: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].rstrip("-") or "post"
