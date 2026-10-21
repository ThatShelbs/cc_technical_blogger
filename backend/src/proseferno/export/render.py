"""Turn a project's Markdown (with ``{{image:slot}}`` placeholders) into publishable HTML/Markdown."""

from __future__ import annotations

import base64
import html
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from markdown_it import MarkdownIt

from proseferno.db import ProjectImage
from proseferno.images import PLACEHOLDER_RE
from proseferno.writer import split_title

_md = MarkdownIt("commonmark", {"html": True, "typographer": False}).enable(["table", "strikethrough"])


@dataclass
class Figure:
    slot_id: str
    file_name: str | None
    path: Path | None
    alt: str
    caption: str
    credit: str
    width: int
    height: int

    @property
    def full_caption(self) -> str:
        """Caption followed by the credit, in the "caption; credit" style of blog captions."""
        caption, credit = self.caption.strip(), self.credit.strip()
        if not credit or credit.lower() in caption.lower():
            return caption
        if not caption:
            return credit
        separator = " " if caption.endswith((".", "!", "?", ";")) else "; "
        return f"{caption}{separator}{credit}"


def figures_for(images: list[ProjectImage], image_dir: Path) -> dict[str, Figure]:
    return {
        img.slot_id: Figure(
            slot_id=img.slot_id,
            file_name=img.file_name,
            path=(image_dir / img.file_name) if img.file_name else None,
            alt=img.alt or img.purpose,
            caption=img.caption,
            credit=img.credit,
            width=img.width,
            height=img.height,
        )
        for img in images
    }


def strip_title(markdown: str) -> str:
    """Remove the leading '# Title' and italic subtitle lines (platforms take them as fields)."""
    lines = markdown.splitlines()
    out: list[str] = []
    skipping = True
    for line in lines:
        stripped = line.strip()
        if skipping and (
            stripped.startswith("# ")
            or not stripped
            or (stripped.startswith("*") and stripped.endswith("*") and len(stripped) > 2 and not stripped.startswith("**"))
        ):
            continue
        skipping = False
        out.append(line)
    return "\n".join(out).strip() + "\n"


def body_html(
    markdown: str,
    figures: dict[str, Figure],
    *,
    src: Callable[[Figure], str],
    heading_shift: int = 0,
    include_title: bool = False,
) -> str:
    """Render the post body to HTML, replacing placeholders with <figure> blocks."""
    title, subtitle = split_title(markdown)
    text = markdown if include_title else strip_title(markdown)

    def figure_html(match: re.Match[str]) -> str:
        fig = figures.get(match.group(1))
        if fig is None or fig.file_name is None:
            return ""
        caption = html.escape(fig.full_caption)
        return (
            f'\n\n<figure><img src="{html.escape(src(fig))}" alt="{html.escape(fig.alt)}"'
            f' width="{fig.width}" height="{fig.height}" />'
            f"{f'<figcaption>{caption}</figcaption>' if caption else ''}</figure>\n\n"
        )

    rendered = _md.render(PLACEHOLDER_RE.sub(figure_html, text))
    if heading_shift:
        rendered = _shift_headings(rendered, heading_shift)
    if include_title:
        return rendered
    head = ""
    if title:
        head += f"<h1>{html.escape(title)}</h1>\n"
    if subtitle:
        head += f"<h2>{html.escape(subtitle)}</h2>\n" if heading_shift else f'<p class="subtitle"><em>{html.escape(subtitle)}</em></p>\n'
    return head + rendered


def _shift_headings(rendered: str, shift: int) -> str:
    def repl(match: re.Match[str]) -> str:
        level = min(6, int(match.group(2)) + shift)
        return f"<{match.group(1)}h{level}"

    return re.sub(r"<(/?)h([1-6])", repl, rendered)


def markdown_with_images(markdown: str, figures: dict[str, Figure], *, prefix: str = "images/") -> str:
    """Markdown with real image links and italic caption lines."""

    def repl(match: re.Match[str]) -> str:
        fig = figures.get(match.group(1))
        if fig is None or fig.file_name is None:
            return ""
        caption = f"\n*{fig.full_caption}*" if fig.full_caption else ""
        return f"![{fig.alt}]({prefix}{fig.file_name}){caption}"

    return PLACEHOLDER_RE.sub(repl, markdown)


def data_uri(fig: Figure) -> str:
    if fig.path is None or not fig.path.exists():
        return ""
    return "data:image/png;base64," + base64.b64encode(fig.path.read_bytes()).decode("ascii")


ARTICLE_CSS = """
body { margin: 0; background: #fffdf5; color: #1b0c41; font-family: Georgia, 'Times New Roman', serif; }
article { max-width: 720px; margin: 48px auto; padding: 0 20px; line-height: 1.7; font-size: 20px; }
h1, h2, h3, h4 { font-family: 'Segoe UI', Helvetica, Arial, sans-serif; line-height: 1.25; color: #000004; }
h1 { font-size: 40px; margin-bottom: 8px; }
.subtitle, article > h2:first-of-type { color: #781c6d; font-weight: 400; font-size: 22px; margin-top: 0; }
figure { margin: 32px 0; }
figure img { width: 100%; height: auto; border-radius: 6px; }
figcaption { font-family: 'Segoe UI', Helvetica, Arial, sans-serif; font-size: 14px; color: #5b4a6b; text-align: center; margin-top: 8px; }
pre { background: #1b0c41; color: #fcffa4; padding: 16px; border-radius: 8px; overflow-x: auto; font-size: 15px; }
code { font-family: Consolas, Menlo, monospace; }
blockquote { border-left: 4px solid #ed6925; margin-left: 0; padding-left: 16px; color: #4a0c6b; }
table { border-collapse: collapse; } td, th { border: 1px solid #e6d8c3; padding: 6px 10px; }
"""


def standalone_html(title: str, body: str) -> str:
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(title)}</title>'
        f"<style>{ARTICLE_CSS}</style></head><body><article>\n{body}\n</article></body></html>\n"
    )
