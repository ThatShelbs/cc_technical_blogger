# ruff: noqa: E501
"""Faces: eyes, brows, mouths and the little extras (blush, sweat, tears, sparkles) shared by every character.

A face is drawn around a center point in a unit ``u`` (1.0 = a full-size head), so the same expression reads the
same on a ghost, a dog or a person. Expressions are named, and every name is a fixed recipe: the model picks the
name, the code draws it, so a "blank stare" is the same blank stare in every panel.
"""

from __future__ import annotations

from dataclasses import dataclass

from inferno_ghostwriter.images.kit.style import Coat, KitStyle


@dataclass(frozen=True)
class FaceSpec:
    eyes: str
    brows: str
    mouth: str
    extras: tuple[str, ...] = ()
    blush: bool = False
    look: float = 0.0  # where the eyes look: -1 left .. 1 right (before facing is applied)
    look_up: float = 0.0


EXPRESSIONS: dict[str, FaceSpec] = {
    "happy": FaceSpec("open", "none", "smile", blush=True),
    "beaming": FaceSpec("happy", "raised", "open_smile", ("sparkles",), blush=True),
    "smug": FaceSpec("half", "skeptic", "smirk"),
    "blank": FaceSpec("dot", "none", "flat"),
    "hopeful": FaceSpec("sparkle", "raised", "small_open", blush=True),
    "nervous": FaceSpec("open", "worried", "wobbly", ("sweat",)),
    "worried": FaceSpec("open", "worried", "frown", ("sweat",)),
    "shocked": FaceSpec("wide", "raised", "o"),
    "panic": FaceSpec("wide", "raised", "scream", ("sweat", "sweat2")),
    "calm": FaceSpec("closed", "none", "smile", blush=True),
    "thinking": FaceSpec("open", "skeptic", "hmm", ("question",), look=-0.6, look_up=0.8),
    "mind_blown": FaceSpec("wide", "raised", "o", ("rays", "sparkles")),
    "deadpan": FaceSpec("half", "flat", "flat"),
    "sad": FaceSpec("teary", "worried", "frown"),
    "nope": FaceSpec("squeeze", "angry", "frown"),
    "grumpy": FaceSpec("half", "angry", "frown"),
    "determined": FaceSpec("open", "angry", "smirk"),
    "sweating": FaceSpec("wide", "worried", "wobbly", ("sweat", "sweat2", "sweat3")),
    "love": FaceSpec("sparkle", "raised", "open_smile", ("hearts",), blush=True),
    "sleepy": FaceSpec("closed", "flat", "o", ("zzz",)),
    "content": FaceSpec("closed", "none", "tiny", blush=True),
    "frozen_smile": FaceSpec("wide", "worried", "smile", ("sweat",), blush=True),
}
EXPRESSION_HINTS = {
    "happy": "friendly smile",
    "beaming": "overjoyed, eyes squeezed happy",
    "smug": "half-lidded, lopsided smirk",
    "blank": "dead, expressionless stare",
    "hopeful": "big sparkly hopeful eyes, small open smile",
    "nervous": "forced wobbly smile, sweat drop",
    "worried": "brows up, small frown, sweat",
    "shocked": "wide eyes, O mouth",
    "panic": "wide eyes, screaming, sweating",
    "calm": "eyes closed, serene smile",
    "thinking": "looking up, one brow raised",
    "mind_blown": "wide eyes, rays and sparkles",
    "deadpan": "half-lidded, flat mouth",
    "sad": "teary eyes, frown",
    "nope": "eyes squeezed shut in disgust",
    "grumpy": "half-lidded and frowning",
    "determined": "focused brows, smirk",
    "sweating": "wide eyes, lots of sweat",
    "frozen_smile": "still smiling, but the eyes have realized something (the 'right?' panel)",
    "love": "sparkly eyes, hearts",
    "sleepy": "eyes closed, zzz",
    "content": "eyes closed, tiny smile",
}


def f(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".") if abs(v - round(v)) > 1e-6 else str(round(v))


