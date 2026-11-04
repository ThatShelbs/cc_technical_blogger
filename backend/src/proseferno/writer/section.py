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
from proseferno.db import Persona, Project, Sample, utcnow
from proseferno.llm import LLM, ResearchResult, SystemBlock
from proseferno.prompts import raw, render
from proseferno.voice import current_voice_profile, format_exemplars, select_exemplars
from proseferno.voice.lessons import format_lessons, record_feedback
from proseferno.writer.pipeline import WriterError, measure, split_title, writer_system
from proseferno.writer.revisions import push_revision
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
        "and attributed to its speaker. Use only a quote that appears in the supplied research, worded exactly as found. "
        "Never paraphrase it or invent one."
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


def _research_block(result: ResearchResult) -> str:
    sources = "\n".join(f"- [{c.title or c.url}]({c.url})" for c in result.citations)
    return f"<research>\n{result.text.strip()}\n\nSources:\n{sources}\n</research>"


async def _research(llm: LLM, settings: Settings, action: str, title: str, selection: str, instruction: str) -> str:
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
    return _research_block(result)


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
    if action in RESEARCH_ACTIONS:
        research = await _research(llm, settings, action, project.title, selection, instruction)

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
        if action == "custom" and instruction.strip() != "Make it sound more like me.":
            persona_row = session.get(Persona, project.persona_id)
            if persona_row is not None:
                record_feedback(persona_row, instruction)
                session.add(persona_row)
        session.commit()
    return new_markdown
