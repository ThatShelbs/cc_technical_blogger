"""References: real sources, quotes, social posts, resources and related articles worked into a finished post.

A later pass, like the images: once the text is final, Claude plans where references would strengthen it,
researches each one on the web, and weaves them in with small find/replace edits in the author's voice.
Nothing is invented: every URL must come from the search's citations and every quote must appear word for
word in the research, or that one reference fails (with a Redraw button) and the post goes on without it.

The post stays plain Markdown. Each ``ProjectReference`` row remembers the text it replaced (``original``)
and the text it put there (``inserted``), so one reference can be redrawn, reverted or removed on its own.
"""

from __future__ import annotations

import asyncio
import logging
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import Engine
from sqlmodel import Session, col, delete, select

from proseferno.config import Settings
from proseferno.db import Persona, Project, ProjectReference, Sample, utcnow
from proseferno.jobs import JobContext
from proseferno.llm import LLM, LLMError, ResearchResult, SystemBlock
from proseferno.prompts import raw, render
from proseferno.voice import current_voice_profile, format_exemplars, select_exemplars
from proseferno.voice.lessons import format_lessons
from proseferno.writer.dials import REFERENCE_KINDS, Dials, ResolvedDials, auto_reference_count, resolve
from proseferno.writer.links import LinkChecker
from proseferno.writer.pipeline import Reporter, WriterError, measure, split_title, writer_system
from proseferno.writer.revisions import push_revision
from proseferno.writer.schemas import ReferenceEdit, ReferenceEdits, ReferencePlan
from proseferno.writer.tweak import finish_text, locate

log = logging.getLogger(__name__)

KIND_LABEL = {
    "source": "source",
    "quote": "quote",
    "social_post": "social post",
    "resource": "resource",
    "related_article": "related article",
}
KIND_WANT = {
    "source": "a reputable source (a paper, official documentation, a well-known report, book or benchmark) that backs up "
    "this claim or explains this concept",
    "quote": "a famous, verifiable quote that sharpens this point, preferably from a well-known figure in statistics, causal inference, "
    "AI/ML research or the technology industry, with who said it",
    "social_post": "a widely shared public post (X/Twitter, Bluesky, Threads, LinkedIn or Mastodon) by a recognized AI/ML voice that makes "
    "or illustrates this point: the post's own URL, the author and handle, and the exact words",
    "resource": "a hands-on resource the reader can use next: a tutorial, a Python package (its docs, PyPI or repository page) or a "
    "YouTube video",
    "related_article": "a closely related article or blog post the reader would enjoy next",
}
# Placements each kind may use; the first is the fallback.
PLACEMENTS = {
    "source": ("inline",),
    "quote": ("blockquote", "inline"),
    "social_post": ("blockquote", "inline"),
    "resource": ("go_deeper", "inline"),
    "related_article": ("go_deeper", "inline"),
}
MAX_GO_DEEPER = 3
DEFAULT_GO_DEEPER_HEADING = "Go deeper"
STALE_PENDING = "Stopped before this reference was found. Click Redraw to try again."

LINK_RE = re.compile(r"\]\((https?://[^)\s]+)\)")
_QUOTED_RE = re.compile(r"[\"“]([^\"”]{8,})[\"”]")
_QUOTE_CHARS = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'", "—": "-", "–": "-"})


@dataclass
class PlannedReference:
    slot_id: str
    kind: str
    placement: str
    # Exact text from the post for inline and blockquote; empty for go_deeper.
    anchor: str
    purpose: str
    query: str


@dataclass
class WovenReference:
    planned: PlannedReference
    status: str = "pending"
    error: str | None = None
    url: str = ""
    title: str = ""
    speaker: str = ""
    quote: str = ""
    original: str = ""
    inserted: str = ""
    heading: str = ""
    tried: list[str] = field(default_factory=list)


# -- text helpers ------------------------------------------------------------------------


def norm_url(url: str) -> str:
    parts = urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix("www.")
    return urlunsplit((parts.scheme.lower(), host, parts.path.rstrip("/"), parts.query, ""))


def _norm_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text.translate(_QUOTE_CHARS)).strip().lower()
    return text.strip(" \"'.,;:!?-")