def _eye(kind: str, x: float, y: float, u: float, color: str, white: str, line: str, side: int, lx: float, ly: float) -> str:
    sw = max(2.5, 4.2 * u)
    if kind == "open":
        rx, ry = 13 * u, 18 * u
        x += lx * 3 * u
        y -= ly * 3 * u
        return (
            f'<ellipse cx="{f(x)}" cy="{f(y)}" rx="{f(rx)}" ry="{f(ry)}" fill="{color}"/>'
            f'<circle cx="{f(x + 4.5 * u)}" cy="{f(y - 7 * u)}" r="{f(5.4 * u)}" fill="{white}"/>'
            f'<circle cx="{f(x - 4.5 * u)}" cy="{f(y + 6.5 * u)}" r="{f(2.4 * u)}" fill="{white}" opacity="0.85"/>'
        )
    if kind == "sparkle":
        rx, ry = 15.5 * u, 20.5 * u
        x += lx * 3 * u
        return (
            f'<ellipse cx="{f(x)}" cy="{f(y)}" rx="{f(rx)}" ry="{f(ry)}" fill="{color}"/>'
            f'<circle cx="{f(x + 5 * u)}" cy="{f(y - 7.5 * u)}" r="{f(7 * u)}" fill="{white}"/>'
            f'<circle cx="{f(x - 5.5 * u)}" cy="{f(y + 6 * u)}" r="{f(3.6 * u)}" fill="{white}"/>'
            f'<circle cx="{f(x + 6 * u)}" cy="{f(y + 9 * u)}" r="{f(1.8 * u)}" fill="{white}"/>'
        )
    if kind == "wide":
        rx, ry = 16 * u, 20 * u
        px = x + lx * 5 * u
        py = y - ly * 5 * u
        return (
            f'<ellipse cx="{f(x)}" cy="{f(y)}" rx="{f(rx)}" ry="{f(ry)}" fill="#ffffff" stroke="{line}" stroke-width="{f(sw * 0.8)}"/>'
            f'<circle cx="{f(px)}" cy="{f(py)}" r="{f(6.5 * u)}" fill="{color}"/>'
            f'<circle cx="{f(px + 2 * u)}" cy="{f(py - 2.5 * u)}" r="{f(2 * u)}" fill="{white}"/>'
        )
    if kind == "dot":
        return f'<circle cx="{f(x + lx * 2 * u)}" cy="{f(y + 2 * u)}" r="{f(6 * u)}" fill="{color}"/>'
    if kind == "half":
        rx, ry = 13 * u, 16 * u
        x += lx * 3 * u
        lid = y - 2 * u
        return (
            f'<path d="M{f(x - rx)},{f(lid)} A{f(rx)},{f(ry)} 0 0 0 {f(x + rx)},{f(lid)} Z" fill="{color}"/>'
            f'<circle cx="{f(x + 4 * u)}" cy="{f(lid + 5 * u)}" r="{f(3.4 * u)}" fill="{white}"/>'
            f'<path d="M{f(x - rx - 3 * u)},{f(lid - 1 * u)} L{f(x + rx + 3 * u)},{f(lid - 1 * u)}" stroke="{color}" '
            f'stroke-width="{f(sw)}" stroke-linecap="round"/>'
        )
    if kind == "happy":
        return (
            f'<path d="M{f(x - 12 * u)},{f(y + 5 * u)} Q{f(x)},{f(y - 15 * u)} {f(x + 12 * u)},{f(y + 5 * u)}" fill="none" '
            f'stroke="{color}" stroke-width="{f(sw * 1.25)}" stroke-linecap="round"/>'
        )
    if kind == "closed":
        return (
            f'<path d="M{f(x - 12 * u)},{f(y - 1 * u)} Q{f(x)},{f(y + 11 * u)} {f(x + 12 * u)},{f(y - 1 * u)}" fill="none" '
            f'stroke="{color}" stroke-width="{f(sw * 1.2)}" stroke-linecap="round"/>'
        )
    if kind == "squeeze":
        d = 1 if side > 0 else -1
        # Chevrons pointing toward the nose: > on the left eye, < on the right.
        return (
            f'<path d="M{f(x - 10 * u * d)},{f(y - 10 * u)} L{f(x + 8 * u * d)},{f(y)} L{f(x - 10 * u * d)},{f(y + 10 * u)}" '
            f'fill="none" stroke="{color}" stroke-width="{f(sw * 1.2)}" stroke-linecap="round" stroke-linejoin="round"/>'
        )
    if kind == "teary":
        return (
            _eye("sparkle", x, y, u, color, white, line, side, lx, ly)
            + f'<path d="M{f(x - 4 * u)},{f(y + 20 * u)} q{f(-4 * u)},{f(10 * u)} 0,{f(16 * u)} q{f(4 * u)},{f(-6 * u)} 0,{f(-16 * u)} Z" '
            f'fill="#7cc7ff" stroke="#3a7fc0" stroke-width="{f(sw * 0.4)}"/>'
        )
    return ""


