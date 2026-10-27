from __future__ import annotations

import io

from PIL import Image


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
