"""Regenerate one highlighted section of a finished post: rewrite, compact, expand, add a source or quote, or a free brief.

Only the selected span changes; the rest of the text and the images stay as they are. Sources and quotes come
from a web search, so links are real and quotes are attributed to where they were found.
"""

from __future__ import annotations

from typing import Literal, get_args

from sqlalchemy import Engine
from sqlmodel import Session, select

from proseferno.authenticity import analyze, author_profile
from proseferno.config import Settings
from proseferno.db import Persona, Project, ProjectReference, Sample, utcnow
from proseferno.llm import LLM, ResearchResult, SystemBlock
from proseferno.prompts import raw, render
from proseferno.voice import current_voice_profile, format_exemplars, select_exemplars
from proseferno.voice.lessons import format_lessons, record_feedback
from proseferno.writer.pipeline import WriterError, measure, split_title, writer_system
from proseferno.writer.references import PlannedReference, check_edit, links_in, project_references, research_block
from proseferno.writer.revisions import push_revision
from proseferno.writer.schemas import ReferenceEdit
from proseferno.writer.tweak import finish_text

SectionAction = Literal["custom", "rewrite", "compact", "expand", "add_source", "add_quote"]
SECTION_ACTIONS: tuple[str, ...] = get_args(SectionAction)

GUIDANCE: dict[str, str] = {
    "custom": "Follow the author's instruction.",
    "rewrite": "Say the same thing with fresh phrasing and rhythm. Keep the meaning, the facts, and roughly the length.",
    "compact": (
        "Make it noticeably shorter, about half the length if the content allows. Keep the point, the key facts and "
        "the voice; cut padding, repetition and throat-clearing."
    ),
    "expand": (
        "Make it fuller, about one and a half to two times the length. Add depth with a concrete example, a reason or "
        "a consequence, in the author's voice, without repeating yourself or drifting off topic."
    ),
    "add_source": (
        "Work in exactly one source for a claim this passage makes, as a markdown link in the author's natural phrasing. "
        "Use only a URL from the supplied sources. Do not invent or alter URLs, and do not add a claim the source does not support."
    ),
    "add_quote": (
        "Work in exactly one short, well-known quote that fits this passage, introduced the way the author would introduce it "
        "and attributed to its speaker, with a markdown link to the page where it was found. Use only a quote that appears in "
        "the supplied research, worded exactly as found, and only a URL from the supplied sources. Never paraphrase it or invent one."
    ),
}
LABEL: dict[str, str] = {
    "custom": "Rewrite",
    "rewrite": "Rewrite section",
    "compact": "Compact section",
    "expand": "Expand section",
    "add_source": "Add source",
    "add_quote": "Add quote",
}
RESEARCH_ACTIONS = ("add_source", "add_quote")


async def _research(llm: LLM, settings: Settings, action: str, title: str, selection: str, instruction: str) -> ResearchResult:
    result = await llm.research(
        system=[SystemBlock(raw("section_research_system"))],
        prompt=render(
            "section_research",
            want="a reputable source that supports a claim in the passage"
            if action == "add_source"
            else "a short, well-known quote that fits the passage",
            title=title,
            selection=selection,
            instruction=instruction.strip() or "(none)",
        ),
        effort=settings.effort_research,
        max_searches=min(4, settings.research_max_searches),
    )
    if not result.citations:
        what = "source" if action == "add_source" else "quote"
        raise WriterError(
            f"Couldn't find a verifiable {what} for that passage. Try a more specific passage, or write your own with a custom brief."
        )
    return result


def _checked_reference(action: str, selection: str, replacement: str, result: ResearchResult) -> dict[str, str] | None:
    """The source or quote the passage now links, checked against the research; None for a quote with no link."""
    kind = "source" if action == "add_source" else "quote"
    if kind == "quote" and not links_in(replacement):
        return None
    planned = PlannedReference(slot_id="", kind=kind, placement="inline", anchor=selection, purpose="", query="")
    edit = ReferenceEdit(slot="", find=selection, replace=replacement, url="", title="", speaker="", quote="")
    error, fields = check_edit(planned, edit, result)
    if error:
        raise WriterError(error.replace(" Click Redraw to try again.", " Try again."))
    return fields


