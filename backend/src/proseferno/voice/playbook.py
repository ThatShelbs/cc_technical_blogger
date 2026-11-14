"""The persona's playbook: what made the author's well-received posts work.

Entries come from approved "secret sauce" proposals (see evolution.service). They feed every writer call
and the next voice profile, best outcomes first, so the persona keeps writing what lands with readers.
Approved profile changes are listed here too, so a voice profile regenerated from samples keeps them.
"""

from __future__ import annotations

from typing import Any

from sqlmodel import Session, col, select

from proseferno.db import Persona, PersonaEvolution, utcnow

MAX_PLAYBOOK = 20
# Higher = stronger evidence that the trait works.
OUTCOME_RANK = {"viral": 3, "good": 2, "small": 1, "too_early": 0}
OUTCOME_LABEL = {"viral": "viral post", "good": "good traction", "small": "small traction", "too_early": "too early to tell"}


def _rank(entry: dict[str, Any]) -> tuple[int, str]:
    return OUTCOME_RANK.get(str(entry.get("outcome") or ""), 0), str(entry.get("added_at", ""))


def add_playbook(persona: Persona, texts: list[str], *, project_id: int | None, title: str, outcome: str | None) -> int:
    """Add entries (skipping ones already there), keep the strongest. Returns how many were added. The caller saves."""
    current = list(persona.playbook or [])
    seen = {str(e.get("text", "")).casefold() for e in current}
    now = utcnow().isoformat()
    added = 0
    for text in texts:
        text = " ".join(text.split())[:300]
        if not text or text.casefold() in seen:
            continue
        seen.add(text.casefold())
        current.append({"text": text, "project_id": project_id, "title": title, "outcome": outcome, "added_at": now})
        added += 1
    current.sort(key=_rank, reverse=True)
    # Reassign (not mutate) so SQLAlchemy notices the JSON change.
    persona.playbook = current[:MAX_PLAYBOOK]
    return added


def forget_playbook(persona: Persona, index: int | None) -> None:
    """Forget one entry (by index) or, with None, all of them. The caller saves."""
    if index is None:
        persona.playbook = []
        return
    entries = list(persona.playbook or [])
    if 0 <= index < len(entries):
        entries.pop(index)
    persona.playbook = entries


def format_playbook(playbook: list[dict[str, Any]] | None, limit: int = 10) -> str:
    """Markdown bullets for prompts; empty when nothing has been learned yet."""
    lines = []
    for entry in (playbook or [])[:limit]:
        label = OUTCOME_LABEL.get(str(entry.get("outcome") or ""), "")
        source = f' ({label}: "{entry.get("title")}")' if label and entry.get("title") else ""
        lines.append(f"- {entry.get('text', '')}{source}")
    return "\n".join(lines)


def approved_changes(session: Session, persona_id: int, limit: int = 20) -> str:
    """Voice profile changes the author approved after publishing, newest first, as Markdown bullets."""
    rows = session.exec(
        select(PersonaEvolution)
        .where(PersonaEvolution.persona_id == persona_id, PersonaEvolution.applied_version != None)  # noqa: E711
        .order_by(col(PersonaEvolution.applied_at).desc())
    )
    lines: list[str] = []
    for row in rows:
        for item in row.items or []:
            if item.get("applied") and item.get("target") == "profile":
                lines.append(f"- {item.get('change', '')}")
    return "\n".join(lines[:limit])
