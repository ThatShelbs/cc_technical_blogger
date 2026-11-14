"""Data story charts for the opening image, drawn by code from Claude's verified data.

Claude chooses the chart and supplies the rows; code owns the scales, layout, colors and every label, so a chart is
always legible at thumbnail size and never shows a number that was not in the data.
"""

from __future__ import annotations

import math
from collections.abc import Callable

from proseferno.images.opening.canvas import Box, Canvas, esc, mix, readable_on
from proseferno.images.opening.specs import OpeningBuild, OpeningDatum

INFERNO_RAMP = ("#1b0c41", "#4a0c6b", "#781c6d", "#a52c60", "#cf4446", "#ed6925", "#fb9b06", "#f7d13d", "#fcffa4")


# -- data helpers --------------------------------------------------------------


def series_names(data: list[OpeningDatum]) -> list[str]:
    return list(dict.fromkeys(d.series.strip() for d in data))


def label_names(data: list[OpeningDatum]) -> list[str]:
    return list(dict.fromkeys(d.label.strip() for d in data))


def lookup(data: list[OpeningDatum]) -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = {}
    for d in data:
        out.setdefault((d.label.strip(), d.series.strip()), d.value)
    return out


def fmt_number(value: float) -> str:
    a = abs(value)
    # Thousands stay written out ("1,234") until they get long; then 15.3k, 4.2M, 1.1B.
    for limit, divisor, suffix in ((1e9, 1e9, "B"), (1e6, 1e6, "M"), (1e4, 1e3, "k")):
        if a >= limit:
            text = f"{value / divisor:.1f}".removesuffix(".0")
            return text + suffix
    if a >= 100 or value == int(value):
        return f"{value:,.0f}"
    if a >= 10:
        return f"{value:.1f}".removesuffix(".0")
    return f"{value:.2f}".rstrip("0").rstrip(".")


def fmt_value(value: float, unit: str = "", *, signed: bool = False) -> str:
    sign = "+" if signed and value > 0 else "-" if value < 0 else ""
    number = fmt_number(abs(value))
    unit = unit.strip()
    if unit == "%":
        text = f"{number}%"
    elif unit.startswith(("$", "€", "£")):
        text = f"{unit[0]}{number}{unit[1:]}"
    elif unit:
        text = f"{number} {unit}"
    else:
        text = number
    return sign + text


def nice_ticks(lo: float, hi: float, count: int = 5) -> list[float]:
    if hi <= lo:
        hi = lo + 1
    raw = (hi - lo) / max(1, count)
    magnitude = 10 ** math.floor(math.log10(raw))
    step = next(m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= raw)
    start = math.floor(lo / step + 1e-9) * step
    ticks = [round(start, 10)]
    # Up to the first tick at or above ``hi``, so the axis always closes on a labelled line.
    while ticks[-1] < hi - step * 1e-6:
        ticks.append(round(ticks[-1] + step, 10))
    return ticks


def value_range(values: list[float], *, zero: bool = True) -> tuple[float, float]:
    lo, hi = min(values), max(values)
    if zero and lo >= 0 and lo <= 0.45 * hi:
        lo = 0.0
    elif zero and hi <= 0 and hi >= 0.45 * lo:
        hi = 0.0
    else:
        pad = (hi - lo) * 0.08 or abs(hi) * 0.1 or 1
        lo -= pad
    hi += (hi - lo) * 0.06 or 1
    ticks = nice_ticks(lo, hi)
    return min(lo, ticks[0]), max(hi, ticks[-1])


def spread(wanted: list[float], gap: float, top: float, bottom: float) -> list[float]:
    """Move label centres apart so none are closer than ``gap``, keeping them inside [top, bottom] and in order."""
    order = sorted(range(len(wanted)), key=lambda i: wanted[i])
    pos = [wanted[i] for i in order]
    for i in range(len(pos)):
        pos[i] = max(pos[i], top if i == 0 else pos[i - 1] + gap)
    for i in range(len(pos) - 1, -1, -1):
        pos[i] = min(pos[i], bottom if i == len(pos) - 1 else pos[i + 1] - gap)
    for i in range(len(pos)):
        pos[i] = max(pos[i], top if i == 0 else pos[i - 1] + gap)
    out = [0.0] * len(wanted)
    for rank, i in enumerate(order):
        out[i] = pos[rank]
    return out


