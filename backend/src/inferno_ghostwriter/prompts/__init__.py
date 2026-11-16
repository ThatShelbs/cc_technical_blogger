"""Prompt templates live next to this file as Markdown so they are easy to read and tune.

Templates use ``$name`` placeholders (``string.Template``) so JSON and code
examples inside prompts never need escaping.
"""

from __future__ import annotations

from functools import cache
from importlib import resources
from string import Template


@cache
def _load(name: str) -> str:
    return resources.files(__package__).joinpath(f"{name}.md").read_text(encoding="utf-8")


def render(name: str, **values: object) -> str:
    return Template(_load(name)).substitute({k: str(v) for k, v in values.items()})


def raw(name: str) -> str:
    return _load(name)
