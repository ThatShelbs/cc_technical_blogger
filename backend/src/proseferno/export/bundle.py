"""Platform-optimized export bundles (zip) and copy-ready HTML."""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from typing import Literal

from PIL import Image

from proseferno.db import Project, ProjectImage
from proseferno.export.render import (
    Figure,
    body_html,
    data_uri,
    figures_for,
    markdown_with_images,
    standalone_html,
    strip_title,
)
from proseferno.storage import slugify
from proseferno.writer import split_title

Platform = Literal["medium", "substack", "gumroad", "markdown"]
PLATFORMS: tuple[Platform, ...] = ("medium", "substack", "gumroad", "markdown")

# Thumbnail sizes: Medium and Substack crop previews from a wide image; 1200x630 is the
# common social-card size and suits Gumroad covers too.
THUMBNAIL_SIZE = {"medium": (1400, 788), "substack": (1200, 630), "gumroad": (1280, 720), "markdown": (1000, 420)}

INSTRUCTIONS = {
    "medium": """Publishing on Medium
====================
1. In Proseferno's export dialog, click "Copy for Medium" and paste into a new Medium story
   (images are embedded in the copied content). If any image does not come through, drag it in
   from the images/ folder and paste its caption from post.md.
2. Medium uses the first image as the story preview; thumbnail.png is sized for that.
3. Headings are mapped to Medium's two heading sizes (large = section, small = subsection).
4. Add up to five tags: {tags}
""",
    "substack": """Publishing on Substack
======================
1. Paste the title and subtitle below into Substack's Title and Subtitle fields.
   Title: {title}
   Subtitle: {subtitle}
2. In Proseferno's export dialog, click "Copy for Substack" and paste into the post body.
   If an image does not come through, upload it from images/ and add its caption from post.md.
3. Set thumbnail.png as the post's social preview image in Settings > Social preview.
""",
    "gumroad": """Publishing on Gumroad
=====================
post.pdf is a print-ready version of the post for a Gumroad product or post attachment.
post.html is a styled web version; cover.png (thumbnail.png) works as the product cover.
""",
    "markdown": """Markdown export
===============
post.md has front matter for dev.to, Hashnode, Ghost or a static site, with images in images/.
post.docx is a Word version for editors who prefer Word or Google Docs.
""",
}


def copy_html(project: Project, images: list[ProjectImage], image_dir: Path, platform: Platform) -> str:
    """HTML for the clipboard: images embedded as data URIs so a paste carries them."""
    figures = figures_for(images, image_dir)
    if platform == "medium":
        # Medium: title h1, subtitle h2, sections h3 (large heading), subsections h4 (small heading).
        return body_html(project.markdown, figures, src=data_uri, heading_shift=1)
    if platform == "substack":
        return body_html(strip_title(project.markdown), figures, src=data_uri, include_title=True)
    return body_html(project.markdown, figures, src=data_uri)


def build_bundle(project: Project, images: list[ProjectImage], image_dir: Path, platform: Platform) -> tuple[str, bytes]:
    figures = figures_for(images, image_dir)
    title, subtitle = split_title(project.markdown)
    title = title or project.title or "Untitled post"
    subtitle = subtitle or project.subtitle
    tags = ", ".join((project.plan or {}).get("tags", [])[:5]) or "(choose your own)"
    slug = slugify(title)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for fig in figures.values():
            if fig.path is not None and fig.path.exists():
                zf.write(fig.path, f"images/{fig.file_name}")
        hero = figures.get("hero")
        if hero is not None and hero.path is not None and hero.path.exists():
            zf.writestr("thumbnail.png", _thumbnail(hero.path, THUMBNAIL_SIZE[platform]))

        relative = lambda f: f"images/{f.file_name}"  # noqa: E731
        if platform == "medium":
            body = body_html(project.markdown, figures, src=relative, heading_shift=1)
        else:
            body = body_html(project.markdown, figures, src=relative)
        zf.writestr("post.html", standalone_html(title, body))

        md = markdown_with_images(project.markdown, figures)
        if platform == "markdown":
            md = _front_matter(title, subtitle, (project.plan or {}).get("tags", []), figures) + strip_title(md)
            zf.writestr("post.docx", _docx(project.markdown, figures, title, subtitle))
        zf.writestr("post.md", md)

        if platform == "gumroad":
            zf.writestr("post.pdf", _pdf(title, body_html(project.markdown, figures, src=lambda f: f.file_name or ""), image_dir))

        zf.writestr("README.txt", INSTRUCTIONS[platform].format(title=title, subtitle=subtitle, tags=tags))
    return f"{slug}-{platform}.zip", buffer.getvalue()


