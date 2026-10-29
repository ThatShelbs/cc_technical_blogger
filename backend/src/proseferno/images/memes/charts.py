"""Chart jokes drawn by code from Claude's data, so they look like real charts (which is the joke)."""

from __future__ import annotations

import math
from typing import Any

from proseferno.images.base import ImageProviderError
from proseferno.images.memes.specs import MemeDatum
from proseferno.images.render import vega_to_png

PIE_COLORS = ["#ed6925", "#781c6d", "#f7d13d", "#cf4446", "#4a0c6b", "#fb9b06"]


def _shade(color: str, factor: float) -> str:
    """Lighten (factor > 1) or darken (factor < 1) a hex color."""
    r, g, b = (int(color[i : i + 2], 16) for i in (1, 3, 5))
    if factor >= 1:
        r, g, b = (round(c + (255 - c) * (factor - 1)) for c in (r, g, b))
    else:
        r, g, b = (round(c * factor) for c in (r, g, b))
    return f"#{min(r, 255):02x}{min(g, 255):02x}{min(b, 255):02x}"


def pie_slices(data: list[MemeDatum]) -> list[tuple[str, float]]:
    slices = [(d.label.strip() or "Other", max(0.0, d.value)) for d in data if d.value > 0][:6]
    total = sum(v for _, v in slices)
    if len(slices) < 2 or total <= 0:
        raise ImageProviderError("The pie chart needs at least two slices with positive values.")
    return [(label, 100 * v / total) for label, v in slices]


def pie_svg(
    slices: list[tuple[str, float]],
    colors: list[str] = PIE_COLORS,
    *,
    cx: float = 430,
    cy: float = 470,
    rx: float = 330,
    ry: float = 190,
    depth: float = 70,
) -> str:
    """A shiny, tilted, exploded 3D pie: the chart every data person loves to hate."""
    largest = max(range(len(slices)), key=lambda i: slices[i][1])
    parts: list[str] = [
        '<defs><filter id="pie-shadow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="14"/></filter>',
    ]
    for i, color in enumerate(colors):
        parts.append(
            f'<linearGradient id="pie-top-{i}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{_shade(color, 1.35)}"/>'
            f'<stop offset="1" stop-color="{color}"/></linearGradient>'
        )
    parts.append("</defs>")
    parts.append(
        f'<ellipse cx="{cx + 12}" cy="{cy + depth + 26}" rx="{rx * 1.04}" ry="{ry * 0.62}" fill="#000" opacity="0.22" filter="url(#pie-shadow)"/>'
    )

    def point(theta: float, ox: float, oy: float, drop: float = 0) -> str:
        return f"{cx + ox + rx * math.cos(theta):.1f},{cy + oy + drop + ry * math.sin(theta):.1f}"

    pieces = []
    angle = -math.pi / 2
    for i, (_, pct) in enumerate(slices):
        span = 2 * math.pi * pct / 100
        a0, a1 = angle, angle + span
        mid = (a0 + a1) / 2
        explode = 46 if i == largest else 6
        pieces.append((math.sin(mid), i, a0, a1, explode * math.cos(mid), explode * math.sin(mid) * ry / rx))
        angle = a1
    for _, i, a0, a1, ox, oy in sorted(pieces):
        color = colors[i % len(colors)]
        large = 1 if a1 - a0 > math.pi else 0
        # Front wall: the part of the arc facing the viewer (0..pi in screen angles, also 2pi..3pi after wrapping).
        for lo, hi in ((0.0, math.pi), (2 * math.pi, 3 * math.pi)):
            t0, t1 = max(a0, lo), min(a1, hi)
            if t1 > t0:
                parts.append(
                    f'<path d="M{point(t0, ox, oy)} A{rx},{ry} 0 0 1 {point(t1, ox, oy)} L{point(t1, ox, oy, depth)} '
                    f'A{rx},{ry} 0 0 0 {point(t0, ox, oy, depth)} Z" fill="{_shade(color, 0.62)}" stroke="#ffffff" stroke-width="1.5"/>'
                )
        parts.append(
            f'<path d="M{cx + ox:.1f},{cy + oy:.1f} L{point(a0, ox, oy)} A{rx},{ry} 0 {large} 1 {point(a1, ox, oy)} Z" '
            f'fill="url(#pie-top-{i % len(colors)})" stroke="#ffffff" stroke-width="3" stroke-linejoin="round"/>'
        )
    parts.append(f'<ellipse cx="{cx - 70}" cy="{cy - 70}" rx="{rx * 0.55}" ry="{ry * 0.3}" fill="#ffffff" opacity="0.16"/>')
    return "".join(parts)


