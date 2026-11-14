"""Add an image where the author highlighted a passage.

Claude picks the kind of image, what it shows and the paragraph or sentence it follows, and may rework one or two
neighbouring sentences. Code then makes sure the placeholder lands at a safe break (never inside a code block, list,
table or quote, never between a lead-in and its example, never after the closing meme), gives the image a slot in the
plan, and draws it. The change is one undo point in the post's text history.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import Engine
from sqlmodel import Session, col, select

from proseferno.config import Settings
from proseferno.db import Persona, Project, ProjectImage, Sample
from proseferno.images import PLACEHOLDER_RE, ImageService
from proseferno.jobs import JobContext
from proseferno.llm import LLM
from proseferno.prompts import render
from proseferno.voice import current_voice_profile, format_exemplars, select_exemplars
from proseferno.voice.lessons import format_lessons
from proseferno.voice.playbook import format_playbook
from proseferno.writer.examples import _blocks, _is_leadin, _section_index
from proseferno.writer.image_text import describe_image, save_text_change
from proseferno.writer.pipeline import WriterError, writer_system
from proseferno.writer.schemas import ImagePlacement, ImageSlot
from proseferno.writer.tweak import apply_edits, finish_text, locate, plan_slots

MAX_IMAGES = 15
_SENTENCE_END = re.compile(r"[.!?][)\"'”’*_]*$")
# Blocks the image moves past rather than sits next to.
_SKIP = ("heading", "subheading", "image")


def place_placeholder(markdown: str, end: int, tag: str) -> str:
    """Put ``tag`` on its own line at the nearest safe break at or after character offset ``end``.

    A break inside a paragraph (the sentence the image follows) splits the paragraph in two. Anywhere else the image goes
    after the block it falls in; a lead-in ("Here is the file:") or a heading moves it past what comes next, and it
    never lands after the closing meme.
    """
    lines = markdown.split("\n")
    end = max(0, min(end, len(markdown)))
    line = markdown.count("\n", 0, end)
    blocks = _blocks(lines)
    if not blocks:
        return markdown.rstrip() + f"\n\n{tag}\n"
    index = next((i for i, b in enumerate(blocks) if b.start <= line <= b.end), None)
    if index is None:
        index = max((i for i, b in enumerate(blocks) if b.end < line), default=0)

    block = blocks[index]
    if block.kind == "prose" and not _is_leadin(block.text) and block.start <= line <= block.end:
        # A sentence break inside a long paragraph: split it there.
        column = end - sum(len(x) + 1 for x in lines[:line])
        head = lines[line][:column].rstrip()
        tail = "\n".join([lines[line][column:], *lines[line + 1 : block.end + 1]]).strip()
        if tail and head and _SENTENCE_END.search(head):
            rebuilt = [*lines[:line], head, "", tag, "", *tail.split("\n"), *lines[block.end + 1 :]]
            return _keep_before_meme("\n".join(rebuilt), tag)
    # Whole blocks: move past headings, images and lead-ins to the block after them.
    while index + 1 < len(blocks) and (blocks[index].kind in _SKIP or (blocks[index].kind == "prose" and _is_leadin(blocks[index].text))):
        index += 1
    lines[blocks[index].end + 1 : blocks[index].end + 1] = ["", tag, ""]
    return _keep_before_meme("\n".join(lines), tag)


def _keep_before_meme(markdown: str, tag: str) -> str:
    """If the new placeholder ended up after the closing meme, move it to just before the meme."""
    meme = "{{image:meme}}"
    at, meme_at = markdown.find(tag), markdown.find(meme)
    if at < 0 or meme_at < 0 or at < meme_at:
        return _tidy(markdown)
    without = markdown.replace(tag, "", 1)
    meme_at = without.find(meme)
    return _tidy(without[:meme_at] + tag + "\n\n" + without[meme_at:])


def _tidy(markdown: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", markdown).strip() + "\n"


def next_slot_id(taken: set[str]) -> str:
    numbers = [int(m.group(1)) for s in taken if (m := re.fullmatch(r"img(\d+)", s))]
    return f"img{max(numbers, default=1) + 1}"


def _slots_for(project: Project, rows: list[ProjectImage]) -> list[ImageSlot]:
    """The plan's slots, or ones rebuilt from the image rows for an older post that stored none."""
    slots = plan_slots(project.plan)
    if slots:
        return slots
    return [
        ImageSlot(slot_id=r.slot_id, kind=r.kind, section_index=-1 if r.kind == "hero" else 0, purpose=r.purpose, brief=r.prompt)  # type: ignore[arg-type]
        for r in rows
    ]


def _image_list(rows: list[ProjectImage]) -> str:
    return "\n".join(f"- `{{{{image:{r.slot_id}}}}}` ({r.kind}): {r.purpose or r.prompt}" for r in rows) or "(none)"


