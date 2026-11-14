"""Code-drawn opening templates: cheat sheet, versus, big number, framework diagrams and data charts.

Claude writes the words and data (``OpeningBuild``); a template lays them out on a 1600x900 canvas with every
essential inside the centre 5:2 band, so any platform's thumbnail crop keeps it. To add a template, define its
layout here (or in ``charts.py``), register it in ``TEMPLATES`` and list it on its style in ``styles.py``.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from proseferno.images.base import ImageProviderError
from proseferno.images.opening.canvas import Box, Canvas, Theme, W, frame, mix, readable_on, render, theme_for
from proseferno.images.opening.charts import CHARTS, label_names, series_names
from proseferno.images.opening.specs import OpeningBuild

HEADLINE_MAX = 70
SUBHEAD_MAX = 110


@dataclass(frozen=True)
class Template:
    id: str
    style: str
    name: str
    # What it looks like and what it is for, for the pitching and build prompts.
    looks_like: str
    draw: Callable[[Canvas, OpeningBuild, Box], None]
    items: tuple[int, int] = (0, 0)
    label_max: int = 0
    detail_max: int = 0
    # Charts: how many distinct series and labels the data needs.
    series: tuple[int, int] = (0, 0)
    labels: tuple[int, int] = (0, 0)
    # Extra fields it uses, with their limits.
    fields: tuple[tuple[str, int], ...] = ()
    notes: str = ""

    @property
    def is_chart(self) -> bool:
        return self.id in CHARTS


# -- layouts --------------------------------------------------------------------------


def _badge(c: Canvas, cx: float, cy: float, r: float, number: int, color: str) -> None:
    c.circle(cx, cy, r, color)
    c.text((int(cx - r), int(cy - r), int(2 * r), int(2 * r)), str(number), "badge", fill=readable_on(color), group="badge")


def cheat_grid(c: Canvas, b: OpeningBuild, body: Box) -> None:
    x, y, w, h = body
    n = len(b.items)
    cols = {1: 1, 2: 2, 3: 3, 4: 2, 5: 3, 6: 3, 7: 4, 8: 4, 9: 3}.get(n, 4)
    rows = math.ceil(n / cols)
    gap = 22
    tile_w = (w - gap * (cols - 1)) / cols
    tile_h = (h - gap * (rows - 1)) / rows
    pad = 20
    r = min(26.0, tile_h * 0.2)
    has_detail = any(i.detail.strip() for i in b.items)
    for k, item in enumerate(b.items):
        tx = x + (k % cols) * (tile_w + gap)
        ty = y + (k // cols) * (tile_h + gap)
        c.rect((int(tx), int(ty), int(tile_w), int(tile_h)), c.theme.panel, rx=18)
        c.rect((int(tx), int(ty), 8, int(tile_h)), c.theme.accent(k), rx=4)
        _badge(c, tx + pad + 8 + r, ty + pad + r, r, k + 1, c.theme.accent(k))
        label_x = int(tx + pad + 8 + 2 * r + 14)
        label_h = int((tile_h - 2 * pad) * (0.46 if has_detail else 1.0))
        c.text(
            (label_x, int(ty + pad), int(tx + tile_w - pad - label_x), max(label_h, int(2 * r))),
            item.label,
            "label",
            align="left",
            group="label",
        )
        if item.detail.strip():
            top = int(ty + pad + max(label_h, 2 * r) + 6)
            c.text(
                (int(tx + pad + 8), top, int(tile_w - 2 * pad - 8), int(ty + tile_h - pad - top)),
                item.detail,
                "detail",
                align="left",
                group="detail",
            )


def _cross(c: Canvas, cx: float, cy: float, s: float, color: str) -> None:
    c.line(cx - s, cy - s, cx + s, cy + s, color, 6)
    c.line(cx - s, cy + s, cx + s, cy - s, color, 6)


def _check(c: Canvas, cx: float, cy: float, s: float, color: str) -> None:
    c.add(
        f'<polyline points="{cx - s:.1f},{cy:.1f} {cx - s * 0.3:.1f},{cy + s * 0.7:.1f} {cx + s:.1f},{cy - s * 0.8:.1f}" '
        f'fill="none" stroke="{color}" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>'
    )


def versus(c: Canvas, b: OpeningBuild, body: Box) -> None:
    x, y, w, h = body
    mid_gap = 96
    col_w = (w - mid_gap) / 2
    head_h = 66
    old, new = mix(c.theme.panel, c.theme.ink, 0.12), c.theme.accent(0)
    for side, (fill, title) in enumerate(((old, b.left_label), (new, b.right_label))):
        cx = x + side * (col_w + mid_gap)
        c.rect((int(cx), y, int(col_w), head_h), fill, rx=14)
        c.text((int(cx) + 20, y, int(col_w) - 40, head_h), title, "label", fill=readable_on(fill), group="vh")
    rows_top = y + head_h + 18
    n = len(b.items)
    gap = 14
    row_h = (y + h - rows_top - gap * (n - 1)) / n
    for i, item in enumerate(b.items):
        ry = rows_top + i * (row_h + gap)
        for side, text in enumerate((item.label, item.detail)):
            cx = x + side * (col_w + mid_gap)
            c.rect((int(cx), int(ry), int(col_w), int(row_h)), c.theme.panel, rx=12)
            mark = cx + 40
            if side == 0:
                _cross(c, mark, ry + row_h / 2, 11, c.theme.accent(2))
            else:
                _check(c, mark, ry + row_h / 2, 14, c.theme.accent(0))
            role = "detail" if side == 0 else "label"
            c.text((int(cx) + 76, int(ry) + 8, int(col_w) - 96, int(row_h) - 16), text, role, align="left", group=f"vr{side}")
    vx, vy = x + col_w + mid_gap / 2, y + head_h / 2
    c.circle(vx, vy, 38, c.theme.ink)
    c.text((int(vx - 34), int(vy - 30), 68, 60), "VS", "badge", fill=c.theme.bg)


def big_number(c: Canvas, b: OpeningBuild, body: Box) -> None:
    x, y, w, h = body
    split = int(w * 0.52)
    c.text((x, y, split - 30, h), b.number, "number", align="left")
    c.line(x + split, y + 20, x + split, y + h - 20, c.theme.line, 3)
    right = x + split + 40
    c.text((right, y + 10, x + w - right, int(h * 0.55)), b.subhead or b.headline, "label", align="left")
    if b.items:
        c.text((right, y + int(h * 0.58), x + w - right, int(h * 0.4)), b.items[0].label, "detail", align="left")


def big_number_frame(c: Canvas, b: OpeningBuild, sources: str) -> Box:
    """Big numbers lead with the figure: the headline sits above it and there is no separate subhead line."""
    return frame(c, b.headline, "", sources)


def flow(c: Canvas, b: OpeningBuild, body: Box) -> None:
    x, y, w, h = body
    n = len(b.items)
    arrow = 64
    box_w = (w - arrow * (n - 1)) / n
    box_h = min(h, 330)
    top = y + (h - box_h) / 2
    for i, item in enumerate(b.items):
        bx = x + i * (box_w + arrow)
        last = i == n - 1
        c.rect((int(bx), int(top), int(box_w), int(box_h)), c.theme.panel, rx=18, stroke=c.theme.accent(0) if last else "", stroke_width=4)
        _badge(c, bx + 40, top + 40, 22, i + 1, c.theme.accent(i))
        c.text((int(bx) + 20, int(top) + 74, int(box_w) - 40, int(box_h * 0.32)), item.label, "label", align="left", group="fl")
        if item.detail.strip():
            dy = int(top + 74 + box_h * 0.32 + 8)
            c.text(
                (int(bx) + 20, dy, int(box_w) - 40, int(top + box_h - 18 - dy)),
                item.detail,
                "detail",
                align="left",
                valign="top",
                group="fd",
            )
        if not last:
            c.arrow(bx + box_w + 10, top + box_h / 2, bx + box_w + arrow - 8, top + box_h / 2, c.theme.accent(0), 6)


def matrix_2x2(c: Canvas, b: OpeningBuild, body: Box) -> None:
    x, y, w, h = body
    axis = 40
    gx, gy, gw, gh = x + axis, y + 34, w - axis, h - 34 - axis
    gap = 14
    qw, qh = (gw - gap) / 2, (gh - gap) / 2
    c.arrow(x + 14, gy + gh, x + 14, gy - 4, c.theme.muted, 5)
    c.arrow(gx, gy + gh + 24, gx + gw, gy + gh + 24, c.theme.muted, 5)
    c.text((x + 40, y, int(gw * 0.6), 30), b.right_label, "tick", align="left")
    c.text((int(gx + gw * 0.3), int(gy + gh + 34), int(gw * 0.7), 30), b.left_label, "tick", align="right")
    for i, item in enumerate(b.items[:4]):
        qx = gx + (i % 2) * (qw + gap)
        qy = gy + (i // 2) * (qh + gap)
        hot = i == 1
        fill = c.theme.accent(0) if hot else c.theme.panel
        ink = readable_on(fill) if hot else c.theme.ink
        c.rect((int(qx), int(qy), int(qw), int(qh)), fill, rx=16)
        c.text((int(qx) + 24, int(qy) + 14, int(qw) - 48, int(qh * 0.45)), item.label, "label", align="left", fill=ink, group="ml")
        if item.detail.strip():
            c.text(
                (int(qx) + 24, int(qy + qh * 0.45) + 18, int(qw) - 48, int(qh * 0.55) - 30),
                item.detail,
                "detail",
                align="left",
                valign="top",
                fill=mix(ink, fill, 0.15),
                group="md",
            )


def stack(c: Canvas, b: OpeningBuild, body: Box) -> None:
    x, y, w, h = body
    n = len(b.items)
    gap = 12
    layer_h = (h - gap * (n - 1)) / n
    for i, item in enumerate(b.items):
        inset = i * 26
        ly = y + i * (layer_h + gap)
        c.rect((x + inset, int(ly), w - 2 * inset, int(layer_h)), c.theme.panel, rx=14)
        c.rect((x + inset, int(ly), 14, int(layer_h)), c.theme.accent(i), rx=6)
        c.text((x + inset + 36, int(ly), int(w * 0.32), int(layer_h)), item.label, "label", align="left", group="sl")
        c.text(
            (x + inset + int(w * 0.36), int(ly) + 6, w - 2 * inset - int(w * 0.36) - 24, int(layer_h) - 12),
            item.detail,
            "detail",
            align="left",
            group="sd",
        )


def cycle(c: Canvas, b: OpeningBuild, body: Box) -> None:
    x, y, w, h = body
    n = len(b.items)
    cx, cy = x + w / 2, y + h / 2
    node_w, node_h = 380, 140
    rx, ry = w / 2 - node_w / 2 - 10, h / 2 - node_h / 2 - 4
    c.add(f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" fill="none" stroke="{c.theme.line}" stroke-width="3"/>')
    centres = [
        (cx + rx * math.cos(-math.pi / 2 + 2 * math.pi * i / n), cy + ry * math.sin(-math.pi / 2 + 2 * math.pi * i / n)) for i in range(n)
    ]
    for i in range(n):
        (ax, ay), (bx, by) = centres[i], centres[(i + 1) % n]
        c.arrow(ax + (bx - ax) * 0.36, ay + (by - ay) * 0.36, ax + (bx - ax) * 0.64, ay + (by - ay) * 0.64, c.theme.accent(0), 6)
    for i, (item, (px, py)) in enumerate(zip(b.items, centres, strict=True)):
        left, top = px - node_w / 2, py - node_h / 2
        c.rect((int(left), int(top), node_w, node_h), c.theme.panel, rx=18, stroke=c.theme.accent(i), stroke_width=3)
        c.text((int(left) + 18, int(top) + 10, node_w - 36, 54), item.label, "label", group="cl")
        c.text((int(left) + 18, int(top) + 66, node_w - 36, node_h - 76), item.detail, "detail", group="cd")


def funnel(c: Canvas, b: OpeningBuild, body: Box) -> None:
    x, y, w, h = body
    n = len(b.items)
    gap = 10
    stage_h = (h - gap * (n - 1)) / n
    full = w * 0.56
    narrow = full * 0.42
    centre = x + full / 2
    for i, item in enumerate(b.items):
        top_w = full - (full - narrow) * i / n
        bottom_w = full - (full - narrow) * (i + 1) / n
        sy = y + i * (stage_h + gap)
        color = c.theme.accent(i)
        points = (
            f"{centre - top_w / 2:.1f},{sy:.1f} {centre + top_w / 2:.1f},{sy:.1f} "
            f"{centre + bottom_w / 2:.1f},{sy + stage_h:.1f} {centre - bottom_w / 2:.1f},{sy + stage_h:.1f}"
        )
        c.add(f'<polygon points="{points}" fill="{color}"/>')
        c.text(
            (int(centre - bottom_w / 2) + 12, int(sy), int(bottom_w) - 24, int(stage_h)),
            item.label,
            "label",
            fill=readable_on(color),
            group="ul",
        )
        dx = int(x + full + 50)
        c.line(centre + top_w / 2 + 8, sy + stage_h / 2, dx - 12, sy + stage_h / 2, c.theme.line, 2, dash="4 6")
        c.text((dx, int(sy), x + w - dx, int(stage_h)), item.detail, "detail", align="left", group="ud")


def timeline(c: Canvas, b: OpeningBuild, body: Box) -> None:
    x, y, w, h = body
    n = len(b.items)
    # Dates above the line, details below it, the whole group centred in the body.
    label_h, detail_h = min(110, h * 0.3), min(190, h * 0.45)
    top = y + (h - (label_h + 60 + detail_h)) / 2
    line_y = top + label_h + 28
    slot = w / n
    c.line(x, line_y, x + w, line_y, c.theme.line, 6)
    for i, item in enumerate(b.items):
        cx = x + slot * (i + 0.5)
        last = i == n - 1
        c.circle(cx, line_y, 20 if last else 15, c.theme.accent(0) if last else c.theme.accent(i), stroke=c.theme.bg, stroke_width=5)
        c.text(
            (int(cx - slot / 2) + 10, int(top), int(slot) - 20, int(label_h)),
            item.label,
            "headline",
            fill=c.theme.accent(0) if last else "",
            group="tl",
        )
        c.text((int(cx - slot / 2) + 14, int(line_y + 34), int(slot) - 28, int(detail_h)), item.detail, "subhead", valign="top", group="td")


# -- the catalog --------------------------------------------------------------------------

_CHART_FIELDS = (("unit", 8), ("annotation", 90))

TEMPLATES: dict[str, Template] = {
    t.id: t
    for t in [
        Template(
            "cheat_grid",
            "cheat_sheet",
            "Cheat sheet grid",
            "A grid of 4-9 numbered tiles, each a bold label (a step, rule or command) and one short line of detail.",
            cheat_grid,
            items=(4, 9),
            label_max=32,
            detail_max=80,
        ),
        Template(
            "versus",
            "versus",
            "Versus split",
            "Two titled columns with 2-5 matched rows: the old way or myth on the left (crossed), "
            "the new way or reality on the right (checked).",
            versus,
            items=(2, 5),
            label_max=60,
            detail_max=60,
            fields=(("left_label", 24), ("right_label", 24)),
            notes="Each item's `label` is the left cell and its `detail` the matching right cell.",
        ),
        Template(
            "big_number",
            "big_number",
            "Big number",
            "One huge figure on the left; what it means on the right; the source underneath.",
            big_number,
            items=(0, 1),
            label_max=110,
            fields=(("number", 8),),
            notes="`number` is the figure exactly as printed. `subhead` says what it measures (up to 110 characters); "
            "an optional single item's `label` adds one line of context. Put the figure's value in `data` too (one row), "
            "so it can be checked against the research.",
        ),
        Template(
            "flow",
            "framework",
            "Flow",
            "3-6 numbered steps left to right with arrows between them; the last step is highlighted.",
            flow,
            items=(3, 6),
            label_max=24,
            detail_max=64,
        ),
        Template(
            "matrix_2x2",
            "framework",
            "2x2 matrix",
            "Four quadrants with two labelled axes; the top-right quadrant is highlighted as the place to be.",
            matrix_2x2,
            items=(4, 4),
            label_max=24,
            detail_max=60,
            fields=(("left_label", 30), ("right_label", 30)),
            notes="Items in order: top-left, top-right (the winner), bottom-left, bottom-right. `left_label` is the x-axis "
            "(low to high, left to right), `right_label` the y-axis (low to high, bottom to top).",
        ),
        Template(
            "stack",
            "framework",
            "Layered stack",
            "3-5 horizontal layers stacked top to bottom, each a label and a line of detail (a tech stack, levels, tiers).",
            stack,
            items=(3, 5),
            label_max=24,
            detail_max=80,
        ),
        Template(
            "cycle",
            "framework",
            "Cycle",
            "3-6 stages around a loop with arrows: a feedback loop, a flywheel, an iteration cycle.",
            cycle,
            items=(3, 6),
            label_max=20,
            detail_max=44,
        ),
        Template(
            "funnel",
            "framework",
            "Funnel",
            "3-5 narrowing stages, each with a line of detail beside it.",
            funnel,
            items=(3, 5),
            label_max=18,
            detail_max=70,
        ),
        Template(
            "timeline",
            "framework",
            "Timeline",
            "3-6 dated milestones on a line, each with a short line of detail; the last is highlighted.",
            timeline,
            items=(3, 6),
            label_max=16,
            detail_max=60,
        ),
        Template(
            "line_annotated",
            "data_chart",
            "Annotated line",
            "A trend over time for 1-4 series, the first highlighted, with end labels and one callout on its peak.",
            CHARTS["line_annotated"],
            series=(1, 4),
            labels=(3, 40),
            fields=_CHART_FIELDS,
            notes="`label` is the x value (in time order), `series` the line name ('' for a single line).",
        ),
        Template(
            "slope",
            "data_chart",
            "Slope chart",
            "Two points in time for 2-8 things, joined by lines; the biggest mover is highlighted.",
            CHARTS["slope"],
            series=(2, 2),
            labels=(2, 8),
            fields=_CHART_FIELDS[:1],
            notes="`series` is the period (exactly two, earlier first), `label` the thing measured.",
        ),
        Template(
            "dumbbell",
            "data_chart",
            "Dumbbell",
            "Before and after (or A and B) for 2-10 rows as two dots joined by a bar.",
            CHARTS["dumbbell"],
            series=(2, 2),
            labels=(2, 10),
            fields=_CHART_FIELDS[:1],
            notes="`series` names the two states (exactly two, the 'before' first), `label` the row.",
        ),
        Template(
            "waterfall",
            "data_chart",
            "Waterfall",
            "How a starting total becomes an ending one: 3-10 bars of gains and losses between total bars.",
            CHARTS["waterfall"],
            series=(1, 2),
            labels=(3, 10),
            fields=_CHART_FIELDS[:1],
            notes="Rows in order. A row with `series` 'total' is drawn from zero (the start, a subtotal or the end); "
            "every other row is a change (+/-) with `series` ''.",
        ),
        Template(
            "tornado",
            "data_chart",
            "Tornado",
            "2-10 factors with bars to the left and right of a centre line, sorted biggest first: sensitivity or two groups.",
            CHARTS["tornado"],
            series=(2, 2),
            labels=(2, 10),
            fields=_CHART_FIELDS[:1],
            notes="`series` names the two sides (exactly two, left first), `label` the factor; values are sizes (signs are ignored).",
        ),
        Template(
            "ranked_bar",
            "data_chart",
            "Ranked bars",
            "2-12 horizontal bars sorted largest first, the leader highlighted.",
            CHARTS["ranked_bar"],
            series=(1, 1),
            labels=(2, 12),
            fields=_CHART_FIELDS[:1],
            notes="One row per bar, `series` ''; values zero or more.",
        ),
        Template(
            "heatmap",
            "data_chart",
            "Heatmap",
            "A grid of 2-10 columns by 2-8 rows, each cell coloured and labelled by its value.",
            CHARTS["heatmap"],
            series=(2, 8),
            labels=(2, 10),
            fields=_CHART_FIELDS[:1],
            notes="`label` is the column, `series` the row.",
        ),
        Template(
            "spider",
            "data_chart",
            "Spider (radar)",
            "3-8 axes around a centre with 1-3 overlaid shapes: comparing profiles across dimensions.",
            CHARTS["spider"],
            series=(1, 3),
            labels=(3, 8),
            fields=_CHART_FIELDS[:1],
            notes="`label` is the axis, `series` the shape; values zero or more on one shared scale.",
        ),
    ]
}


def get_template(template_id: str) -> Template | None:
    return TEMPLATES.get(template_id)


def for_style(style_id: str) -> list[Template]:
    return [t for t in TEMPLATES.values() if t.style == style_id]


def menu(style_ids: list[str]) -> str:
    """The templates each code-drawn style can use, for the pitching prompt."""
    lines = []
    for style_id in style_ids:
        for t in for_style(style_id):
            lines.append(f"  - `{t.id}` ({t.name}, style `{style_id}`): {t.looks_like}")
    return "\n".join(lines)


def build_spec(t: Template) -> str:
    """What the build call must fill in for this template, with every limit."""
    lines = [
        f"Template `{t.id}`: {t.name}. {t.looks_like}",
        f"- `headline`: up to {HEADLINE_MAX} characters, the takeaway a reader gets at a glance.",
        f"- `subhead`: up to {SUBHEAD_MAX} characters of context ('' allowed).",
    ]
    if t.items != (0, 0):
        lines.append(
            f"- `items`: {t.items[0]}-{t.items[1]} entries; `label` up to {t.label_max} characters"
            + (f", `detail` up to {t.detail_max} characters." if t.detail_max else ", `detail` ''.")
        )
    if t.is_chart:
        lines.append(f"- `data`: {t.labels[0]}-{t.labels[1]} distinct labels and {t.series[0]}-{t.series[1]} distinct series.")
        lines.append("- `sources`: every source a number came from (title as printed; the URL from the research, or '' for the post).")
    for name, limit in t.fields:
        lines.append(f"- `{name}`: up to {limit} characters.")
    if t.notes:
        lines.append(f"- {t.notes}")
    lines.append("- Every field this template does not use stays empty.")
    return "\n".join(lines)


def validate(t: Template, b: OpeningBuild) -> tuple[list[str], list[str]]:
    """(blocking problems, style problems). Overlong text still fits (it shrinks) but reads worse, so it costs a retry."""
    blocking: list[str] = []
    style: list[str] = []

    def length(name: str, text: str, limit: int) -> None:
        if limit and len(text.strip()) > limit * 1.15:
            style.append(f"`{name}` has {len(text.strip())} characters; the limit is {limit}.")

    if not b.headline.strip():
        blocking.append("`headline` is empty.")
    length("headline", b.headline, HEADLINE_MAX)
    length("subhead", b.subhead, SUBHEAD_MAX)
    lo, hi = t.items
    if (lo, hi) != (0, 0) and not lo <= len(b.items) <= hi:
        blocking.append(f"`items` needs {lo}-{hi} entries; it has {len(b.items)}.")
    for i, item in enumerate(b.items):
        if lo and not item.label.strip():
            blocking.append(f"Item {i + 1} has no label.")
        length(f"items[{i}].label", item.label, t.label_max)
        length(f"items[{i}].detail", item.detail, t.detail_max)
    for name, limit in t.fields:
        value = str(getattr(b, name, "") or "")
        length(name, value, limit)
        if name in ("number", "left_label", "right_label") and not value.strip():
            blocking.append(f"`{name}` is empty.")
    if t.id == "big_number" and not any(ch.isdigit() for ch in b.number):
        blocking.append("`number` must contain the figure's digits.")
    if t.is_chart:
        series, labels = series_names(b.data), label_names(b.data)
        if not t.labels[0] <= len(labels) <= t.labels[1]:
            blocking.append(f"`data` needs {t.labels[0]}-{t.labels[1]} distinct labels; it has {len(labels)}.")
        if t.id != "waterfall" and not t.series[0] <= len(series) <= t.series[1]:
            blocking.append(f"`data` needs {t.series[0]}-{t.series[1]} distinct series; it has {len(series)}.")
        if t.id in ("ranked_bar", "spider") and any(d.value < 0 for d in b.data):
            blocking.append("Values must be zero or more for this chart.")
        if t.id in ("slope", "dumbbell", "tornado") and len(series) == 2:
            table = {(d.label.strip(), d.series.strip()) for d in b.data}
            if not any((label, series[0]) in table and (label, series[1]) in table for label in labels):
                blocking.append("Every row needs a value for both series.")
        if not b.sources:
            blocking.append("`sources` is empty: say where the numbers come from.")
    return blocking, style


def draw(t: Template, b: OpeningBuild, palette: tuple[str, ...] = ()) -> tuple[bytes, int, int]:
    """Lay the build out and render it; raises ImageProviderError when the build cannot be drawn."""
    blocking, _ = validate(t, b)
    if blocking:
        raise ImageProviderError("\n".join(blocking))
    theme: Theme = theme_for(palette)
    canvas = Canvas(theme)
    sources = source_line(b)
    body = big_number_frame(canvas, b, sources) if t.id == "big_number" else frame(canvas, b.headline, b.subhead, sources)
    try:
        t.draw(canvas, b, body)
    except (ValueError, ZeroDivisionError, KeyError, IndexError) as exc:
        raise ImageProviderError(f"The {t.name} could not be laid out: {exc}") from exc
    return render(canvas)


def source_line(b: OpeningBuild) -> str:
    names = list(dict.fromkeys(s.title.strip() for s in b.sources if s.title.strip()))
    if not names:
        return ""
    return ("Source: " if len(names) == 1 else "Sources: ") + "; ".join(names)


def slot_texts(t: Template, b: OpeningBuild) -> list[tuple[str, str, str, int]]:
    """The words an author may retype (name, hint, text, limit); numbers and sources are not among them."""
    slots = [("headline", "Headline", b.headline, HEADLINE_MAX)]
    if t.id != "big_number" or b.subhead:
        slots.append(("subhead", "Subhead" if t.id != "big_number" else "What it measures", b.subhead, SUBHEAD_MAX))
    for i, item in enumerate(b.items):
        slots.append((f"items.{i}.label", f"Item {i + 1}" if not t.is_chart else f"Row {i + 1}", item.label, t.label_max or 60))
        if t.detail_max:
            slots.append((f"items.{i}.detail", f"Item {i + 1} detail", item.detail, t.detail_max))
    for name, limit in t.fields:
        if name not in ("number", "unit"):
            slots.append((name, name.replace("_", " ").capitalize(), str(getattr(b, name, "") or ""), limit))
    return slots


def apply_words(b: OpeningBuild, words: dict[str, str]) -> OpeningBuild:
    """The build with the author's retyped words; unknown names are ignored."""
    data = b.model_dump()
    for name, text in words.items():
        parts = name.split(".")
        if len(parts) == 3 and parts[0] == "items" and parts[1].isdigit() and parts[2] in ("label", "detail"):
            index = int(parts[1])
            if index < len(data["items"]):
                data["items"][index][parts[2]] = text.strip()
        elif name in ("headline", "subhead", "annotation", "left_label", "right_label"):
            data[name] = text.strip()
    return OpeningBuild.model_validate(data)


__all__ = ["TEMPLATES", "Template", "W", "build_spec", "draw", "for_style", "get_template", "menu", "validate"]