def links_in(text: str) -> list[str]:
    return LINK_RE.findall(text)


def research_block(result: ResearchResult) -> str:
    sources = "\n".join(f"- [{c.title or c.url}]({c.url})" for c in result.citations)
    return f"<research>\n{result.text.strip()}\n\nSources:\n{sources}\n</research>"


def quote_in_research(quote: str, result: ResearchResult) -> bool:
    """The quote's words (ignoring case, curly quotes and spacing) appear in the research or a cited passage."""
    needle = _norm_text(quote)
    if len(needle) < 4:
        return False
    haystack = _norm_text(" ".join([result.text, *(c.cited_text for c in result.citations)]))
    return needle in haystack


def _paragraph_bounds(markdown: str, start: int, end: int) -> tuple[int, int]:
    before = markdown.rfind("\n\n", 0, start)
    after = markdown.find("\n\n", end)
    return (0 if before < 0 else before + 2), (len(markdown) if after < 0 else after)


def _blocked_lines(markdown: str) -> set[int]:
    """Line numbers no reference may anchor in: the title block, headings, code, image placeholders."""
    blocked: set[int] = set()
    in_code = False
    seen_title = False
    for i, line in enumerate(markdown.split("\n")):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            blocked.add(i)
            continue
        if in_code or stripped.startswith(("#", "{{", "|")):
            blocked.add(i)
        if stripped.startswith("# "):
            seen_title = True
        elif seen_title and i < 6 and stripped.startswith(("*", "_")) and stripped.endswith(("*", "_")):
            blocked.add(i)  # the subtitle
    return blocked


def _line_of(markdown: str, index: int) -> int:
    return markdown.count("\n", 0, index)


# -- planning ----------------------------------------------------------------------------


def plan_references(
    plan: ReferencePlan, markdown: str, *, count: int, kinds: list[str], start_index: int = 1, taken: list[str] | None = None
) -> list[PlannedReference]:
    """Keep the plan's slots that can really be placed: allowed kinds, a varied mix, one per paragraph, real anchors."""
    allowed = [k for k in kinds if k in REFERENCE_KINDS]
    if count <= 0 or not allowed:
        return []
    per_kind_cap = max(2, math.ceil(count / len(allowed)))
    blocked = _blocked_lines(markdown)
    used_paragraphs: set[int] = set()
    for text in taken or []:
        span = locate(markdown, text)
        if span:
            used_paragraphs.add(_paragraph_bounds(markdown, *span)[0])
    per_kind: Counter[str] = Counter()
    go_deeper = 0
    out: list[PlannedReference] = []
    for slot in plan.slots:
        if len(out) >= count:
            break
        kind = slot.kind
        if kind not in allowed or per_kind[kind] >= per_kind_cap:
            continue
        placement = slot.placement if slot.placement in PLACEMENTS[kind] else PLACEMENTS[kind][0]
        anchor = ""
        if placement != "go_deeper":
            span = locate(markdown, slot.anchor)
            ok = span is not None
            if span is not None:
                lines = range(_line_of(markdown, span[0]), _line_of(markdown, span[1]) + 1)
                paragraph = _paragraph_bounds(markdown, *span)
                ok = not any(line in blocked for line in lines) and paragraph[0] not in used_paragraphs
            if span is None or not ok:
                if "go_deeper" not in PLACEMENTS[kind]:
                    continue
                placement = "go_deeper"
            else:
                start, end = span
                paragraph = _paragraph_bounds(markdown, start, end)
                used_paragraphs.add(paragraph[0])
                # A blockquote goes after the anchor's paragraph, so the anchor runs to the paragraph's end.
                anchor = markdown[start : paragraph[1]] if placement == "blockquote" else markdown[start:end]
        if placement == "go_deeper":
            if go_deeper >= MAX_GO_DEEPER:
                continue
            go_deeper += 1
        per_kind[kind] += 1
        out.append(
            PlannedReference(
                slot_id=f"r{start_index + len(out)}",
                kind=kind,
                placement=placement,
                anchor=anchor,
                purpose=slot.purpose.strip(),
                query=slot.query.strip(),
            )
        )
    return out


