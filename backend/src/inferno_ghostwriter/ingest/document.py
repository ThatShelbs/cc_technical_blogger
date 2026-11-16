"""A format-neutral representation of a parsed writing sample."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

BlockKind = Literal["heading", "paragraph", "list_item", "code", "quote", "image", "caption"]

# Markers that show the model where images and captions sat in the original post.
IMAGE_MARKER = "[IMAGE]"
CAPTION_PREFIX = "[CAPTION] "


@dataclass
class Block:
    kind: BlockKind
    text: str = ""
    level: int = 0
    ordered: bool = False


@dataclass
class ParsedDocument:
    source_type: str
    blocks: list[Block] = field(default_factory=list)
    title: str = ""
    subtitle: str = ""
    author: str = ""

    @property
    def captions(self) -> list[str]:
        return [b.text for b in self.blocks if b.kind == "caption"]

    @property
    def image_count(self) -> int:
        return sum(1 for b in self.blocks if b.kind == "image")

    @property
    def word_count(self) -> int:
        return count_words(" ".join(b.text for b in self.blocks if b.kind != "caption"))

    def to_markdown(self) -> str:
        lines: list[str] = []
        if self.title:
            lines += [f"# {self.title}", ""]
        if self.subtitle:
            lines += [f"*{self.subtitle}*", ""]
        for block in self.blocks:
            match block.kind:
                case "heading":
                    lines += [f"{'#' * max(2, min(block.level or 2, 4))} {block.text}", ""]
                case "list_item":
                    lines.append(f"{'1.' if block.ordered else '-'} {block.text}")
                case "code":
                    lines += ["```", block.text, "```", ""]
                case "quote":
                    lines += [f"> {block.text}", ""]
                case "image":
                    lines += [IMAGE_MARKER, ""]
                case "caption":
                    lines += [f"{CAPTION_PREFIX}{block.text}", ""]
                case _:
                    lines += [block.text, ""]
        text = "\n".join(lines)
        return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’\-]*")


def count_words(text: str) -> int:
    return len(_WORD.findall(text))
