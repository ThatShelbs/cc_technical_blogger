"""Read a person's writing (Word, PDF, Markdown, HTML, URLs), clean it up and measure its style."""

from inferno_ghostwriter.ingest.document import Block, ParsedDocument, count_words
from inferno_ghostwriter.ingest.parsers import (
    SUPPORTED_EXTENSIONS,
    UnsupportedFormatError,
    fetch_url,
    parse_file,
    parse_markdown,
)

__all__ = [
    "SUPPORTED_EXTENSIONS",
    "Block",
    "ParsedDocument",
    "UnsupportedFormatError",
    "count_words",
    "fetch_url",
    "parse_file",
    "parse_markdown",
]