def ramp(t: float, colors: tuple[str, ...] = INFERNO_RAMP) -> str:
    t = max(0.0, min(1.0, t)) * (len(colors) - 1)
    i = min(len(colors) - 2, int(t))
    return mix(colors[i], colors[i + 1], t - i)


def _muted_bar(c: Canvas) -> str:
    return mix(c.theme.panel, c.theme.ink, 0.28)


def _legend(c: Canvas, box: Box, names: list[str], colors: list[str]) -> None:
    x, y, w, h = box
    slot = min(360, w // max(1, len(names)))
    for i, (name, color) in enumerate(zip(names, colors, strict=False)):
        left = x + i * slot
        c.circle(left + 12, y + h / 2, 10, color)
        c.text((left + 30, y, slot - 40, h), name, "tick", align="left", group="legend")


def _y_axis(c: Canvas, plot: Box, lo: float, hi: float, unit: str) -> Callable[[float], float]:
    px, py, pw, ph = plot

    def to_y(v: float) -> float:
        return py + ph - (v - lo) / (hi - lo) * ph

    for tick in nice_ticks(lo, hi):
        if lo - 1e-9 <= tick <= hi + 1e-9:
            ty = to_y(tick)
            c.line(px, ty, px + pw, ty, c.theme.line, 1.5 if tick else 2.5)
            c.text((px - 112, int(ty) - 14, 88, 28), fmt_value(tick, unit), "tick", align="right", group="yt")
    return to_y


# -- charts ----------------------------------------------------------------------------


def ranked_bar(c: Canvas, b: OpeningBuild, body: Box) -> None:
    x, y, w, h = body
    rows: dict[str, float] = {}
    for d in b.data:
        rows.setdefault(d.label.strip(), d.value)
    ordered = sorted(rows.items(), key=lambda kv: kv[1], reverse=True)
    n = len(ordered)
    label_w, value_w = 360, 170
    bar_x = x + label_w + 18
    bar_max = w - label_w - 18 - value_w
    gap = min(18, h * 0.3 / n)
    bar_h = min(68, (h - gap * (n - 1)) / n)
    top = y + (h - (bar_h * n + gap * (n - 1))) / 2
    vmax = max(v for _, v in ordered) or 1
    for i, (name, value) in enumerate(ordered):
        by = top + i * (bar_h + gap)
        bw = max(4, bar_max * max(0.0, value) / vmax)
        c.rect((int(bar_x), int(by), int(bw), int(bar_h)), c.theme.accent(0) if i == 0 else _muted_bar(c), rx=6)
        c.text((x, int(by), label_w, int(bar_h)), name, "label", align="right", group="rl")
        c.text((int(bar_x + bw + 14), int(by), value_w, int(bar_h)), fmt_value(value, b.unit), "value", align="left", group="rv")


def line_annotated(c: Canvas, b: OpeningBuild, body: Box) -> None:
    x, y, w, h = body
    names = series_names(b.data)
    xs = label_names(b.data)
    table = lookup(b.data)
    values = [d.value for d in b.data]
    lo, hi = value_range(values)
    plot = (x + 110, y + 8, w - 110 - 250, h - 52)
    px, py, pw, ph = plot
    to_y = _y_axis(c, plot, lo, hi, b.unit)

    def to_x(i: int) -> float:
        return px + (pw * i / (len(xs) - 1) if len(xs) > 1 else pw / 2)

    shown = sorted({round(i * (len(xs) - 1) / 6) for i in range(7)}) if len(xs) > 8 else list(range(len(xs)))
    for i in shown:
        c.text((int(to_x(i)) - 80, py + ph + 10, 160, 34), xs[i], "tick", group="xt")
    ends: list[tuple[float, str, str]] = []
    key_point: tuple[float, float] | None = None
    every_point: list[tuple[float, float]] = []
    for s, name in enumerate(names):
        color = c.theme.accent(0) if s == 0 else mix(c.theme.accent(s + 2), c.theme.bg, 0.15)
        points = [(to_x(i), to_y(table[(label, name)])) for i, label in enumerate(xs) if (label, name) in table]
        if not points:
            continue
        every_point += points
        path = " ".join(f"{px_:.1f},{py_:.1f}" for px_, py_ in points)
        width = 7 if s == 0 else 4
        c.add(
            f'<polyline points="{path}" fill="none" stroke="{color}" stroke-width="{width}" '
            'stroke-linejoin="round" stroke-linecap="round"/>'
        )
        c.circle(*points[-1], 9 if s == 0 else 6, color)
        last_label = next(label for label in reversed(xs) if (label, name) in table)
        text = f"{name}  {fmt_value(table[(last_label, name)], b.unit)}" if name else fmt_value(table[(last_label, name)], b.unit)
        ends.append((points[-1][1], text, color))
        if s == 0:
            key_point = max(points, key=lambda p: -p[1]) if b.annotation else None
    placed = spread([e[0] for e in ends], 38, py + 16, py + ph - 16)
    for (_, text, color), ly in zip(ends, placed, strict=True):
        c.text((px + pw + 22, int(ly) - 18, 228, 36), text, "value", align="left", fill=color, group="ends")
    if key_point and b.annotation:
        kx, ky = key_point
        c.circle(kx, ky, 16, "none", stroke=c.theme.ink, stroke_width=3)
        # The callout goes in whichever corner of the plot is furthest from every line.
        box_w, box_h = 460, 100
        corners = [
            (px + 30, py + 10),
            (px + pw - box_w - 10, py + 10),
            (px + 30, py + ph - box_h - 10),
            (px + pw - box_w - 10, py + ph - box_h - 10),
        ]

        def clearance(corner: tuple[float, float]) -> float:
            cx_, cy_ = corner[0] + box_w / 2, corner[1] + box_h / 2
            return min(math.hypot(max(0, abs(x_ - cx_) - box_w / 2), max(0, abs(y_ - cy_) - box_h / 2)) for x_, y_ in every_point)

        bx, by = max(corners, key=clearance)
        c.rect((int(bx), int(by), box_w, box_h), c.theme.panel, rx=12, opacity=0.94)
        c.rect((int(bx), int(by), 8, box_h), c.theme.accent(0), rx=4)
        anchor_x = min(max(kx, bx + 20), bx + box_w - 20)
        anchor_y = by + box_h if ky > by + box_h else by
        c.line(anchor_x, anchor_y, kx, ky + (-16 if ky > anchor_y else 16), c.theme.ink, 2, dash="6 6")
        c.text((int(bx) + 26, int(by) + 12, box_w - 44, box_h - 24), b.annotation, "detail", align="left", fill=c.theme.ink)


def slope(c: Canvas, b: OpeningBuild, body: Box) -> None:
    x, y, w, h = body
    periods = series_names(b.data)[:2]
    entities = label_names(b.data)
    table = lookup(b.data)
    pairs = [(e, table[(e, periods[0])], table[(e, periods[1])]) for e in entities if (e, periods[0]) in table and (e, periods[1]) in table]
    lo, hi = value_range([v for _, a, z in pairs for v in (a, z)], zero=False)
    left_x, right_x = x + 380, x + w - 380
    top, bottom = y + 56, y + h - 16

    def to_y(v: float) -> float:
        return bottom - (v - lo) / (hi - lo) * (bottom - top)

    c.text((left_x - 150, y, 300, 40), periods[0], "label", group="periods")
    c.text((right_x - 150, y, 300, 40), periods[1], "label", group="periods")
    c.line(left_x, top - 6, left_x, bottom + 6, c.theme.line, 3)
    c.line(right_x, top - 6, right_x, bottom + 6, c.theme.line, 3)
    focus = max(range(len(pairs)), key=lambda i: abs(pairs[i][2] - pairs[i][1]))
    lefts = spread([to_y(a) for _, a, _ in pairs], 34, top, bottom)
    rights = spread([to_y(z) for _, _, z in pairs], 34, top, bottom)
    for i, (name, a, z) in enumerate(pairs):
        color = c.theme.accent(0) if i == focus else _muted_bar(c)
        c.line(left_x, to_y(a), right_x, to_y(z), color, 7 if i == focus else 4)
        c.circle(left_x, to_y(a), 9, color)
        c.circle(right_x, to_y(z), 9, color)
        ink = c.theme.ink if i == focus else c.theme.muted
        c.text(
            (x, int(lefts[i]) - 16, left_x - x - 20, 32), f"{name}  {fmt_value(a, b.unit)}", "value", align="right", fill=ink, group="sl"
        )
        c.text(
            (right_x + 20, int(rights[i]) - 16, x + w - right_x - 20, 32),
            f"{fmt_value(z, b.unit)}  {name}",
            "value",
            align="left",
            fill=ink,
            group="sl",
        )


def dumbbell(c: Canvas, b: OpeningBuild, body: Box) -> None:
    x, y, w, h = body
    first, second = series_names(b.data)[:2]
    table = lookup(b.data)
    rows = [(e, table[(e, first)], table[(e, second)]) for e in label_names(b.data) if (e, first) in table and (e, second) in table]
    rows.sort(key=lambda r: r[2], reverse=True)
    colors = [mix(c.theme.muted, c.theme.bg, 0.2), c.theme.accent(0)]
    _legend(c, (x + 360, y, w - 360, 34), [first, second], colors)
    lo, hi = value_range([v for _, a, z in rows for v in (a, z)])
    plot_x, plot_w = x + 380, w - 380 - 30
    top = y + 52
    row_h = (y + h - top) / len(rows)

    def to_x(v: float) -> float:
        return plot_x + (v - lo) / (hi - lo) * plot_w

    for i, (name, a, z) in enumerate(rows):
        cy = top + row_h * (i + 0.5)
        c.line(plot_x, cy, plot_x + plot_w, cy, c.theme.line, 1.5)
        c.line(to_x(a), cy, to_x(z), cy, mix(c.theme.accent(0), c.theme.bg, 0.45), 8)
        c.circle(to_x(a), cy, 12, colors[0])
        c.circle(to_x(z), cy, 14, colors[1])
        c.text((x, int(cy - row_h / 2), 360, int(row_h)), name, "label", align="right", group="dl")
        label_h = int(min(30, row_h * 0.45))
        for value, color in ((a, c.theme.muted), (z, c.theme.ink)):
            right_side = (value >= max(a, z)) if a != z else value == z
            lx = to_x(value) + 20 if right_side else to_x(value) - 140
            c.text(
                (int(lx), int(cy - label_h - 12), 120, label_h),
                fmt_value(value, b.unit),
                "tick",
                align="left" if right_side else "right",
                fill=color,
                group="dv",
            )


def waterfall(c: Canvas, b: OpeningBuild, body: Box) -> None:
    x, y, w, h = body
    bars: list[tuple[str, float, float, str]] = []
    running = 0.0
    for d in b.data:
        if d.series.strip().lower() == "total":
            bars.append((d.label, 0.0, d.value, "total"))
            running = d.value
        else:
            bars.append((d.label, running, running + d.value, "up" if d.value >= 0 else "down"))
            running += d.value
    lo, hi = value_range([v for _, s, e, _ in bars for v in (s, e)] + [0.0])
    plot = (x + 110, y + 40, w - 120, h - 40 - 64)
    px, py, pw, ph = plot
    to_y = _y_axis(c, plot, lo, hi, b.unit)
    slot = pw / len(bars)
    colors = {"total": _muted_bar(c), "up": c.theme.accent(0), "down": c.theme.accent(2)}
    for i, (name, start, end, kind) in enumerate(bars):
        bx = px + slot * i + slot * 0.18
        bw = slot * 0.64
        top_y, bottom_y = sorted((to_y(start), to_y(end)))
        c.rect((int(bx), int(top_y), int(bw), max(3, int(bottom_y - top_y))), colors[kind], rx=4)
        if i + 1 < len(bars) and bars[i + 1][3] != "total":
            c.line(bx + bw, to_y(end), bx + slot, to_y(end), c.theme.muted, 2, dash="5 6")
        value = end if kind == "total" else end - start
        label_y = top_y - 36 if (kind != "down" or kind == "total") else bottom_y + 4
        c.text((int(px + slot * i), int(label_y), int(slot), 32), fmt_value(value, b.unit, signed=kind != "total"), "value", group="wv")
        c.text((int(px + slot * i) + 4, py + ph + 10, int(slot) - 8, 54), name, "tick", group="wl")


def tornado(c: Canvas, b: OpeningBuild, body: Box) -> None:
    x, y, w, h = body
    low, high = series_names(b.data)[:2]
    table = lookup(b.data)
    rows = [(e, abs(table[(e, low)]), abs(table[(e, high)])) for e in label_names(b.data) if (e, low) in table and (e, high) in table]
    rows.sort(key=lambda r: r[1] + r[2], reverse=True)
    label_w = 330
    cx = x + label_w + (w - label_w) / 2
    half = (w - label_w) / 2 - 130
    vmax = max(max(a, z) for _, a, z in rows) or 1
    left_color, right_color = c.theme.accent(2), c.theme.accent(0)
    c.text((int(cx - half), y, int(half) - 10, 34), low, "tick", align="right", fill=left_color)
    c.text((int(cx) + 10, y, int(half), 34), high, "tick", align="left", fill=right_color)
    top = y + 46
    row_h = (y + h - top) / len(rows)
    bar_h = min(56, row_h * 0.7)
    for i, (name, a, z) in enumerate(rows):
        cy = top + row_h * (i + 0.5)
        lw, rw = half * a / vmax, half * z / vmax
        c.rect((int(cx - lw), int(cy - bar_h / 2), int(lw), int(bar_h)), left_color, rx=4)
        c.rect((int(cx), int(cy - bar_h / 2), int(rw), int(bar_h)), right_color, rx=4)
        c.text((x, int(cy - row_h / 2), label_w - 16, int(row_h)), name, "label", align="right", group="tl")
        c.text((int(cx - lw - 124), int(cy - bar_h / 2), 116, int(bar_h)), fmt_value(a, b.unit), "tick", align="right", group="tv")
        c.text((int(cx + rw + 8), int(cy - bar_h / 2), 116, int(bar_h)), fmt_value(z, b.unit), "tick", align="left", group="tv")
    c.line(cx, top - 6, cx, y + h, c.theme.ink, 3)


def heatmap(c: Canvas, b: OpeningBuild, body: Box) -> None:
    x, y, w, h = body
    cols, rows = label_names(b.data), series_names(b.data)
    table = lookup(b.data)
    values = list(table.values())
    lo, hi = min(values), max(values)
    label_w, head_h, gap = 280, 44, 6
    cell_w = (w - label_w - gap * (len(cols) - 1)) / len(cols)
    cell_h = (h - head_h - gap * (len(rows) - 1)) / len(rows)
    brand = c.theme.accents[0] != "#fb9b06"
    for j, col in enumerate(cols):
        c.text((int(x + label_w + j * (cell_w + gap)), y, int(cell_w), head_h - 8), col, "tick", group="hc")
    for i, row in enumerate(rows):
        cy = y + head_h + i * (cell_h + gap)
        c.text((x, int(cy), label_w - 16, int(cell_h)), row, "label", align="right", group="hr")
        for j, col in enumerate(cols):
            if (col, row) not in table:
                continue
            value = table[(col, row)]
            t = (value - lo) / (hi - lo) if hi > lo else 0.5
            fill = mix(c.theme.panel, c.theme.accent(0), 0.15 + 0.85 * t) if brand else ramp(0.12 + 0.88 * t)
            cx = x + label_w + j * (cell_w + gap)
            c.rect((int(cx), int(cy), int(cell_w), int(cell_h)), fill, rx=6)
            c.text((int(cx), int(cy), int(cell_w), int(cell_h)), fmt_value(value, b.unit), "value", fill=readable_on(fill), group="hv")


def spider(c: Canvas, b: OpeningBuild, body: Box) -> None:
    x, y, w, h = body
    axes, names = label_names(b.data), series_names(b.data)
    table = lookup(b.data)
    vmax = max(max(v for v in table.values()), 1e-9)
    ticks = nice_ticks(0, vmax, 4)
    vmax = ticks[-1]
    legend_w = 380 if any(names) else 0
    cx, cy = x + (w - legend_w) / 2, y + h / 2
    radius = h / 2 - 22

    def point(i: int, r: float) -> tuple[float, float]:
        angle = -math.pi / 2 + 2 * math.pi * i / len(axes)
        return cx + r * math.cos(angle), cy + r * math.sin(angle)

    for t in ticks[1:]:
        ring = " ".join(f"{px:.1f},{py:.1f}" for px, py in (point(i, radius * t / vmax) for i in range(len(axes))))
        c.add(f'<polygon points="{ring}" fill="none" stroke="{c.theme.line}" stroke-width="2"/>')
    for i, axis in enumerate(axes):
        ex, ey = point(i, radius)
        c.line(cx, cy, ex, ey, c.theme.line, 2)
        lx, ly = point(i, radius + 22)
        align = "center" if abs(lx - cx) < 30 else "left" if lx > cx else "right"
        bx = lx - 150 if align == "center" else lx if align == "left" else lx - 300
        # Labels straight above or below the centre sit clear of the spoke's end.
        ly += -14 if align == "center" and ly < cy else 14 if align == "center" else 0
        c.text((int(bx), int(ly) - 18, 300, 36), axis, "value", align=align, group="sa")
    colors = [c.theme.accent(0), mix(c.theme.muted, c.theme.bg, 0.1), c.theme.accent(2)]
    for s, name in enumerate(names):
        pts = [point(i, radius * max(0.0, table.get((axis, name), 0.0)) / vmax) for i, axis in enumerate(axes)]
        shape = " ".join(f"{px:.1f},{py:.1f}" for px, py in pts)
        color = colors[s % len(colors)]
        c.add(f'<polygon points="{shape}" fill="{color}" fill-opacity="0.22" stroke="{color}" stroke-width="5" stroke-linejoin="round"/>')
        for px, py in pts:
            c.circle(px, py, 7, color)
    if any(names):
        for s, name in enumerate(names):
            ly = y + 40 + s * 56
            c.circle(x + w - legend_w + 40, ly + 20, 12, colors[s % len(colors)])
            c.text((x + w - legend_w + 64, int(ly), legend_w - 70, 40), name or "Score", "label", align="left", group="sl")
    for t in ticks[-1:]:
        # The scale: the outer ring's value, just right of the top spoke (the first axis points straight up).
        c.text((int(cx) + 8, int(cy - radius * t / vmax) - 2, 90, 24), fmt_value(t, b.unit), "small", align="left", group="st")


CHARTS: dict[str, Callable[[Canvas, OpeningBuild, Box], None]] = {
    "line_annotated": line_annotated,
    "slope": slope,
    "dumbbell": dumbbell,
    "waterfall": waterfall,
    "tornado": tornado,
    "ranked_bar": ranked_bar,
    "heatmap": heatmap,
    "spider": spider,
}

__all__ = ["CHARTS", "esc", "fmt_value", "label_names", "series_names"]
