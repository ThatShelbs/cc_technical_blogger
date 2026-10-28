"""Text version history: the post as it was before each tweak, rewrite, edit or restore."""

from __future__ import annotations

from typing import Any, Literal

from proseferno.db import Project, utcnow
from proseferno.images import PLACEHOLDER_RE

RevisionKind = Literal["tweak", "rewrite", "edit", "restore"]
MAX_REVISIONS = 10


def push_revision(project: Project, label: str, kind: RevisionKind) -> None:
    """Remember the project's current text (newest first). The caller saves the project."""
    if not project.markdown:
        return
    entry: dict[str, Any] = {
        "markdown": project.markdown,
        "title": project.title,
        "subtitle": project.subtitle,
        "label": " ".join(label.split())[:160],
        "kind": kind,
        "created_at": utcnow().isoformat(),
    }
    # Reassign (not mutate) so SQLAlchemy notices the JSON change.
    project.revisions = [entry, *(project.revisions or [])][:MAX_REVISIONS]


def word_count(markdown: str) -> int:
    return len(PLACEHOLDER_RE.sub("", markdown).split())
