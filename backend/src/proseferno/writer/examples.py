"""Every example a post introduces must be in the post.

Writers lead into examples the way the author does ("Here is the top of the file:"). When the
example is missing (no image slot was left for it, or an edit cut it) the lead-in dangles. The
editor is told about each one first; whatever is still missing after editing becomes a new image
slot right after its lead-in, so the image step draws it (a "screenshot" is a drawn mock of the screen).
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import Engine
from sqlmodel import Session, col, select

from proseferno.db import Persona, Project, ProjectImage, utcnow
from proseferno.images import PLACEHOLDER_RE, ImageService
from proseferno.voice import current_voice_profile
from proseferno.writer.revisions import push_revision
from proseferno.writer.schemas import ImageKind, ImageSlot

if TYPE_CHECKING:
    from proseferno.writer.pipeline import Reporter

# Never add more than this many images to one post on top of the planned ones.
MAX_EXTRA_SLOTS = 8

_FENCE = re.compile(r"^\s*(```|~~~)")
_LIST = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_KIND_WORDS: list[tuple[re.Pattern[str], ImageKind]] = [
    (re.compile(r"chart|graph|plot", re.I), "chart"),
    (re.compile(r"diagram|flow|pipeline|architecture|loop|map", re.I), "diagram"),
    (re.compile(r"icon", re.I), "icon"),
    (re.compile(r"illustration|scene", re.I), "illustration"),
]


@dataclass
class _Block:
    start: int  # first line index
    end: int  # last line index
    kind: str  # prose | heading | subheading | code | list | table | quote | image
    text: str


def _blocks(lines: list[str]) -> list[_Block]:
    blocks: list[_Block] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if _FENCE.match(line):
            j = i + 1
            while j < len(lines) and not _FENCE.match(lines[j]):
                j += 1
            blocks.append(_Block(i, min(j, len(lines) - 1), "code", ""))
            i = j + 1
            continue
        j = i
        while j + 1 < len(lines) and lines[j + 1].strip() and not _FENCE.match(lines[j + 1]):
            j += 1
        text = "\n".join(lines[i : j + 1]).strip()
        first = lines[i].strip()
        if PLACEHOLDER_RE.fullmatch(first) or first.startswith("!["):
            kind = "image"
        elif first.startswith("## ") or first.startswith("# "):
            kind = "heading"
        elif first.startswith("#"):
            kind = "subheading"
        elif _LIST.match(first):
            kind = "list"
        elif first.startswith("|"):
            kind = "table"
        elif first.startswith(">"):
            kind = "quote"
        elif first.startswith("<"):
            kind = "html"
        else:
            kind = "prose"
        blocks.append(_Block(i, j, kind, text))
        i = j + 1
    return blocks


# A lead-in that shows something ("Here is the file:", "It looks like this:"), not one that the next paragraph answers
# ("There are three options:").
_SHOWS = re.compile(
    r"\b(?:here(?:'|’)?s|here (?:is|are)|this is (?:what|how)|looks? like|below|for (?:example|instance)|"
    r"(?:take a )?look|check (?:it )?out|see|shown?|example|screenshot|snippet|excerpt|in practice|came out)\b",
    re.I,
)


def _is_leadin(text: str) -> bool:
    return text.rstrip(" *_").endswith(":") and bool(_SHOWS.search(_last_sentence(text)))


def find_dangling_leadins(markdown: str) -> list[str]:
    """Prose paragraphs that end in a colon but are not followed by what they introduce."""
    return [block.text for block in _dangling(markdown.split("\n"))]


def _dangling(lines: list[str]) -> list[_Block]:
    blocks = _blocks(lines)
    out: list[_Block] = []
    for index, block in enumerate(blocks):
        if block.kind != "prose" or not _is_leadin(block.text):
            continue
        following = blocks[index + 1] if index + 1 < len(blocks) else None
        if following is None or following.kind in ("prose", "heading"):
            out.append(block)
    return out


def format_missing_examples(markdown: str) -> str:
    """Bullet list for the editor prompt."""
    return "\n".join(f'- "{_last_sentence(text)}"' for text in find_dangling_leadins(markdown)) or "- None found."


def _last_sentence(text: str) -> str:
    plain = re.sub(r"[*_`]", "", " ".join(text.split()))
    parts = re.split(r"(?<=[.!?])\s+", plain)
    return parts[-1].strip() if parts else plain


def _section_index(lines: list[str], line_index: int) -> int:
    return max(0, sum(1 for line in lines[:line_index] if line.startswith("## ")) - 1)


def _kind_for(words: str) -> ImageKind:
    return next((kind for pattern, kind in _KIND_WORDS if pattern.search(words)), "screenshot")


def _previous_prose(lines: list[str], line_index: int) -> str:
    """The block just above a line, when it is a prose paragraph (the lead-in for an image placeholder)."""
    before = _blocks(lines[:line_index])
    return before[-1].text if before and before[-1].kind == "prose" else ""


def _next_prose(lines: list[str], line_index: int) -> str:
    """The block just below a line, when it is a prose paragraph (often the author's remark on the example)."""
    after = _blocks(lines[line_index + 1 :])
    return after[0].text if after and after[0].kind == "prose" else ""


def add_example_slots(markdown: str, slots: list[ImageSlot], *, fill_dangling: bool = True) -> tuple[str, list[ImageSlot]]:
    """Give every introduced example an image slot.

    - A placeholder the writer made up (``{{image:early_meme}}``) right after a lead-in becomes a real slot instead of being dropped.
    - With ``fill_dangling``, a lead-in with nothing after it gets a new placeholder and slot right after it.

    New slots go between the planned ones and the meme, in reading order. The text itself is not changed.
    """
    known = {slot.slot_id for slot in slots}
    used = {int(m) for s in slots for m in re.findall(r"^img(\d+)$", s.slot_id)}
    next_number = max(used | {1}) + 1
    lines = markdown.split("\n")
    added: list[ImageSlot] = []

    def new_slot(kind: ImageKind, purpose: str, brief: str, line_index: int) -> str:
        nonlocal next_number
        slot_id = f"img{next_number}"
        next_number += 1
        slot = ImageSlot(
            slot_id=slot_id,
            kind=kind,
            section_index=_section_index(lines, line_index),
            purpose=purpose[:300] or "The example this part of the post introduces",
            brief=brief[:1200] or purpose,
        )
        added.append(slot)
        return slot_id

    # 1. Placeholders the writer invented.
    for i, line in enumerate(lines):
        match = PLACEHOLDER_RE.fullmatch(line.strip())
        if not match or match.group(1) in known or len(added) >= MAX_EXTRA_SLOTS:
            continue
        name = match.group(1).replace("_", " ").replace("-", " ")
        lead = _previous_prose(lines, i)
        if not _is_leadin(lead):
            continue  # an extra image nobody introduced: dropped later, so the chosen image count holds
        purpose = _last_sentence(lead)
        slot_id = new_slot(_kind_for(name), purpose, f"{name}. Shown right after: {lead}".strip(), i)
        lines[i] = f"{{{{image:{slot_id}}}}}"
        known.add(slot_id)

    # 2. Lead-ins with nothing after them. Slots are numbered top-down; placeholders go in bottom-up so line numbers stay valid.
    if fill_dangling:
        dangling = _dangling(lines)[: max(0, MAX_EXTRA_SLOTS - len(added))]
        inserts: list[tuple[int, str]] = []
        for block in dangling:
            above, below = _previous_prose(lines, block.start), _next_prose(lines, block.end)
            purpose = _last_sentence(block.text)
            brief = (
                f"Show exactly what this sentence promises, with the real content the post describes: {block.text}"
                + (f"\nText just before it: {above}" if above else "")
                + (f"\nText right after it: {below}" if below else "")
            )
            inserts.append((block.end, new_slot(_kind_for(purpose), purpose, brief, block.end)))
        for end, slot_id in reversed(inserts):
            lines[end + 1 : end + 1] = ["", f"{{{{image:{slot_id}}}}}"]

    if not added:
        return markdown, slots
    text = "\n".join(lines)
    order = {slot_id: i for i, slot_id in enumerate(PLACEHOLDER_RE.findall(text))}
    middle = [s for s in [*slots, *added] if s.kind not in ("hero", "meme")]
    middle.sort(key=lambda s: order.get(s.slot_id, len(order)))
    hero = [s for s in slots if s.kind == "hero"]
    meme = [s for s in slots if s.kind == "meme"]
    return text, [*hero, *middle, *meme]


async def fill_missing_examples(*, engine: Engine, images: ImageService, project_id: int, ctx: Reporter) -> dict[str, Any]:
    """Fix a post written before lead-ins were checked: draw an image for every example it introduces but lacks.

    The text only gains placeholder lines (the old text is kept in the history); existing images are untouched.
    """
    with Session(engine, expire_on_commit=False) as session:
        project = session.get(Project, project_id)
        if project is None:
            raise ValueError("Project not found.")
        persona = session.get(Persona, project.persona_id)
        voice_profile = current_voice_profile(session, project.persona_id)
        rows = list(session.exec(select(ProjectImage).where(ProjectImage.project_id == project_id).order_by(col(ProjectImage.position))))
    if persona is None:
        raise ValueError("The project's persona no longer exists.")
    slots = [
        ImageSlot(slot_id=r.slot_id, kind=r.kind, section_index=0, purpose=r.purpose or "", brief=r.prompt or r.purpose or "")  # type: ignore[arg-type]
        for r in rows
    ]
    await ctx.progress(0.05, "Looking for examples the post introduces but does not show")
    markdown, new_slots = add_example_slots(project.markdown, slots)
    added = [s for s in new_slots if s.slot_id not in {r.slot_id for r in rows}]
    if not added:
        await ctx.progress(1.0, "Every example in this post is already there")
        return {"project_id": project_id, "added": []}

    order = {slot.slot_id: i for i, slot in enumerate(new_slots)}
    with Session(engine) as session:
        row = session.get(Project, project_id)
        assert row is not None
        push_revision(row, "Before adding missing examples", "edit")
        row.markdown = markdown
        plan = dict(row.plan or {})
        plan["image_slots"] = [s.model_dump() for s in new_slots]
        row.plan = plan
        row.updated_at = utcnow()
        session.add(row)
        for image in session.exec(select(ProjectImage).where(ProjectImage.project_id == project_id)):
            image.position = order.get(image.slot_id, len(order))
            session.add(image)
        fresh = [
            ProjectImage(
                project_id=project_id, slot_id=s.slot_id, position=order[s.slot_id], kind=s.kind, purpose=s.purpose, prompt=s.brief
            )
            for s in added
        ]
        session.add_all(fresh)
        session.commit()
        image_ids = [i.id for i in fresh if i.id is not None]
    await ctx.emit("draft_reset", {})
    await ctx.emit("draft_delta", {"text": markdown})

    done = 0

    async def draw(image_id: int) -> None:
        nonlocal done
        await images.create(
            image_id,
            persona=persona,
            title=project.title,
            markdown=markdown,
            voice_profile=voice_profile.markdown if voice_profile else "",
            brand_kit=project.brand_kit,
            usage=ctx.add_usage,
        )
        done += 1
        await ctx.emit("image_ready", {"image_id": image_id})
        await ctx.progress(0.1 + 0.9 * done / len(image_ids), f"Drew {done} of {len(image_ids)} missing examples")

    await ctx.progress(0.1, f"Drawing {len(image_ids)} missing examples")
    semaphore = asyncio.Semaphore(3)

    async def limited(image_id: int) -> None:
        async with semaphore:
            await draw(image_id)

    await asyncio.gather(*(limited(i) for i in image_ids))
    return {"project_id": project_id, "added": [s.slot_id for s in added]}