def _brow(kind: str, x: float, y: float, u: float, color: str, side: int) -> str:
    """One brow over an eye at (x, y); ``side`` is -1 for the viewer's left eye, 1 for the right."""
    if kind == "none":
        return ""
    sw = max(2.5, 4.4 * u)
    by = y - 30 * u
    inner, outer = x - side * 11 * u, x + side * 11 * u
    if kind == "raised":
        d = f"M{f(outer)},{f(by - 2 * u)} Q{f(x)},{f(by - 11 * u)} {f(inner)},{f(by - 3 * u)}"
    elif kind == "worried":
        d = f"M{f(outer)},{f(by + 3 * u)} Q{f(x)},{f(by - 2 * u)} {f(inner)},{f(by - 9 * u)}"
    elif kind == "angry":
        d = f"M{f(outer)},{f(by - 7 * u)} L{f(inner)},{f(by + 4 * u)}"
    elif kind == "flat":
        d = f"M{f(outer)},{f(by + 2 * u)} L{f(inner)},{f(by + 2 * u)}"
    elif kind == "skeptic":
        d = (
            f"M{f(outer)},{f(by - 4 * u)} Q{f(x)},{f(by - 14 * u)} {f(inner)},{f(by - 6 * u)}"
            if side > 0
            else f"M{f(outer)},{f(by + 3 * u)} L{f(inner)},{f(by + 3 * u)}"
        )
    else:
        return ""
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{f(sw)}" stroke-linecap="round"/>'


def _mouth(kind: str, x: float, y: float, u: float, color: str, animal: bool) -> str:
    sw = max(2.5, 4.6 * u)
    stroke = f'fill="none" stroke="{color}" stroke-width="{f(sw)}" stroke-linecap="round" stroke-linejoin="round"'
    tongue = "#ff7f8f"
    if kind == "smile":
        if animal:
            return f'<path d="M{f(x - 13 * u)},{f(y)} Q{f(x - 6.5 * u)},{f(y + 9 * u)} {f(x)},{f(y)} Q{f(x + 6.5 * u)},{f(y + 9 * u)} {f(x + 13 * u)},{f(y)}" {stroke}/>'
        return f'<path d="M{f(x - 14 * u)},{f(y)} Q{f(x)},{f(y + 14 * u)} {f(x + 14 * u)},{f(y)}" {stroke}/>'
    if kind == "tiny":
        return f'<path d="M{f(x - 7 * u)},{f(y)} Q{f(x)},{f(y + 7 * u)} {f(x + 7 * u)},{f(y)}" {stroke}/>'
    if kind in ("open_smile", "small_open"):
        w = 18 * u if kind == "open_smile" else 12 * u
        h = 24 * u if kind == "open_smile" else 16 * u
        return (
            f'<path d="M{f(x - w)},{f(y - 2 * u)} Q{f(x)},{f(y + h)} {f(x + w)},{f(y - 2 * u)} Z" fill="{color}" stroke="{color}" '
            f'stroke-width="{f(sw * 0.6)}" stroke-linejoin="round"/>'
            f'<path d="M{f(x - w * 0.5)},{f(y + h * 0.42)} Q{f(x)},{f(y + h * 0.2)} {f(x + w * 0.5)},{f(y + h * 0.42)} '
            f'Q{f(x)},{f(y + h * 0.62)} {f(x - w * 0.5)},{f(y + h * 0.42)} Z" fill="{tongue}"/>'
        )
    if kind == "smirk":
        return f'<path d="M{f(x - 12 * u)},{f(y + 5 * u)} Q{f(x + 4 * u)},{f(y + 10 * u)} {f(x + 15 * u)},{f(y - 4 * u)}" {stroke}/>'
    if kind == "flat":
        return f'<path d="M{f(x - 10 * u)},{f(y + 4 * u)} L{f(x + 10 * u)},{f(y + 4 * u)}" {stroke}/>'
    if kind == "hmm":
        return f'<path d="M{f(x - 8 * u)},{f(y + 6 * u)} L{f(x + 9 * u)},{f(y + 2 * u)}" {stroke}/>'
    if kind == "o":
        return f'<ellipse cx="{f(x)}" cy="{f(y + 6 * u)}" rx="{f(7 * u)}" ry="{f(9.5 * u)}" fill="{color}"/>'
    if kind == "scream":
        return (
            f'<ellipse cx="{f(x)}" cy="{f(y + 10 * u)}" rx="{f(14 * u)}" ry="{f(19 * u)}" fill="{color}"/>'
            f'<ellipse cx="{f(x)}" cy="{f(y + 21 * u)}" rx="{f(8 * u)}" ry="{f(6 * u)}" fill="{tongue}"/>'
        )
    if kind == "frown":
        return f'<path d="M{f(x - 11 * u)},{f(y + 9 * u)} Q{f(x)},{f(y - 3 * u)} {f(x + 11 * u)},{f(y + 9 * u)}" {stroke}/>'
    if kind == "wobbly":
        s = 5.5 * u
        return (
            f'<path d="M{f(x - 16 * u)},{f(y + 4 * u)} q{f(s / 2)},{f(-s)} {f(s)},0 q{f(s / 2)},{f(s)} {f(s)},0 '
            f'q{f(s / 2)},{f(-s)} {f(s)},0 q{f(s / 2)},{f(s)} {f(s)},0 q{f(s / 2)},{f(-s)} {f(s)},0 q{f(s / 2)},{f(s)} {f(s)},0" {stroke}/>'
        )
    return ""


