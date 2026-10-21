"""Structured outputs Claude returns when designing each image."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RasterSpec(BaseModel):
    prompt: str = Field(description="Detailed text-to-image prompt. No words, letters or logos in the image.")
    alt: str = Field(description="Alt text describing the image for screen readers.")
    caption: str = Field(description="Caption in the author's style, without the credit.")


class MemeSpec(RasterSpec):
    top_text: str = Field(description="Short top caption (or empty).")
    bottom_text: str = Field(description="Punchline bottom caption.")


class SvgSpec(BaseModel):
    svg: str = Field(description="A complete, self-contained <svg> document with a viewBox.")
    alt: str
    caption: str


class ChartSpec(BaseModel):
    vega_lite_json: str = Field(description="A complete Vega-Lite v5 spec as a JSON string with inline data values.")
    alt: str
    caption: str
    data_is_illustrative: bool = Field(description="True when the values are illustrative rather than real data.")