def _existing_text(rows: list[ProjectReference]) -> str:
    if not rows:
        return ""
    lines = "\n".join(f"- {KIND_LABEL.get(r.kind, r.kind)}: {r.title or r.url} ({r.url})" for r in rows)
    return f"\nAlready in the post (do not repeat these, and anchor nothing in the sentences that cite them):\n{lines}\n"


# -- research ----------------------------------------------------------------------------


async def research_reference(
    *,
    llm: LLM,
    settings: Settings,
    links: LinkChecker,
    planned: PlannedReference,
    title: str,
    avoid: list[str],
    usage: Any = None,
) -> ResearchResult:
    """Web research for one reference; citations already tried, or whose page is gone, are dropped."""
    avoid = list(avoid)
    result = ResearchResult(text="", citations=[])
    for _ in range(2):
        result = await llm.research(
            system=[SystemBlock(raw("reference_research_system"))],
            prompt=render(
                "reference_research",
                want=KIND_WANT[planned.kind],
                kind=planned.kind,
                title=title,
                purpose=planned.purpose or "(not given)",
                query=planned.query or "(your choice)",
                passage=planned.anchor or "(the end of the post: something for the reader to explore next)",
                avoid=", ".join(avoid) or "(none)",
            ),
            effort=settings.effort_references,
            max_searches=max(1, settings.reference_max_searches),
            usage=usage,
        )
        skip = {norm_url(u) for u in avoid}
        citations = [c for c in result.citations if norm_url(c.url) not in skip]
        dead = await links.dead([c.url for c in citations]) if citations and settings.check_reference_links else set()
        live = [c for c in citations if c.url not in dead]
        result = ResearchResult(text=result.text, citations=live)
        if live or not dead:
            break
        # Every link it found is gone: one more search that avoids them.
        avoid.extend(dead)
    return result


# -- weaving -----------------------------------------------------------------------------


def _slot_block(planned: PlannedReference, research: ResearchResult) -> str:
    return (
        f'<slot id="{planned.slot_id}" kind="{planned.kind}" placement="{planned.placement}">\n'
        f"Anchor: {planned.anchor or '(none: go_deeper)'}\n"
        f"Purpose: {planned.purpose or '(not given)'}\n"
        f"{research_block(research)}\n</slot>"
    )


async def weave(
    *,
    llm: LLM,
    settings: Settings,
    system: list[SystemBlock],
    markdown: str,
    dials: ResolvedDials,
    slots: list[tuple[PlannedReference, ResearchResult]],
    usage: Any = None,
) -> ReferenceEdits:
    return await llm.structured(
        task="reference weave",
        system=system,
        prompt=render(
            "reference_weave",
            platform=dials.platform,
            platform_guide=dials.platform_guide,
            slots="\n\n".join(_slot_block(p, r) for p, r in slots),
            markdown=markdown,
        ),
        schema=ReferenceEdits,
        effort=settings.effort_references,
        max_tokens=32000,
        usage=usage,
    )


def check_edit(planned: PlannedReference, edit: ReferenceEdit, research: ResearchResult) -> tuple[str | None, dict[str, str]]:
    """Validate one woven reference against its research. Returns (error, cleaned fields)."""
    label = KIND_LABEL.get(planned.kind, "reference")
    replace = re.sub(r"\n{3,}", "\n\n", edit.replace.strip())
    if not replace:
        return f"Couldn't find a verifiable {label} for this spot. Click Redraw to try again.", {}
    if planned.placement == "go_deeper":
        replace = "- " + " ".join(replace.split()).lstrip("-*• ").strip()
    elif len(replace) > len(planned.anchor) + 900:
        return f"The {label} changed too much of the post, so it was left out. Click Redraw to try again.", {}
    before = {norm_url(u) for u in links_in(planned.anchor)}
    new_urls = [u for u in links_in(replace) if norm_url(u) not in before]
    if not new_urls:
        return f"Claude didn't link the {label}, so it was left out. Click Redraw to try again.", {}
    allowed = {norm_url(c.url): c for c in research.citations}
    if any(norm_url(u) not in allowed for u in new_urls):
        return f"Claude linked a page the search didn't find, so the {label} was left out. Click Redraw to try again.", {}
    url = next((u for u in new_urls if norm_url(u) == norm_url(edit.url)), new_urls[0])
    quote = edit.quote.strip().strip('"“”')
    if not quote and planned.kind == "quote":
        match = _QUOTED_RE.search(replace)
        quote = match.group(1) if match else ""
    if planned.kind == "quote" and not quote:
        return "Claude didn't quote anyone, so the quote was left out. Click Redraw to try again.", {}
    if quote and not quote_in_research(quote, research):
        return f"Couldn't verify the exact words of that {label}, so it was left out. Click Redraw to try again.", {}
    if quote and _norm_text(quote) not in _norm_text(replace):
        return f"The {label} in the post doesn't match the words found, so it was left out. Click Redraw to try again.", {}
    citation = allowed[norm_url(url)]
    title = edit.title.strip() or citation.title or url
    return None, {"replace": replace, "url": url, "title": title[:300], "speaker": edit.speaker.strip()[:200], "quote": quote}