def sparkle_path(x: float, y: float, r: float) -> str:
    """A four-point sparkle centered at (x, y)."""
    k = r * 0.28
    return (
        f"M{f(x)},{f(y - r)} Q{f(x + k)},{f(y - k)} {f(x + r)},{f(y)} Q{f(x + k)},{f(y + k)} {f(x)},{f(y + r)} "
        f"Q{f(x - k)},{f(y + k)} {f(x - r)},{f(y)} Q{f(x - k)},{f(y - k)} {f(x)},{f(y - r)} Z"
    )


def drop_path(x: float, y: float, s: float) -> str:
    """A sweat drop with its tip at (x, y)."""
    return f"M{f(x)},{f(y)} C{f(x + 7 * s)},{f(y + 10 * s)} {f(x + 8 * s)},{f(y + 18 * s)} {f(x)},{f(y + 19 * s)} C{f(x - 8 * s)},{f(y + 18 * s)} {f(x - 7 * s)},{f(y + 10 * s)} {f(x)},{f(y)} Z"


def heart_path(x: float, y: float, s: float) -> str:
    return (
        f"M{f(x)},{f(y + 6 * s)} C{f(x - 10 * s)},{f(y - 2 * s)} {f(x - 8 * s)},{f(y - 12 * s)} {f(x)},{f(y - 6 * s)} "
        f"C{f(x + 8 * s)},{f(y - 12 * s)} {f(x + 10 * s)},{f(y - 2 * s)} {f(x)},{f(y + 6 * s)} Z"
    )