async def add_image_at(
    *,
    engine: Engine,
    llm: LLM,
    settings: Settings,
    images: ImageService,
    project_id: int,
    selection: str,
    instruction: str = "",
    ctx: JobContext,
) -> dict[str, Any]:
    """Add an image near ``selection`` (an exact slice of the post's Markdown); returns its id, slot and what changed."""
    with Session(engine, expire_on_commit=False) as session:
        project = session.get(Project, project_id)
        if project is None:
            raise WriterError("Project not found.")
        persona = session.get(Persona, project.persona_id)
        voice_profile = current_voice_profile(session, project.persona_id)
        samples = list(session.exec(select(Sample).where(Sample.persona_id == project.persona_id)))
        rows = list(session.exec(select(ProjectImage).where(ProjectImage.project_id == project_id).order_by(col(ProjectImage.position))))
    if persona is None:
        raise WriterError("The project's persona no longer exists.")
    if voice_profile is None:
        raise WriterError("This persona has no voice profile yet.")
    markdown = project.markdown
    if not markdown:
        raise WriterError("Generate the post before adding images.")
    if len(rows) >= MAX_IMAGES:
        raise WriterError(f"A post can have at most {MAX_IMAGES} images. Remove or redraw one instead.")
    selected = locate(markdown, selection)
    if selected is None:
        raise WriterError("The highlighted text is no longer in the post. Select it again.")

    await ctx.progress(0.1, "Finding the right spot for an image")
    system = writer_system(
        voice_profile.markdown,
        format_exemplars(select_exemplars(project.prompt, samples)),
        format_lessons(persona.edit_lessons),
        format_playbook(persona.playbook),
    )
    note = f"\nThe author also said what they want to see: {instruction.strip()}\n" if instruction.strip() else ""
    placement = await llm.structured(
        task="image placement",
        system=system,
        prompt=render(
            "image_add", selection=markdown[selected[0] : selected[1]], instruction=note, images=_image_list(rows), markdown=markdown
        ),
        schema=ImagePlacement,
        effort=settings.effort_critique,
        max_tokens=16000,
        usage=ctx.add_usage,
    )

    # Where: the sentence or paragraph Claude chose, else the highlight itself; code moves it to a safe break.
    anchor = locate(markdown, placement.anchor_text) or selected
    taken = {r.slot_id for r in rows} | {s.slot_id for s in plan_slots(project.plan)} | set(PLACEHOLDER_RE.findall(markdown))
    slot_id = next_slot_id(taken)
    tag = f"{{{{image:{slot_id}}}}}"
    placed = place_placeholder(markdown, anchor[1], tag)
    edited, applied, _skipped = apply_edits(placed, placement.edits)
    if tag not in edited:  # an edit swallowed the placeholder: keep Claude's text out of it
        edited, applied = placed, 0

    slot = ImageSlot(
        slot_id=slot_id,
        kind=placement.kind,
        section_index=_section_index(placed.split("\n"), placed.split("\n").index(tag)),
        purpose=placement.purpose.strip()[:300] or "Illustrates the highlighted passage",
        brief=placement.brief.strip()[:1200] or placement.purpose,
    )
    slots = [*_slots_for(project, rows), slot]
    order = {s: i for i, s in enumerate(PLACEHOLDER_RE.findall(edited))}
    slots.sort(key=lambda s: order.get(s.slot_id, len(order)))
    plan = {**(project.plan or {}), "image_slots": [s.model_dump() for s in slots]}
    final = finish_text(edited, plan)
    new_order = {s: i for i, s in enumerate(PLACEHOLDER_RE.findall(final))}
    created: list[int] = []

    def store(session: Session, row: Project) -> None:
        row.plan = plan
        # Undoing this revision takes the image out again (see the restore endpoint).
        if row.revisions:
            row.revisions = [{**row.revisions[0], "added_slot": slot_id}, *row.revisions[1:]]
        image = ProjectImage(project_id=project_id, slot_id=slot_id, kind=slot.kind, purpose=slot.purpose, prompt=slot.brief)
        session.add(image)
        session.flush()
        if image.id is not None:
            created.append(image.id)
        for existing in session.exec(select(ProjectImage).where(ProjectImage.project_id == project_id)):
            existing.position = new_order.get(existing.slot_id, len(new_order))
            session.add(existing)

    await ctx.progress(0.4, "Checking how the post reads")
    await save_text_change(
        engine=engine,
        llm=llm,
        settings=settings,
        project_id=project_id,
        markdown=final,
        label=f"Before adding an image ({slot_id})",
        kind="image",
        usage=ctx.add_usage,
        also=store,
    )
    image_id = created[0]

    await ctx.progress(0.6, "Drawing the image")
    drawn = await images.create(
        image_id,
        persona=persona,
        title=project.title,
        markdown=final,
        voice_profile=voice_profile.markdown,
        brand_kit=project.brand_kit,
        usage=ctx.add_usage,
    )
    await ctx.emit("image_ready", {"image_id": image_id})
    await ctx.progress(1.0, "Image added")
    return {
        "project_id": project_id,
        "image_id": image_id,
        "slot_id": slot_id,
        "kind": slot.kind,
        "summary": placement.summary.strip(),
        "text_edits": applied,
        "image_error": drawn.error if drawn.status == "error" else None,
        "description": describe_image(drawn),
    }