def add_go_deeper(markdown: str, heading: str, line: str) -> str:
    """Add one line to the post's "Go deeper" list, creating the list before the closing meme if needed."""
    lines = markdown.rstrip("\n").split("\n")
    heading_line = f"## {heading}"
    if heading_line in lines:
        i = lines.index(heading_line) + 1
        while i < len(lines) and not lines[i].strip():
            i += 1
        while i < len(lines) and lines[i].startswith("- "):
            i += 1
        if i > 0 and not lines[i - 1].startswith("- "):
            lines[i:i] = [line, ""]
        else:
            lines[i:i] = [line]
    else:
        meme = next((i for i, text in enumerate(lines) if text.strip() == "{{image:meme}}"), len(lines))
        lines[meme:meme] = ["", heading_line, "", line, ""]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip() + "\n"


def remove_go_deeper(markdown: str, heading: str, line: str) -> str:
    lines = markdown.rstrip("\n").split("\n")
    if line in lines:
        lines.remove(line)
    heading_line = f"## {heading}"
    if heading_line in lines:
        i = lines.index(heading_line) + 1
        while i < len(lines) and not lines[i].strip():
            i += 1
        if i >= len(lines) or not lines[i].startswith("- "):
            lines.remove(heading_line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip() + "\n"


def in_post(row: ProjectReference, markdown: str) -> bool:
    if not row.inserted:
        return False
    if row.placement == "go_deeper":
        return row.inserted in markdown.split("\n")
    return row.inserted in markdown


def place(markdown: str, woven: WovenReference, replace: str, heading: str) -> tuple[str, str] | None:
    """Put one checked reference into the post. Returns (markdown, original text) or None if its anchor is gone."""
    if woven.planned.placement == "go_deeper":
        return add_go_deeper(markdown, heading, replace), ""
    span = locate(markdown, woven.planned.anchor)
    if span is None:
        return None
    start, end = span
    return markdown[:start] + replace + markdown[end:], markdown[start:end]


def _history_entry(ref: WovenReference | ProjectReference) -> dict[str, Any]:
    kind = ref.planned.kind if isinstance(ref, WovenReference) else ref.kind
    return {
        "kind": kind,
        "url": ref.url,
        "title": ref.title,
        "speaker": ref.speaker,
        "quote": ref.quote,
        "inserted": ref.inserted,
        "created_at": utcnow().isoformat(),
    }


async def weave_references(
    *,
    llm: LLM,
    settings: Settings,
    links: LinkChecker,
    system: list[SystemBlock],
    markdown: str,
    title: str,
    dials: ResolvedDials,
    image_plan: dict[str, Any] | None,
    reporter: Reporter,
    count: int,
    kinds: list[str],
    existing: list[ProjectReference] | None = None,
    start_index: int = 1,
    progress: tuple[float, float] = (0.62, 0.68),
) -> tuple[str, list[WovenReference]]:
    """Plan, research and weave ``count`` new references into ``markdown``. Never raises for one bad reference."""
    existing = existing or []
    if count <= 0 or not kinds:
        return markdown, []
    lo, hi = progress
    await reporter.progress(lo, "Finding sources, quotes and resources to back up the post")
    plan = await llm.structured(
        task="reference plan",
        system=system,
        prompt=render(
            "reference_plan",
            count=count,
            kinds=", ".join(kinds),
            existing=_existing_text(existing),
            topic=dials.topic,
            audience=dials.audience or "the author's usual readers",
            education=dials.education,
            platform=dials.platform,
            markdown=markdown,
        ),
        schema=ReferencePlan,
        effort=settings.effort_references,
        usage=reporter.add_usage,
    )
    planned = plan_references(
        plan, markdown, count=count, kinds=kinds, start_index=start_index, taken=[r.inserted for r in existing if r.inserted]
    )
    if not planned:
        return markdown, []
    woven = [WovenReference(planned=p) for p in planned]
    avoid = [r.url for r in existing if r.url]

    semaphore = asyncio.Semaphore(3)
    done = 0
    researched: dict[str, ResearchResult] = {}

    async def look_up(ref: WovenReference) -> None:
        nonlocal done
        label = KIND_LABEL[ref.planned.kind]
        try:
            async with semaphore:
                result = await research_reference(
                    llm=llm, settings=settings, links=links, planned=ref.planned, title=title, avoid=avoid, usage=reporter.add_usage
                )
        except LLMError as exc:
            ref.status, ref.error = "error", f"The search for a {label} failed ({exc}). Click Redraw to try again."
            result = None
        except Exception as exc:  # one reference must never fail the post
            log.exception("Reference research failed")
            ref.status, ref.error = "error", f"The search for a {label} failed ({type(exc).__name__}). Click Redraw to try again."
            result = None
        if result is not None:
            ref.tried = [c.url for c in result.citations]
            if result.citations:
                researched[ref.planned.slot_id] = result
            else:
                ref.status, ref.error = "error", f"Couldn't find a verifiable {label} for this spot. Click Redraw to try again."
        done += 1
        await reporter.progress(lo + (hi - lo) * 0.8 * done / len(woven), f"Researched {done} of {len(woven)} references")

    await asyncio.gather(*(look_up(r) for r in woven))

    ready = [r for r in woven if r.planned.slot_id in researched]
    if ready:
        await reporter.progress(lo + (hi - lo) * 0.85, "Working the references into the post")
        try:
            edits = await weave(
                llm=llm,
                settings=settings,
                system=system,
                markdown=markdown,
                dials=dials,
                slots=[(r.planned, researched[r.planned.slot_id]) for r in ready],
                usage=reporter.add_usage,
            )
        except LLMError as exc:
            for ref in ready:
                ref.status, ref.error = "error", f"Couldn't work this reference into the post ({exc}). Click Redraw to try again."
            edits = ReferenceEdits(go_deeper_heading="", edits=[])
            ready = []
        heading = " ".join(edits.go_deeper_heading.split()).strip("# ") or DEFAULT_GO_DEEPER_HEADING
        heading = next((r.anchor for r in existing if r.placement == "go_deeper" and r.anchor), heading)
        by_slot = {e.slot: e for e in edits.edits}
        for ref in ready:
            edit = by_slot.get(ref.planned.slot_id)
            label = KIND_LABEL[ref.planned.kind]
            if edit is None:
                ref.status, ref.error = "error", f"Claude didn't work the {label} in. Click Redraw to try again."
                continue
            error, fields = check_edit(ref.planned, edit, researched[ref.planned.slot_id])
            if error:
                ref.status, ref.error = "error", error
                continue
            placed = place(markdown, ref, fields["replace"], heading)
            if placed is None:
                ref.status = "error"
                ref.error = f"The sentence for this {label} changed before it could be placed. Click Redraw to try again."
                continue
            markdown, ref.original = placed
            ref.inserted, ref.url, ref.title, ref.speaker, ref.quote = (
                fields["replace"],
                fields["url"],
                fields["title"],
                fields["speaker"],
                fields["quote"],
            )
            ref.heading = heading if ref.planned.placement == "go_deeper" else ""
            ref.status, ref.error = "ready", None
        markdown = finish_text(markdown, image_plan)
        for ref in ready:
            if ref.status == "ready" and not (
                ref.inserted in markdown.split("\n") if ref.planned.placement == "go_deeper" else ref.inserted in markdown
            ):
                ref.status, ref.error = "error", "This reference was lost while tidying the post. Click Redraw to put it back."
    count_ready = sum(1 for r in woven if r.status == "ready")
    await reporter.emit("references", {"ready": count_ready, "total": len(woven)})
    await reporter.progress(hi, f"Added {count_ready} of {len(woven)} references")
    return markdown, woven


def to_rows(project_id: int, woven: list[WovenReference], *, position: int = 0) -> list[ProjectReference]:
    rows = []
    for i, ref in enumerate(woven):
        p = ref.planned
        rows.append(
            ProjectReference(
                project_id=project_id,
                slot_id=p.slot_id,
                position=position + i,
                kind=p.kind,
                placement=p.placement,
                anchor=ref.heading if p.placement == "go_deeper" else p.anchor,
                purpose=p.purpose,
                query=p.query,
                url=ref.url,
                title=ref.title,
                speaker=ref.speaker,
                quote=ref.quote,
                # Never placed (it failed): the anchor is still the text a redraw works on.
                original=(ref.original or p.anchor) if p.placement != "go_deeper" else "",
                inserted=ref.inserted,
                status=ref.status,
                error=ref.error,
                tried_urls=[*dict.fromkeys([*ref.tried, *([ref.url] if ref.url else [])])],
                history=[_history_entry(ref)] if ref.status == "ready" else [],
            )
        )
    return rows


# -- persistence ---------------------------------------------------------------------------


def project_references(session: Session, project_id: int) -> list[ProjectReference]:
    return list(
        session.exec(select(ProjectReference).where(ProjectReference.project_id == project_id).order_by(col(ProjectReference.position)))
    )


def delete_references(session: Session, project_ids: list[int]) -> None:
    session.exec(delete(ProjectReference).where(col(ProjectReference.project_id).in_(project_ids)))  # type: ignore[call-overload]


def replace_references(engine: Engine, project_id: int, woven: list[WovenReference]) -> None:
    with Session(engine) as session:
        delete_references(session, [project_id])
        session.add_all(to_rows(project_id, woven))
        session.commit()


def fail_pending(engine: Engine) -> int:
    """References still "pending" at startup lost their job in a previous run."""
    with Session(engine) as session:
        rows = list(session.exec(select(ProjectReference).where(ProjectReference.status == "pending")))
        for row in rows:
            row.status, row.error = "error", STALE_PENDING
            session.add(row)
        session.commit()
        return len(rows)


def _slot_number(slot_id: str) -> int:
    match = re.fullmatch(r"r(\d+)", slot_id)
    return int(match.group(1)) if match else 0


@dataclass
class _Context:
    project: Project
    persona: Persona
    system: list[SystemBlock]
    dials: ResolvedDials
    baseline: dict[str, Any]


def _load(engine: Engine, settings: Settings, project_id: int) -> _Context:
    with Session(engine, expire_on_commit=False) as session:
        project = session.get(Project, project_id)
        if project is None:
            raise WriterError("Project not found.")
        persona = session.get(Persona, project.persona_id)
        voice_profile = current_voice_profile(session, project.persona_id)
        samples = list(session.exec(select(Sample).where(Sample.persona_id == project.persona_id)))
    if persona is None:
        raise WriterError("The project's persona no longer exists.")
    if voice_profile is None:
        raise WriterError("This persona has no voice profile yet.")
    if not project.markdown:
        raise WriterError("Generate the post before adding references.")
    system = writer_system(
        voice_profile.markdown, format_exemplars(select_exemplars(project.prompt, samples)), format_lessons(persona.edit_lessons)
    )
    dials = resolve(Dials(**(project.dials or {})), persona, project.prompt, default_revisions=settings.revision_passes)
    return _Context(project, persona, system, dials, voice_profile.baseline_stylometrics)


def _save_text(session: Session, project: Project, markdown: str, label: str, baseline: dict[str, Any]) -> None:
    push_revision(project, label, "reference")
    project.markdown = markdown
    title, subtitle = split_title(markdown)
    project.title, project.subtitle = title or project.title, subtitle or project.subtitle
    project.fidelity = measure(markdown, baseline)
    project.updated_at = utcnow()
    session.add(project)


# -- jobs and actions ------------------------------------------------------------------------


async def enrich_post(
    *,
    engine: Engine,
    llm: LLM,
    settings: Settings,
    links: LinkChecker,
    project_id: int,
    count: int | None,
    kinds: list[str] | None,
    ctx: JobContext,
) -> dict[str, Any]:
    """Add references to an existing post (an older one, or one written with references turned off)."""
    c = _load(engine, settings, project_id)
    with Session(engine) as session:
        rows = project_references(session, project_id)
    present = [r for r in rows if r.status == "ready" and in_post(r, c.project.markdown)]
    if count is None:
        target = c.dials.reference_count or auto_reference_count(c.dials.target_words)
        count = max(1, target - len(present))
    use_kinds: list[str] = [k for k in REFERENCE_KINDS if k in (kinds or c.dials.reference_kinds or REFERENCE_KINDS)]
    markdown, woven = await weave_references(
        llm=llm,
        settings=settings,
        links=links,
        system=c.system,
        markdown=c.project.markdown,
        title=c.project.title,
        dials=c.dials,
        image_plan=c.project.plan,
        reporter=ctx,
        count=count,
        kinds=use_kinds,
        existing=present,
        start_index=max((_slot_number(r.slot_id) for r in rows), default=0) + 1,
        progress=(0.05, 0.95),
    )
    added = sum(1 for r in woven if r.status == "ready")
    with Session(engine) as session:
        project = session.get(Project, project_id)
        if project is None:
            raise WriterError("Project not found.")
        if project.markdown != c.project.markdown:
            raise WriterError("The post changed while references were being added. Try again.")
        if added:
            _save_text(session, project, markdown, f"Added {added} reference{'s' if added != 1 else ''}", c.baseline)
        session.add_all(to_rows(project_id, woven, position=max((r.position for r in rows), default=-1) + 1))
        session.commit()
    if not added:
        raise WriterError("Couldn't find verifiable references for this post. Try again, or pick different kinds.")
    await ctx.progress(1.0, f"Added {added} reference{'s' if added != 1 else ''}")
    return {"project_id": project_id, "added": added}


async def redraw_reference(
    *,
    engine: Engine,
    llm: LLM,
    settings: Settings,
    links: LinkChecker,
    reference_id: int,
    kind: str | None,
    ctx: JobContext,
) -> dict[str, Any]:
    """Find a different reference for the same spot (optionally of another kind) and swap it into the text."""
    with Session(engine, expire_on_commit=False) as session:
        row = session.get(ProjectReference, reference_id)
        if row is None:
            raise WriterError("Reference not found.")
    c = _load(engine, settings, row.project_id)
    markdown = c.project.markdown
    new_kind = kind or row.kind
    if new_kind not in REFERENCE_KINDS:
        raise WriterError(f"Unknown reference kind {new_kind!r}.")
    placement = row.placement
    if placement == "go_deeper" and "go_deeper" not in PLACEMENTS[new_kind]:
        raise WriterError(f"A {KIND_LABEL[new_kind]} needs a sentence to back up, and this reference sits in the list at the end.")
    if placement not in PLACEMENTS[new_kind]:
        placement = "inline"
    present = in_post(row, markdown)
    if placement != "go_deeper" and not present and locate(markdown, row.original) is None:
        raise WriterError("The passage this reference belonged to has changed. Remove it, or add a new reference.")
    label = KIND_LABEL[new_kind]

    planned = PlannedReference(
        slot_id=row.slot_id,
        kind=new_kind,
        placement=placement,
        anchor=row.original if placement != "go_deeper" else "",
        purpose=row.purpose,
        query=row.query if new_kind == row.kind else "",
    )
    # The model sees the post as it was before this reference, so the new one replaces it rather than stacking on it.
    if present and placement != "go_deeper":
        base = markdown.replace(row.inserted, row.original, 1)
    elif present:
        base = remove_go_deeper(markdown, row.anchor, row.inserted)
    else:
        base = markdown

    await ctx.progress(0.1, f"Looking for a different {label}")
    research = await research_reference(
        llm=llm,
        settings=settings,
        links=links,
        planned=planned,
        title=c.project.title,
        avoid=[*row.tried_urls, row.url],
        usage=ctx.add_usage,
    )

    def fail(message: str) -> WriterError:
        with Session(engine) as session:
            fresh = session.get(ProjectReference, reference_id)
            if fresh is not None and fresh.status != "ready":
                fresh.error = message
                session.add(fresh)
                session.commit()
        return WriterError(message)

    if not research.citations:
        raise fail(f"Couldn't find another verifiable {label} for this spot. Try again, or switch the kind.")
    await ctx.progress(0.6, f"Working the new {label} into the post")
    edits = await weave(
        llm=llm, settings=settings, system=c.system, markdown=base, dials=c.dials, slots=[(planned, research)], usage=ctx.add_usage
    )
    edit = next((e for e in edits.edits if e.slot == row.slot_id), edits.edits[0] if edits.edits else None)
    if edit is None:
        raise fail(f"Claude didn't work a new {label} in. Try again.")
    error, fields = check_edit(planned, edit, research)
    if error:
        raise fail(error)

    replace = fields["replace"]
    heading = row.anchor if placement == "go_deeper" and row.anchor else DEFAULT_GO_DEEPER_HEADING
    if present:
        new_markdown = markdown.replace(row.inserted, replace, 1)
        original = row.original
    else:
        woven = WovenReference(planned=planned)
        placed = place(markdown, woven, replace, heading)
        if placed is None:
            raise fail("The passage this reference belonged to has changed. Remove it, or add a new reference.")
        new_markdown, original = placed
    new_markdown = finish_text(new_markdown, c.project.plan)

    with Session(engine) as session:
        project = session.get(Project, row.project_id)
        fresh = session.get(ProjectReference, reference_id)
        if project is None or fresh is None:
            raise WriterError("The post or reference no longer exists.")
        if project.markdown != markdown:
            raise WriterError("The post changed while the reference was being redrawn. Try again.")
        _save_text(session, project, new_markdown, f"Redrew {label}: {fields['title']}", c.baseline)
        fresh.kind, fresh.placement = new_kind, placement
        fresh.url, fresh.title, fresh.speaker, fresh.quote = fields["url"], fields["title"], fields["speaker"], fields["quote"]
        fresh.inserted, fresh.original = replace, original
        if placement == "go_deeper":
            fresh.anchor = heading
        fresh.status, fresh.error = "ready", None
        fresh.tried_urls = [*dict.fromkeys([*fresh.tried_urls, *(c.url for c in research.citations), fields["url"]])]
        fresh.history = [*fresh.history, _history_entry(fresh)]
        session.add(fresh)
        session.commit()
    await ctx.progress(1.0, f"New {label} added")
    return {"reference_id": reference_id, "project_id": row.project_id}


def remove_reference(session: Session, row: ProjectReference, project: Project, baseline: dict[str, Any] | None) -> None:
    """Take a reference out of the post (its sentence goes back to how it read before) and forget it."""
    if in_post(row, project.markdown):
        if row.placement == "go_deeper":
            markdown = remove_go_deeper(project.markdown, row.anchor, row.inserted)
        else:
            markdown = project.markdown.replace(row.inserted, row.original, 1)
        markdown = finish_text(markdown, project.plan)
        _save_text(session, project, markdown, f"Removed {KIND_LABEL.get(row.kind, 'reference')}: {row.title}", baseline or {})
    session.delete(row)


def revert_reference(session: Session, row: ProjectReference, project: Project, index: int, baseline: dict[str, Any] | None) -> None:
    """Swap an earlier version of this reference back into the post."""
    if not 0 <= index < len(row.history):
        raise IndexError(index)
    if not in_post(row, project.markdown):
        raise WriterError("This reference is no longer in the post, so there is nothing to swap. Redraw it instead.")
    entry = row.history[index]
    inserted = str(entry.get("inserted", ""))
    if not inserted:
        raise WriterError("That version has no text to restore.")
    markdown = finish_text(project.markdown.replace(row.inserted, inserted, 1), project.plan)
    _save_text(session, project, markdown, f"Restored reference: {entry.get('title', '')}", baseline or {})
    row.kind = str(entry.get("kind", row.kind))
    row.url, row.title = str(entry.get("url", "")), str(entry.get("title", ""))
    row.speaker, row.quote = str(entry.get("speaker", "")), str(entry.get("quote", ""))
    row.inserted = inserted
    session.add(row)
