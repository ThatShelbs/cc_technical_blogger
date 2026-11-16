from __future__ import annotations

import io
import re
from collections.abc import Awaitable, Callable

from PIL import Image

# Where an image sits in a post's Markdown: ``{{image:slot_id}}`` on its own line.
PLACEHOLDER_RE = re.compile(r"\{\{image:([A-Za-z0-9_\-]+)\}\}")


class ImageProviderError(RuntimeError):
    """An image could not be designed or rendered."""


def to_png(data: bytes) -> tuple[bytes, int, int]:
    """Normalize any image bytes to PNG and return (png, width, height)."""
    with Image.open(io.BytesIO(data)) as img:
        img.load()
        width, height = img.size
        if img.format == "PNG":
            return data, width, height
        out = io.BytesIO()
        img.convert("RGBA" if img.mode in ("RGBA", "LA", "P") else "RGB").save(out, format="PNG")
        return out.getvalue(), width, height


def retry_note(problems: str) -> str:
    """What a second attempt is told about the first (one problem per line)."""
    lines = "\n".join(f"- {line}" for line in problems.splitlines() if line.strip())
    return f"\n\nYour previous attempt had these problems; fix every one:\n{lines}\n"


async def draw_with_retry[D, R](ask: Callable[[str], Awaitable[D]], draw: Callable[[D, bool], R], *, tries: int = 2) -> tuple[D, R]:
    """Ask Claude for a design and draw it. A design that cannot be drawn is asked for again with the problems quoted back.

    ``ask(note)`` returns a design (``note`` is empty on the first try); ``draw(design, last)`` renders it or raises
    :class:`ImageProviderError` naming the problems, one per line. The last failure is raised.
    """
    note = ""
    for attempt in range(tries):
        design = await ask(note)
        try:
            return design, draw(design, attempt == tries - 1)
        except ImageProviderError as exc:
            if attempt == tries - 1:
                raise
            note = retry_note(str(exc))
    raise ImageProviderError("No attempts were made.")  # unreachable: tries >= 1