def _record_reference(session: Session, project_id: int, action: str, selection: str, fields: dict[str, str]) -> None:
    """Track a source or quote added from a highlight like the ones the references pass adds, so it gets Redraw too."""
    rows = project_references(session, project_id)
    numbers = [int(r.slot_id[1:]) for r in rows if r.slot_id[1:].isdigit()]
    kind = "source" if action == "add_source" else "quote"
    entry = {k: fields[k] for k in ("url", "title", "speaker", "quote")}
    session.add(
        ProjectReference(
            project_id=project_id,
            slot_id=f"r{max(numbers, default=0) + 1}",
            position=max((r.position for r in rows), default=-1) + 1,
            kind=kind,
            placement="inline",
            anchor=selection,
            purpose=f"Added from a highlighted passage ({LABEL[action].lower()})",
            url=fields["url"],
            title=fields["title"],
            speaker=fields["speaker"],
            quote=fields["quote"],
            original=selection,
            inserted=fields["replace"],
            status="ready",
            tried_urls=[fields["url"]],
            history=[{**entry, "kind": kind, "inserted": fields["replace"], "created_at": utcnow().isoformat()}],
        )
    )


async def rewrite_passage(
    *,
    llm: LLM,
    settings: Settings,
    engine: Engine,
    project_id: int,
    selection: str,
    instruction: str = "",
    action: SectionAction = "custom",
) -> str:
    if action not in SECTION_ACTIONS:
        raise WriterError(f"Unknown action {action!r}.")
    if action == "custom" and not instruction.strip():
        instruction = "Make it sound more like me."
    with Session(engine) as session:
        project = session.get(Project, project_id)
        if project is None:
            raise WriterError("Project not found.")
        voice_profile = current_voice_profile(session, project.persona_id)
        samples = list(session.exec(select(Sample).where(Sample.persona_id == project.persona_id)))
        persona = session.get(Persona, project.persona_id)
    if voice_profile is None:
        raise WriterError("This persona has no voice profile yet.")
    if selection not in project.markdown:
        raise WriterError("The selected passage was not found in the post. It may have changed; select it again.")

    research = ""
    found: ResearchResult | None = None
    if action in RESEARCH_ACTIONS:
        found = await _research(llm, settings, action, project.title, selection, instruction)
        research = research_block(found)

    system = writer_system(
        voice_profile.markdown,
        format_exemplars(select_exemplars(project.prompt, samples)),
        format_lessons(persona.edit_lessons if persona else None),
    )
    replacement = await llm.text(
        task="passage rewrite" if action == "custom" else f"passage {action}",
        system=system,
        prompt=render(
            "rewrite",
            guidance=GUIDANCE[action],
            instruction=instruction.strip() or "(none)",
            research=research,
            markdown=project.markdown,
            selection=selection,
        ),
        effort=settings.effort_critique,
        max_tokens=16000,
    )
    replacement = replacement.strip()
    if not replacement:
        raise WriterError("Claude returned an empty passage. Try again.")
    reference = _checked_reference(action, selection, replacement, found) if found is not None else None
    new_markdown = finish_text(project.markdown.replace(selection, replacement, 1), project.plan)
    title, subtitle = split_title(new_markdown)
    authenticity = await analyze(
        llm=llm,
        settings=settings,
        markdown=new_markdown,
        voice_profile=voice_profile.markdown,
        profile=author_profile(samples, voice_profile.baseline_stylometrics),
        use_judge=settings.ai_detection,
    )
    with Session(engine) as session:
        row = session.get(Project, project_id)
        if row is None:
            raise WriterError("Project not found.")
        label = f"{LABEL[action]}: {instruction.strip()}" if instruction.strip() else LABEL[action]
        push_revision(row, label, "section")
        row.markdown = new_markdown
        row.title, row.subtitle = title or row.title, subtitle or row.subtitle
        row.fidelity = measure(new_markdown, voice_profile.baseline_stylometrics)
        row.authenticity = authenticity
        row.updated_at = utcnow()
        session.add(row)
        if reference is not None and reference["replace"] in new_markdown:
            _record_reference(session, project_id, action, selection, reference)
        if action == "custom" and instruction.strip() != "Make it sound more like me.":
            persona_row = session.get(Persona, project.persona_id)
            if persona_row is not None:
                record_feedback(persona_row, instruction)
                session.add(persona_row)
        session.commit()
    return new_markdown
