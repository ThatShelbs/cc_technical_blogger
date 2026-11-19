"""Free checks on model-drawn SVG, before any model looks at it: the jank a reviewer would otherwise have to catch.

``lint`` parses a drawing, removes what can safely be removed (shapes entirely off the canvas, tiny stray marks far
from everything else) and reports what it cannot fix (too many elements, references to ids that do not exist, text
outside its box or the crop band). The problems go back to Claude through ``draw_with_retry`` like any render error,
so a fix costs one retry instead of a review round. Colors are snapped to the image's scheme (``palettes.snap_tree``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from lxml import etree

from inferno_ghostwriter.images.palettes import snap_tree
from inferno_ghostwriter.images.render import parse_xml

SHAPES = {"rect", "circle", "ellipse", "line", "polyline", "polygon", "path", "text", "use", "image"}
_NUM = re.compile(r"-?\d*\.?\d+(?:e-?\d+)?", re.IGNORECASE)
_REF = re.compile(r"url\(#([^)\s]+)\)")

Box = tuple[float, float, float, float]  # x0, y0, x1, y1


@dataclass
class LintReport:
    svg: str
    problems: list[str] = field(default_factory=list)
    removed: int = 0
    elements: int = 0
    recolored: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.problems


def _local(el: etree._Element) -> str:
    return etree.QName(el).localname if isinstance(el.tag, str) else ""


def _f(el: etree._Element, name: str, default: float = 0.0) -> float:
    try:
        return float(re.sub(r"[a-z%]+$", "", (el.get(name) or "").strip()) or default)
    except ValueError:
        return default


def _transformed(el: etree._Element) -> bool:
    """True when this element or an ancestor moves it (then its own coordinates say nothing about where it lands)."""
    node: etree._Element | None = el
    while node is not None and _local(node) != "svg":
        if node.get("transform") or _local(node) in ("symbol", "defs", "pattern", "mask", "clipPath", "marker"):
            return True
        node = node.getparent()
    return False


def bbox(el: etree._Element) -> Box | None:
    """A rough box for a simple shape in its own coordinates; None when it cannot be told cheaply."""
    tag = _local(el)
    if tag == "rect":
        x, y = _f(el, "x"), _f(el, "y")
        return x, y, x + _f(el, "width"), y + _f(el, "height")
    if tag == "circle":
        cx, cy, r = _f(el, "cx"), _f(el, "cy"), _f(el, "r")
        return cx - r, cy - r, cx + r, cy + r
    if tag == "ellipse":
        cx, cy, rx, ry = _f(el, "cx"), _f(el, "cy"), _f(el, "rx"), _f(el, "ry")
        return cx - rx, cy - ry, cx + rx, cy + ry
    if tag == "line":
        lx, ly = (_f(el, "x1"), _f(el, "x2")), (_f(el, "y1"), _f(el, "y2"))
        return min(lx), min(ly), max(lx), max(ly)
    if tag in ("polyline", "polygon"):
        nums = [float(n) for n in _NUM.findall(el.get("points") or "")]
        if len(nums) < 4:
            return None
        xs, ys = nums[0::2], nums[1::2]
        return min(xs), min(ys), max(xs), max(ys)
    if tag == "path":
        d = el.get("d") or ""
        # Absolute commands only give a trustworthy box; relative paths are skipped.
        if not d or re.search(r"[a-z]", re.sub(r"e-?\d", "", d)):
            return None
        nums = [float(n) for n in _NUM.findall(d)]
        if len(nums) < 4 or re.search(r"[AHV]", d):
            return None
        xs, ys = nums[0::2], nums[1::2]
        return min(xs), min(ys), max(xs), max(ys)
    return None


def lint(
    svg: str,
    *,
    size: tuple[int, int],
    budget: int = 450,
    allowed_colors: tuple[str, ...] = (),
    safe_band: tuple[float, float] | None = None,
    what: str = "the drawing",
) -> LintReport:
    """Check and tidy one SVG drawing whose canvas is ``size`` (width, height)."""
    root = parse_xml(svg.encode() if isinstance(svg, str) else svg, what)
    width, height = size
    problems: list[str] = []
    removed = 0

    ids = {el.get("id") for el in root.iter() if isinstance(el.tag, str) and el.get("id")}
    dangling: set[str] = set()
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        for value in el.attrib.values():
            dangling.update(m for m in _REF.findall(value) if m not in ids)
        href = el.get("href") or el.get("{http://www.w3.org/1999/xlink}href") or ""
        if href.startswith("#") and href[1:] not in ids:
            dangling.add(href[1:])
    if dangling:
        problems.append(
            f"These ids are referenced but never defined: {', '.join(sorted(dangling)[:6])}. Define them or remove the references."
        )

    shapes = [el for el in root.iter() if _local(el) in SHAPES]
    if len(shapes) > budget:
        problems.append(f"The drawing has {len(shapes)} shapes; keep it under {budget} (reuse <defs> and simplify).")

    boxes: list[tuple[etree._Element, Box]] = []
    for el in shapes:
        if _transformed(el):
            continue
        box = bbox(el)
        if box is not None:
            boxes.append((el, box))

    area = width * height
    for el, (x0, y0, x1, y1) in boxes:
        parent = el.getparent()
        if x1 < -2 or y1 < -2 or x0 > width + 2 or y0 > height + 2:
            if parent is not None:
                parent.remove(el)
                removed += 1
            continue
        w, h = max(0.0, x1 - x0), max(0.0, y1 - y0)
        tiny = w * h < area * 0.00004 and max(w, h) < min(width, height) * 0.02
        if tiny and _local(el) != "text":
            # A tiny mark with nothing else around it is a stray; tiny marks in clusters (stars, dots) are deliberate.
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            # Backgrounds and big shapes do not count: a dot alone on the sky is still a stray.
            near = sum(
                1
                for other, (a0, b0, a1, b1) in boxes
                if other is not el and (a1 - a0) * (b1 - b0) < area * 0.05 and a0 - 40 <= cx <= a1 + 40 and b0 - 40 <= cy <= b1 + 40
            )
            if near == 0 and parent is not None:
                parent.remove(el)
                removed += 1

    if safe_band is not None:
        top, bottom = safe_band
        for el in root.iter():
            if _local(el) != "text" or _transformed(el):
                continue
            y = _f(el, "y", -1)
            if y >= 0 and (y < top or y > bottom + 20):
                words = "".join(el.itertext()).strip()[:30]
                problems.append(f"The text '{words}' sits at y={y:g}, outside the crop-safe band y {top:g}-{bottom:g}; move it in.")

    recolored = snap_tree(root, allowed_colors) if allowed_colors else {}
    out = etree.tostring(root, encoding="unicode")
    return LintReport(out, problems, removed, len(shapes), recolored)