def extras(names: tuple[str, ...], head_x: float, head_y: float, head_r: float, u: float, coat: Coat, line: str) -> tuple[str, str]:
    """(behind the head, in front of the head) decorations around a head of radius ``head_r`` centered at (x, y)."""
    back, front = [], []
    sw = max(2.0, 3.0 * u)
    for name in names:
        if name in ("sweat", "sweat2", "sweat3"):
            k = {"sweat": 0, "sweat2": 1, "sweat3": 2}[name]
            angle_x = (0.78, -0.82, 0.55)[k]
            dx = head_x + head_r * angle_x
            dy = head_y - head_r * (0.42, 0.3, 0.75)[k]
            s = 1.25 * u
            front.append(
                f'<path d="{drop_path(dx, dy, s)}" fill="#9bd8ff" stroke="#3a86c8" stroke-width="{f(sw * 0.8)}"/>'
                f'<ellipse cx="{f(dx - 2 * s)}" cy="{f(dy + 12 * s)}" rx="{f(1.8 * s)}" ry="{f(3 * s)}" fill="#ffffff" opacity="0.8"/>'
            )
        elif name == "sparkles":
            for sx, sy, sr in ((1.15, -0.85, 13), (-1.2, -0.55, 9), (1.3, 0.15, 7)):
                front.append(
                    f'<path d="{sparkle_path(head_x + head_r * sx, head_y + head_r * sy, sr * u)}" fill="{coat.accent}" '
                    f'stroke="{line}" stroke-width="{f(sw * 0.5)}"/>'
                )
        elif name == "hearts":
            for hx_, hy_, hs in ((1.15, -0.85, 1.3), (-1.15, -0.7, 1.0)):
                front.append(f'<path d="{heart_path(head_x + head_r * hx_, head_y + head_r * hy_, hs * u)}" fill="#ff5d7a"/>')
        elif name == "rays":
            rays = []
            for i in range(10):
                import math

                a = -math.pi / 2 + (i - 4.5) * 0.3
                r0, r1 = head_r * 1.18, head_r * (1.55 if i % 2 else 1.4)
                rays.append(
                    f'<path d="M{f(head_x + math.cos(a) * r0)},{f(head_y + math.sin(a) * r0)} '
                    f'L{f(head_x + math.cos(a) * r1)},{f(head_y + math.sin(a) * r1)}" stroke="{coat.accent}" '
                    f'stroke-width="{f(7 * u)}" stroke-linecap="round"/>'
                )
            back.append("".join(rays))
        elif name == "question":
            qx, qy = head_x + head_r * 0.95, head_y - head_r * 1.05
            front.append(
                f'<path d="M{f(qx - 9 * u)},{f(qy - 6 * u)} q0,{f(-13 * u)} {f(11 * u)},{f(-13 * u)} q{f(11 * u)},0 {f(11 * u)},{f(11 * u)} '
                f'q0,{f(8 * u)} {f(-10 * u)},{f(14 * u)} l0,{f(5 * u)}" fill="none" stroke="{line}" stroke-width="{f(5.5 * u)}" '
                f'stroke-linecap="round"/><circle cx="{f(qx + 1 * u)}" cy="{f(qy + 22 * u)}" r="{f(3.6 * u)}" fill="{line}"/>'
            )
        elif name == "zzz":
            zx, zy = head_x + head_r * 0.9, head_y - head_r * 0.9
            for i, s in enumerate((9, 12, 15)):
                x0, y0 = zx + i * 16 * u, zy - i * 20 * u
                front.append(
                    f'<path d="M{f(x0)},{f(y0)} h{f(s * u)} l{f(-s * u)},{f(s * u)} h{f(s * u)}" fill="none" stroke="{line}" '
                    f'stroke-width="{f(3.5 * u)}" stroke-linecap="round" stroke-linejoin="round"/>'
                )
    return "".join(back), "".join(front)


def draw_face(
    expression: str,
    cx: float,
    cy: float,
    u: float,
    coat: Coat,
    style: KitStyle,
    *,
    spacing: float = 30.0,
    mouth_dy: float = 34.0,
    animal: bool = False,
    eye_color: str | None = None,
    blush_dy: float = 14.0,
) -> str:
    """The face for one expression, centered on the eyes' midpoint (cx, cy)."""
    spec = EXPRESSIONS.get(expression, EXPRESSIONS["happy"])
    color = eye_color or coat.eye
    line = coat.line if coat.line != "none" else color
    white = "#ffffff"
    parts = []
    if (spec.blush or style.blush) and style.blush and coat.cheek != coat.top:
        for side in (-1, 1):
            parts.append(
                f'<ellipse cx="{f(cx + side * (spacing + 13) * u)}" cy="{f(cy + blush_dy * u)}" rx="{f(11 * u)}" ry="{f(6.5 * u)}" '
                f'fill="{coat.cheek}" opacity="{0.75 if spec.blush else 0.4}"/>'
            )
    for side in (-1, 1):
        ex = cx + side * spacing * u
        parts.append(_eye(spec.eyes, ex, cy, u, color, white, line, side, spec.look, spec.look_up))
        parts.append(_brow(spec.brows, ex, cy, u, color, side))
    parts.append(_mouth(spec.mouth, cx, cy + mouth_dy * u, u, color, animal))
    return "".join(p for p in parts if p)