def pie_label_points(
    slices: list[tuple[str, float]], *, cx: float = 430, cy: float = 470, rx: float = 330, ry: float = 190
) -> list[tuple[float, float]]:
    largest = max(range(len(slices)), key=lambda i: slices[i][1])
    points = []
    angle = -math.pi / 2
    for i, (_, pct) in enumerate(slices):
        span = 2 * math.pi * pct / 100
        mid = angle + span / 2
        explode = 46 if i == largest else 6
        points.append((cx + (0.6 * rx + explode) * math.cos(mid), cy + (0.6 * ry + explode * ry / rx) * math.sin(mid)))
        angle += span
    return points


def bell_curve_svg(
    *, left: float = 100, right: float = 1300, center: float = 700, sigma: float = 150, base: float = 780, peak: float = 520
) -> str:
    def y(x: float) -> float:
        return base - peak * math.exp(-(((x - center) / sigma) ** 2) / 2)

    bands = ["#f7d13d", "#fb9b06", "#ed6925", "#cf4446", "#cf4446", "#ed6925", "#fb9b06", "#f7d13d"]
    parts = []
    for k, color in enumerate(bands):
        x0, x1 = max(left, center + (k - 4) * sigma), min(right, center + (k - 3) * sigma)
        xs = [x0 + (x1 - x0) * t / 30 for t in range(31)]
        pts = " ".join(f"{x:.1f},{y(x):.1f}" for x in xs)
        parts.append(f'<polygon points="{x0:.1f},{base} {pts} {x1:.1f},{base}" fill="{color}" opacity="0.5"/>')
    curve = " ".join(f"{x:.1f},{y(x):.1f}" for x in range(int(left), int(right) + 1, 8))
    parts.append(f'<polyline points="{curve}" fill="none" stroke="#1b0c41" stroke-width="6" stroke-linejoin="round"/>')
    parts.append(f'<line x1="{left}" y1="{base}" x2="{right}" y2="{base}" stroke="#1b0c41" stroke-width="4"/>')
    for k in range(-3, 4):
        x = center + k * sigma
        parts.append(
            f'<line x1="{x}" y1="{base}" x2="{x}" y2="{y(x):.1f}" stroke="#1b0c41" stroke-width="2" stroke-dasharray="6 6" opacity="0.5"/>'
        )
    return "".join(parts)


def spurious_png(texts: dict[str, str], data: list[MemeDatum]) -> tuple[bytes, int, int]:
    """A dead-serious dual-axis line chart of two series that have nothing to do with each other."""
    names: list[str] = []
    for d in data:
        if d.series not in names:
            names.append(d.series)
    if len(names) < 2:
        raise ImageProviderError("The correlation chart needs two series.")
    rows = [{"x": d.label, "value": d.value, "series": "a" if d.series == names[0] else "b"} for d in data if d.series in names[:2]]
    order = list(dict.fromkeys(r["x"] for r in rows))

    def series(name: str, color: str, title: str, orient: str) -> dict[str, Any]:
        return {
            "transform": [{"filter": f"datum.series == '{name}'"}],
            "encoding": {
                "y": {
                    "field": "value",
                    "type": "quantitative",
                    "scale": {"zero": False},
                    "axis": {"title": title, "titleColor": color, "labelColor": color, "orient": orient, "titleFontSize": 15},
                }
            },
            "layer": [
                {"mark": {"type": "line", "color": color, "strokeWidth": 4, "interpolate": "monotone"}},
                {"mark": {"type": "point", "color": color, "filled": True, "size": 90}},
            ],
        }

    spec = {
        "width": 780,
        "height": 380,
        "padding": 24,
        "title": {
            "text": texts.get("title", ""),
            "subtitle": texts.get("note", ""),
            "fontSize": 24,
            "subtitleFontSize": 16,
            "subtitleColor": "#5b4a6b",
            "subtitlePadding": 8,
            "offset": 18,
        },
        "data": {"values": rows},
        "encoding": {"x": {"field": "x", "type": "ordinal", "sort": order, "axis": {"title": None, "labelAngle": 0, "labelFontSize": 13}}},
        "layer": [
            series("a", "#ed6925", texts.get("series_a", ""), "left"),
            series("b", "#781c6d", texts.get("series_b", ""), "right"),
        ],
        "resolve": {"scale": {"y": "independent"}},
        "config": {"axis": {"gridColor": "#efe6f5", "domainColor": "#c8bcd6"}},
    }
    return vega_to_png(spec, scale=2)
