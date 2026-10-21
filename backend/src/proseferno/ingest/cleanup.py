"""Clean up exported blog posts (Medium exports especially).

Medium exports carry UI chrome ("Press enter or click to view image in full
size", clap counts, "Follow"), have no real heading styles, and put image
credits in the paragraph right after each image. This module removes the
chrome, recovers title/subtitle/headings, and tags captions so the voice
analysis sees the post the way readers did.
"""

from __future__ import annotations

import re

from proseferno.ingest.document import Block, ParsedDocument, count_words

_BOILERPLATE = [
    r"press enter or click to view image in full size",
    r"listen",
    r"share",
    r"follow",
    r"--",
    r"\d+(\.\d+)?k?",
    r"\d+ min read",
    r"sign up to discover.*",
    r"written by .*",
    r"published in .*",
    r"responses? \(\d+\)",
    r"more from .*",
    r"recommended from medium",
    r"see all from .*",
    r"member-only story",
    r"open in app",
    r"help status about careers.*",
]
_BOILERPLATE_RE = re.compile(r"^(?:" + "|".join(_BOILERPLATE) + r")$", re.IGNORECASE)

_CREDIT_RE = re.compile(
    r"\b(source|author|image by|photo by|made with|credit|courtesy|created by|chart by|"
    r"generated (?:with|by)|via|figure|fig\.|screenshot|illustration by|unsplash|pexels)\b",
    re.IGNORECASE,
)
_TERMINAL_PUNCT = (".", "!", ":", ";", ",", "…")
_QUOTE_CHARS = ('"', "'", "“", "”", "‘", "’")


def clean_document(doc: ParsedDocument) -> ParsedDocument:
    blocks = [b for b in doc.blocks if not _is_boilerplate(b)]
    blocks = _merge_code(blocks)
    title, subtitle = doc.title, doc.subtitle
    if not title:
        title, subtitle, blocks = _take_title(blocks, subtitle)
    blocks = _tag_captions(blocks)
    if not any(b.kind == "heading" for b in blocks):
        blocks = _infer_headings(blocks)
    return ParsedDocument(
        source_type=doc.source_type,
        blocks=blocks,
        title=title,
        subtitle=subtitle,
        author=doc.author,
    )


def _is_boilerplate(block: Block) -> bool:
    if block.kind in ("image", "code"):
        return False
    text = block.text.strip()
    return not text or bool(_BOILERPLATE_RE.match(text))


def _merge_code(blocks: list[Block]) -> list[Block]:
    merged: list[Block] = []
    for block in blocks:
        if block.kind == "code" and merged and merged[-1].kind == "code":
            merged[-1] = Block("code", merged[-1].text + "\n" + block.text)
        else:
            merged.append(block)
    return merged


def _take_title(blocks: list[Block], subtitle: str) -> tuple[str, str, list[Block]]:
    rest = list(blocks)
    title = ""
    for i, block in enumerate(rest):
        if block.kind in ("paragraph", "heading") and len(block.text) <= 150:
            title = block.text
            rest = rest[i + 1 :]
            break
        if block.kind != "image":
            break
    if not subtitle and rest and rest[0].kind == "paragraph":
        candidate = rest[0].text
        if len(candidate) <= 200 and count_words(candidate) <= 30:
            subtitle = candidate
            rest = rest[1:]
    return title, subtitle, rest


def _tag_captions(blocks: list[Block]) -> list[Block]:
    out: list[Block] = []
    for i, block in enumerate(blocks):
        after_image = i > 0 and blocks[i - 1].kind == "image"
        if after_image and block.kind == "paragraph" and len(block.text) <= 250 and _CREDIT_RE.search(block.text):
            out.append(Block("caption", block.text))
        else:
            out.append(block)
    return out


def _is_short_line(block: Block) -> bool:
    if block.kind != "paragraph":
        return False
    text = block.text.strip()
    return 0 < count_words(text) <= 12 and len(text) <= 90 and (text[:1].isupper() or text[:1].isdigit())


def _infer_headings(blocks: list[Block]) -> list[Block]:
    """Promote short standalone lines that introduce body text to H2 headings."""
    out = list(blocks)
    for i, block in enumerate(blocks):
        if not _is_short_line(block):
            continue
        text = block.text.strip()
        if text.endswith(_TERMINAL_PUNCT) or text.endswith(_QUOTE_CHARS):
            continue
        nxt = blocks[i + 1] if i + 1 < len(blocks) else None
        prev = blocks[i - 1] if i > 0 else None
        if nxt is None or nxt.kind not in ("paragraph", "list_item", "code", "image"):
            continue
        if prev is not None and out[i - 1].kind == "heading":
            continue
        if text.endswith("?"):
            # A question that sets up an image is a prompt to the reader, not a heading.
            if nxt.kind == "image":
                continue
            # A run of short questions is a list of questions, not a heading.
            neighbours = [n for n in (prev, nxt) if n is not None]
            if any(n.kind == "paragraph" and n.text.strip().endswith("?") and count_words(n.text) <= 20 for n in neighbours):
                continue
        out[i] = Block("heading", text, level=2)
    return out
