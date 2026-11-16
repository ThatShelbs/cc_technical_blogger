"""Add a reference from a link the author pasted.

The page is read (never searched for), Claude decides where in the finished post it fits best (a sentence that
already talks about it, or the "Go deeper" list), and the usual weave and checks run on it: the pasted address is
the one allowed link, so nothing else can slip in. A link that cannot be read or worked in fails the job with a
plain message and leaves the post alone.
"""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import Engine
from sqlmodel import Session

from inferno_ghostwriter.config import Settings
from inferno_ghostwriter.db import Project
from inferno_ghostwriter.jobs import JobContext
from inferno_ghostwriter.llm import LLM, LLMError
from inferno_ghostwriter.prompts import render
from inferno_ghostwriter.writer.pages import PageReader, PageReadError
from inferno_ghostwriter.writer.pipeline import WriterError
from inferno_ghostwriter.writer.references import (
    DEFAULT_GO_DEEPER_HEADING,
    KIND_LABEL,
    PlannedReference,
    WovenReference,
    _existing_text,
    _history_entry,
    _load,
    _save_text,
    _slot_number,
    check_edit,
    in_post,
    links_in,
    norm_url,
    page_research,
    place,
    plan_references,
    project_references,
    to_rows,
    weave,
)
from inferno_ghostwriter.writer.schemas import ReferencePlan, ReferenceSlot, UrlPlacement
from inferno_ghostwriter.writer.tweak import finish_text

KIND_HINTS = {
    "source": "The author says this link is a source: back up a claim.",
    "resource": "The author says this link is a resource: something to use next.",
    "related_article": "The author says this link is a related article: something to read next.",
}


async def add_reference_url(
    *,
    engine: Engine,
    llm: LLM,
    settings: Settings,
    pages: PageReader,
    project_id: int,
    url: str,
    kind: str | None,
    note: str,
    ctx: JobContext,
) -> dict[str, Any]:
    """Read the pasted page, pick the best spot for it, and work it into the post as a tracked reference."""
    c = _load(engine, settings, project_id)
    markdown = c.project.markdown
    await ctx.progress(0.1, "Reading the page")
    try:
        page = await pages.read(url)
    except PageReadError as exc:
        raise WriterError(str(exc)) from exc

    with Session(engine) as session:
        rows = project_references(session, project_id)
    present = [r for r in rows if r.status == "ready" and in_post(r, markdown)]
    known = {norm_url(r.url) for r in present} | {norm_url(u) for u in links_in(markdown)}
    if norm_url(page.url) in known or norm_url(url) in known:
        raise WriterError("That link is already in the post.")

    await ctx.progress(0.3, "Finding the best spot for it")
    try:
        placement = await llm.structured(
            task="reference url placement",
            system=c.system,
            prompt=render(
                "reference_url_place",
                page_title=page.title or "(no title)",
                url=page.url,
                page_description=page.description or "(none)",
                page_text=page.text or "(no readable text)",
                note=note.strip() or "(none)",
                kind_hint=KIND_HINTS.get(kind or "", ""),
                existing=_existing_text(present),
                markdown=markdown,
            ),
            schema=UrlPlacement,
            effort=settings.effort_references,
            usage=ctx.add_usage,
        )
    except LLMError as exc:
        raise WriterError(f"Couldn't decide where this link belongs ({exc}). Try again.") from exc

    start_index = max((_slot_number(r.slot_id) for r in rows), default=0) + 1
    taken = [r.inserted for r in present if r.inserted]
    planned_list: list[PlannedReference] = []
    for want in dict.fromkeys([kind or placement.kind, "resource"]):
        slot = ReferenceSlot(
            kind=cast(Any, want),
            placement=placement.placement,
            anchor=placement.anchor,
            purpose=placement.purpose or note.strip(),
            query=page.url,
        )
        planned_list = plan_references(ReferencePlan(slots=[slot]), markdown, count=1, kinds=[want], start_index=start_index, taken=taken)
        if planned_list:
            break
    if not planned_list:
        raise WriterError("Couldn't find a sentence or a list in the post where this link fits. Try adding a note about where it belongs.")
    planned = planned_list[0]
    label = KIND_LABEL[planned.kind]

    await ctx.progress(0.55, f"Working the {label} into the post")
    research = page_research(page)
    try:
        edits = await weave(
            llm=llm, settings=settings, system=c.system, markdown=markdown, dials=c.dials, slots=[(planned, research)], usage=ctx.add_usage
        )
    except LLMError as exc:
        raise WriterError(f"Couldn't work the link into the post ({exc}). Try again.") from exc
    edit = next((e for e in edits.edits if e.slot == planned.slot_id), edits.edits[0] if edits.edits else None)
    if edit is None:
        raise WriterError("Claude didn't work the link in. Try again.")
    error, fields = check_edit(planned, edit, research)
    if error:
        raise WriterError(error.replace(" Click Redraw to try again.", " Try again."))

    heading = " ".join(edits.go_deeper_heading.split()).strip("# ") or DEFAULT_GO_DEEPER_HEADING
    heading = next((r.anchor for r in present if r.placement == "go_deeper" and r.anchor), heading)
    woven = WovenReference(planned=planned)
    placed = place(markdown, woven, fields["replace"], heading)
    if placed is None:
        raise WriterError("The sentence for this link changed before it could be placed. Try again.")
    new_markdown, woven.original = placed
    new_markdown = finish_text(new_markdown, c.project.plan)
    woven.inserted, woven.url, woven.title, woven.speaker, woven.quote = (
        fields["replace"],
        fields["url"],
        fields["title"],
        fields["speaker"],
        fields["quote"],
    )
    woven.heading = heading if planned.placement == "go_deeper" else ""
    woven.tried = [page.url]
    woven.status = "ready"
    lost = woven.inserted not in new_markdown.split("\n") if planned.placement == "go_deeper" else woven.inserted not in new_markdown
    if lost:
        raise WriterError("The link was lost while tidying the post. Try again.")

    await ctx.progress(0.9, "Saving")
    with Session(engine) as session:
        project = session.get(Project, project_id)
        if project is None:
            raise WriterError("Project not found.")
        if project.markdown != markdown:
            raise WriterError("The post changed while the link was being added. Try again.")
        _save_text(session, project, new_markdown, f"Added {label}: {woven.title}", c.baseline)
        (row,) = to_rows(project_id, [woven], position=max((r.position for r in rows), default=-1) + 1)
        row.user_supplied = True
        row.history = [_history_entry(woven)]
        session.add(row)
        session.commit()
    await ctx.progress(1.0, f"Added {label}")
    return {"project_id": project_id, "added": 1}