def _thumbnail(path: Path, size: tuple[int, int]) -> bytes:
    with Image.open(path) as source:
        img = source.convert("RGB")
        target_w, target_h = size
        scale = max(target_w / img.width, target_h / img.height)
        resized = img.resize((round(img.width * scale), round(img.height * scale)), Image.Resampling.LANCZOS)
        left = (resized.width - target_w) // 2
        top = (resized.height - target_h) // 2
        out = io.BytesIO()
        resized.crop((left, top, left + target_w, top + target_h)).save(out, format="PNG")
        return out.getvalue()


def _front_matter(title: str, subtitle: str, tags: list[str], figures: dict[str, Figure]) -> str:
    def q(text: str) -> str:
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'

    lines = ["---", f"title: {q(title)}", f"description: {q(subtitle)}"]
    if tags:
        lines.append("tags: [" + ", ".join(q(re.sub(r"[^a-z0-9]", "", t.lower())) for t in tags[:4]) + "]")
    hero = figures.get("hero")
    if hero is not None and hero.file_name:
        lines.append(f"cover_image: images/{hero.file_name}")
    lines += ["published: false", "---", "", f"*{subtitle}*" if subtitle else "", ""]
    return "\n".join(lines)


def _pdf(title: str, body: str, image_dir: Path) -> bytes:
    import pymupdf

    css = """
    body { font-family: serif; font-size: 11pt; line-height: 1.5; color: #1b0c41; }
    h1 { font-family: sans-serif; font-size: 24pt; color: #000004; }
    h2 { font-family: sans-serif; font-size: 16pt; color: #4a0c6b; }
    h3 { font-family: sans-serif; font-size: 13pt; color: #4a0c6b; }
    .subtitle { color: #781c6d; font-size: 13pt; }
    figcaption { font-family: sans-serif; font-size: 9pt; color: #5b4a6b; text-align: center; }
    pre { font-family: monospace; font-size: 9pt; background-color: #f4effa; padding: 6pt; }
    blockquote { color: #4a0c6b; }
    """
    # Images: scale to the text width.
    body = re.sub(r'width="\d+" height="\d+"', 'width="468"', body)
    out = io.BytesIO()
    story = pymupdf.Story(html=f"<body>{body}</body>", user_css=css, archive=pymupdf.Archive(str(image_dir)))
    writer = pymupdf.DocumentWriter(out)
    mediabox = pymupdf.paper_rect("letter")
    where = mediabox + (72, 72, -72, -72)  # noqa: RUF005 - pymupdf Rect arithmetic (margins), not tuple concat
    more = True
    while more:
        device = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(device)
        writer.end_page()
    writer.close()
    data = out.getvalue()
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        doc.set_metadata({"title": title, "creator": "Proseferno"})
        return doc.tobytes()


def _docx(markdown: str, figures: dict[str, Figure], title: str, subtitle: str) -> bytes:
    from docx import Document
    from docx.shared import Inches, Pt
    from markdown_it import MarkdownIt

    from proseferno.images import PLACEHOLDER_RE

    document = Document()
    document.add_heading(title, level=0)
    if subtitle:
        document.add_paragraph().add_run(subtitle).italic = True

    tokens = MarkdownIt("commonmark").parse(strip_title(markdown))
    list_stack: list[str] = []
    for i, tok in enumerate(tokens):
        if tok.type in ("bullet_list_open", "ordered_list_open"):
            list_stack.append("List Number" if tok.type == "ordered_list_open" else "List Bullet")
        elif tok.type in ("bullet_list_close", "ordered_list_close"):
            list_stack.pop()
        elif tok.type == "heading_open":
            document.add_heading(tokens[i + 1].content, level=min(3, max(1, int(tok.tag[1]) - 1)))
        elif tok.type == "inline" and tokens[i - 1].type == "paragraph_open":
            content = tok.content.strip()
            placeholder = PLACEHOLDER_RE.fullmatch(content)
            if placeholder:
                fig = figures.get(placeholder.group(1))
                if fig is not None and fig.path is not None and fig.path.exists():
                    document.add_picture(str(fig.path), width=Inches(6))
                    if fig.full_caption:
                        cap = document.add_paragraph()
                        run = cap.add_run(fig.full_caption)
                        run.italic = True
                        run.font.size = Pt(9)
                continue
            style = list_stack[-1] if list_stack else None
            document.add_paragraph(_plain(content), style=style)
        elif tok.type in ("fence", "code_block"):
            para = document.add_paragraph()
            run = para.add_run(tok.content.rstrip("\n"))
            run.font.name = "Consolas"
            run.font.size = Pt(9)
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()


def _plain(markdown_inline: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: m.group(1) or m.group(2), markdown_inline)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)|_(.+?)_", lambda m: m.group(1) or m.group(2), text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
