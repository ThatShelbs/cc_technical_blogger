"""Structured outputs Claude returns when designing each image."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SvgSpec(BaseModel):
    svg: str = Field(description="A complete, self-contained <svg> document with a viewBox.")
    alt: str = Field(description="Alt text describing the image for screen readers.")
    caption: str = Field(description="Caption in the author's style, without the credit.")


class SvgMemeSpec(SvgSpec):
    top_text: str = Field(description="Short top caption (or empty).")
    bottom_text: str = Field(description="Punchline bottom caption.")


class ChartSpec(BaseModel):
    vega_lite_json: str = Field(description="A complete Vega-Lite v5 spec as a JSON string with inline data values.")
    alt: str
    caption: str
    data_is_illustrative: bool = Field(description="True when the values are illustrative rather than real data.")
