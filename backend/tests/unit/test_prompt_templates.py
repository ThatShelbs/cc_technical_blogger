"""Prompt templates and the code that fills them must agree (a missing value is a KeyError at draw time)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import inferno_ghostwriter
from inferno_ghostwriter.prompts import raw

SRC = Path(inferno_ghostwriter.__file__).parent


def _render_calls() -> list[tuple[str, set[str], str]]:
    """(template, keyword names, file) for every ``render("name", k=...)`` call that passes no ``**kwargs``."""
    found = []
    for path in SRC.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "render"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
                and all(k.arg is not None for k in node.keywords)
            ):
                found.append((node.args[0].value, {k.arg for k in node.keywords if k.arg}, path.name))
    return found


def test_every_render_call_supplies_its_templates_placeholders() -> None:
    calls = _render_calls()
    assert calls
    for name, given, where in calls:
        needed = set(re.findall(r"(?<!\$)\$([A-Za-z_][A-Za-z0-9_]*)", raw(name)))
        assert needed <= given, f"{where}: render({name!r}) is missing {sorted(needed - given)}"
