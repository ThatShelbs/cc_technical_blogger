from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Protocol

from PIL import Image


class ImageProviderError(RuntimeError):
    pass


class ImageProviderNotConfiguredError(ImageProviderError):
    pass


@dataclass
class RenderedImage:
    png: bytes
    width: int
    height: int
    provider: str
    seed: int | None = None


class RasterProvider(Protocol):
    """Text-to-image model used for hero, illustration and meme images."""

    name: str
    label: str

    def is_configured(self) -> bool: ...

    async def generate(self, prompt: str, *, width: int, height: int, seed: int) -> RenderedImage: ...


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
