"""Fills and outlines for kit shapes in a look's treatment (flat, soft gradient, 3D volume, halftone, line, marker).

Every shape is painted through a ``Painter`` so one character is consistent: the same light direction, outline weight
and shading on its head, body, arms and props. Gradient ids are unique per painter (``prefix``), so many characters
can share one SVG.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from inferno_ghostwriter.images.kit.face import f
from inferno_ghostwriter.images.kit.style import KitStyle
from inferno_ghostwriter.images.palettes import mix


@dataclass
class Painter:
    style: KitStyle
    line: str
    prefix: str
    scale: float = 1.0  # line widths are divided by it, so outlines keep their weight after the character is scaled
    ground: str = "none"  # line looks: the paper color that fills shapes, so linework stays opaque
    defs: list[str] = field(default_factory=list)
    _n: int = 0

    @property
    def width(self) -> float:
        return self.style.outline / max(self.scale, 0.2)

    def _id(self, what: str) -> str:
        self._n += 1
        return f"{self.prefix}-{what}{self._n}"

    def gradient(self, top: str, bottom: str) -> str:
        """A fill reference for a shape lit from the upper left, in this look's shading."""
        s = self.style.shading
        if s in ("flat", "halftone", "line", "marker") or (top == bottom and s != "volume"):
            return mix(top, bottom, 0.35) if s != "line" else top
        gid = self._id("g")
        if s == "volume":
            self.defs.append(
                f'<radialGradient id="{gid}" cx="0.36" cy="0.3" r="0.85" fx="0.32" fy="0.24">'
                f'<stop offset="0" stop-color="{mix(top, "#ffffff", 0.45)}"/><stop offset="0.45" stop-color="{top}"/>'
                f'<stop offset="1" stop-color="{mix(bottom, "#000000", 0.28)}"/></radialGradient>'
            )
        else:
            self.defs.append(
                f'<linearGradient id="{gid}" x1="0" y1="0" x2="0.25" y2="1"><stop offset="0" stop-color="{top}"/>'
                f'<stop offset="0.38" stop-color="{top}"/><stop offset="1" stop-color="{bottom}"/></linearGradient>'
            )
        return f"url(#{gid})"

    def stroke_attrs(self, width_mult: float = 1.0, color: str | None = None) -> str:
        if not self.width or self.line == "none":
            return 'stroke="none"'
        return f'stroke="{color or self.line}" stroke-width="{f(self.width * width_mult)}" stroke-linejoin="round" stroke-linecap="round"'

    def shape(self, tag: str, top: str, bottom: str | None = None, *, outline: float = 1.0, extra: str = "") -> str:
        """``tag`` is an opening tag without its end, e.g. ``<path d="..."``; returns the painted element(s)."""
        bottom = bottom or top
        fill = self.ground if self.style.shading == "line" else self.gradient(top, bottom)
        if self.style.shading == "marker":
            fill = mix("#ffffff", top, 0.25) if top != "#ffffff" else "#ffffff"
        out = f'{tag} fill="{fill}" {self.stroke_attrs(outline)} {extra}/>'
        if self.style.shading == "halftone":
            out += f'{tag} fill="url(#{self._dots(mix(bottom, "#000000", 0.35))})" mask="url(#{self._fade()})" stroke="none"/>'
        if self.style.shading == "volume" and self.style.outline == 0:
            # A rim light on the shadow side reads as 3D.
            out += f'{tag} fill="none" stroke="{mix(top, "#ffffff", 0.55)}" stroke-width="{f(3 / max(self.scale, 0.2))}" opacity="0.5"/>'
        return out

    def _dots(self, color: str) -> str:
        pid = self._id("dots")
        step = 9 / max(self.scale, 0.2)
        self.defs.append(
            f'<pattern id="{pid}" width="{f(step)}" height="{f(step)}" patternUnits="userSpaceOnUse">'
            f'<circle cx="{f(step / 2)}" cy="{f(step / 2)}" r="{f(step * 0.26)}" fill="{color}"/></pattern>'
        )
        return pid

    def _fade(self) -> str:
        mid = self._id("fade")
        gid = self._id("fg")
        self.defs.append(
            f'<linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="1"><stop offset="0.45" stop-color="#000"/>'
            f'<stop offset="0.75" stop-color="#fff"/></linearGradient>'
            f'<mask id="{mid}" maskContentUnits="objectBoundingBox"><rect width="1" height="1" fill="url(#{gid})"/></mask>'
        )
        return mid

    def hose(self, d: str, color: str, width: float) -> str:
        """A rubber-hose limb along path ``d``: an outline stroke under a fill stroke, round ends."""
        out = ""
        if self.width and self.line != "none":
            out += (
                f'<path d="{d}" fill="none" stroke="{self.line}" stroke-width="{f(width + 2 * self.width)}" '
                f'stroke-linecap="round" stroke-linejoin="round"/>'
            )
        fill = color if self.style.shading != "line" else self.ground
        if self.style.shading == "marker":
            fill = "#ffffff"
        if fill != "none":
            out += f'<path d="{d}" fill="none" stroke="{fill}" stroke-width="{f(width)}" stroke-linecap="round" stroke-linejoin="round"/>'
        return out

    def highlight(self, cx: float, cy: float, rx: float, ry: float, angle: float = -28) -> str:
        if self.style.shading not in ("soft", "volume"):
            return ""
        return (
            f'<ellipse cx="{f(cx)}" cy="{f(cy)}" rx="{f(rx)}" ry="{f(ry)}" fill="#ffffff" opacity="0.38" '
            f'transform="rotate({f(angle)} {f(cx)} {f(cy)})"/>'
        )
