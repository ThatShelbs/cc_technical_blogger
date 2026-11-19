# ruff: noqa: E501
"""Set pieces and props for kit scenes: backdrops (meadow, burning room, space, street, office), furniture, the
expanding-brain heads, signs, buttons, screens and more. All drawn by code in the scene's scheme and look.

Each function draws into scene coordinates and returns SVG. ``Stage`` carries the scheme, look and a painter so every
piece in one picture shares its outline weight and shading.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from inferno_ghostwriter.images.kit.face import f, sparkle_path
from inferno_ghostwriter.images.kit.paint import Painter
from inferno_ghostwriter.images.kit.style import INK_DARK, KitStyle, blueprint_ground, kit_style
from inferno_ghostwriter.images.palettes import Scheme, mix, scheme

Box = tuple[float, float, float, float]

PROP_HINTS = {
    "laptop": "an open laptop on the floor or table",
    "table": "a small table",
    "desk": "an office desk",
    "mug": "a coffee mug on a surface",
    "chart_screen": "a monitor showing a rising or falling chart",
    "server": "a server rack with blinking lights",
    "whiteboard": "a whiteboard on legs",
    "sign": "a blank sign on a post (its words come from a label)",
    "plant": "a potted plant",
    "rocket": "a small rocket",
    "cloud": "a fluffy cloud",
    "bucket": "a bucket",
    "gauge": "a dial gauge with a needle",
    "magnet": "a big horseshoe magnet",
    "funnel": "a funnel",
    "lightbulb": "a glowing light bulb",
    "trophy": "a trophy",
    "box": "a cardboard box",
    "stack": "a tall wobbly stack of papers",
    "fire": "a small campfire-style flame",
    "door": "a door",
    "ladder": "a ladder",
    "bridge": "a little bridge",
    "puzzle": "two puzzle pieces",
    "crystal_ball": "a crystal ball on a stand",
    "telescope": "a telescope on a tripod",
    "maze": "a small hedge maze",
    "balloon": "a floating balloon",
    "butterfly": "a glowing butterfly",
    "planet": "a planet with a ring",
}


@dataclass
class Stage:
    sch: Scheme
    look: str = "inferno_flat"
    prefix: str = "st"
    painter: Painter = field(init=False)
    style: KitStyle = field(init=False)
    rng: random.Random = field(default_factory=lambda: random.Random(7))

    def __post_init__(self) -> None:
        self.style = kit_style(self.look)
        line = self.style.ink or INK_DARK
        ground = "none"
        if self.style.shading == "line":
            ground = blueprint_ground(self.sch)
            line = mix(ground, "#ffffff", 0.85)
        self.painter = Painter(self.style, line, self.prefix, ground=ground)

    @property
    def p(self) -> Painter:
        return self.painter

    def defs(self) -> str:
        return f"<defs>{''.join(self.painter.defs)}</defs>" if self.painter.defs else ""


# -- backdrops ----------------------------------------------------------------------------------------------------------


def gradient_rect(st: Stage, box: Box, top: str, bottom: str, *, vertical: bool = True) -> str:
    x, y, w, h = box
    gid = f"{st.prefix}-bg{st.rng.randrange(1_000_000)}"
    x2, y2 = ("0", "1") if vertical else ("1", "0")
    st.p.defs.append(
        f'<linearGradient id="{gid}" x1="0" y1="0" x2="{x2}" y2="{y2}"><stop offset="0" stop-color="{top}"/>'
        f'<stop offset="1" stop-color="{bottom}"/></linearGradient>'
    )
    return f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" fill="url(#{gid})"/>'


def wash(st: Stage, box: Box, body: str) -> str:
    """A backdrop in the look's treatment. Blueprint draws pale linework, so its settings go under a deep blueprint
    wash with a faint grid (the setting still shows through), and the pale characters read on it."""
    if st.style.shading != "line":
        return body
    x, y, w, h = box
    navy = blueprint_ground(st.sch)
    grid = mix(navy, "#ffffff", 0.6)
    lines = "".join(f"M{f(x + k)},{f(y)} V{f(y + h)} " for k in range(0, int(w) + 1, 48))
    lines += "".join(f"M{f(x)},{f(y + k)} H{f(x + w)} " for k in range(0, int(h) + 1, 48))
    return (
        f'{body}<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" fill="{navy}" opacity="0.8"/>'
        f'<path d="{lines}" stroke="{grid}" stroke-width="1.5" opacity="0.18" fill="none"/>'
    )


def plain(st: Stage, box: Box, tone: float = 0.0) -> str:
    """The scheme's surface with a gentle gradient (``tone`` shifts it toward the ramp)."""
    top = mix(st.sch.bg, st.sch.ramp[3], tone) if tone else st.sch.bg
    return wash(st, box, gradient_rect(st, box, top, mix(top, st.sch.bg2, 0.8)))


def meadow(st: Stage, box: Box, horizon: float = 0.62) -> str:
    """A sunlit meadow: pale sky, soft hills, grass tufts and a few flowers."""
    x, y, w, h = box
    hy = y + h * horizon
    # Always a sunny day: the meadow is a recognizable setting, not a palette surface.
    sky_top = mix("#bfe3ff", st.sch.ramp[-1], 0.15)
    sky_bottom = mix("#ffffff", st.sch.ramp[-2], 0.12)
    grass = ("#8fd16a", "#5fae4e") if st.sch.ramp_id != "viridis" else (st.sch.ramp[7], st.sch.ramp[6])
    out = [gradient_rect(st, (x, y, w, h * horizon + 4), sky_top, sky_bottom)]
    out.append(
        f'<circle cx="{f(x + w * 0.82)}" cy="{f(y + h * 0.16)}" r="{f(h * 0.08)}" fill="{mix(st.sch.ramp[-1], "#ffffff", 0.3)}" opacity="0.9"/>'
    )
    for cx_, r_ in ((0.2, 0.18), (0.72, 0.24)):
        out.append(
            f'<ellipse cx="{f(x + w * cx_)}" cy="{f(hy + h * 0.06)}" rx="{f(w * r_ * 1.4)}" ry="{f(h * 0.16)}" fill="{mix(grass[0], sky_bottom, 0.45)}"/>'
        )
    out.append(gradient_rect(st, (x, hy, w, h - (hy - y)), grass[0], grass[1]))
    rng = random.Random(int(x + y))
    for _ in range(int(w / 70)):
        gx, gy = x + rng.random() * w, hy + 12 + rng.random() * (h - (hy - y) - 20)
        out.append(
            f'<path d="M{f(gx)},{f(gy)} l-6,-14 M{f(gx)},{f(gy)} l0,-18 M{f(gx)},{f(gy)} l6,-14" stroke="{mix(grass[1], "#000000", 0.2)}" '
            f'stroke-width="3" stroke-linecap="round"/>'
        )
    for _ in range(int(w / 160)):
        gx, gy = x + rng.random() * w, hy + 20 + rng.random() * (h - (hy - y) - 30)
        petal = rng.choice(("#ffffff", mix(st.sch.ramp[-2], "#ffffff", 0.3), "#ffb3c7"))
        out.append(
            "".join(
                f'<circle cx="{f(gx + 6 * math.cos(a))}" cy="{f(gy + 6 * math.sin(a))}" r="5" fill="{petal}"/>' for a in (0, 1.6, 3.2, 4.7)
            )
        )
        out.append(f'<circle cx="{f(gx)}" cy="{f(gy)}" r="4" fill="#f7d13d"/>')
    return wash(st, box, "".join(out))


def burning_room(st: Stage, box: Box, intensity: float = 1.0) -> str:
    """A cozy room engulfed in flames along the walls and ceiling, smoke under the ceiling."""
    x, y, w, h = box
    wall = "#f3d9a4" if st.sch.ramp_id != "viridis" else "#e8e2c8"
    out = [gradient_rect(st, box, mix(wall, "#5a3a22", 0.25), wall)]
    floor_y = y + h * 0.78
    out.append(f'<rect x="{f(x)}" y="{f(floor_y)}" width="{f(w)}" height="{f(h - (floor_y - y))}" fill="#a0673e"/>')
    for k in range(int(w / 70) + 1):
        out.append(
            f'<line x1="{f(x + k * 70)}" y1="{f(floor_y)}" x2="{f(x + k * 70 - 30)}" y2="{f(y + h)}" stroke="#7d4f2f" stroke-width="3"/>'
        )
    # A framed picture on the wall: a little sunny landscape, slightly crooked.
    px, py, pw, ph = x + w * 0.07, y + h * 0.28, w * 0.12, h * 0.17
    out.append(
        f'<g transform="rotate(-3 {f(px + pw / 2)} {f(py + ph / 2)})">'
        f'<rect x="{f(px)}" y="{f(py)}" width="{f(pw)}" height="{f(ph)}" fill="#bfe3ff" stroke="#6b4428" stroke-width="9"/>'
        f'<path d="M{f(px + 5)},{f(py + ph - 5)} Q{f(px + pw * 0.35)},{f(py + ph * 0.45)} {f(px + pw * 0.7)},{f(py + ph * 0.7)} T{f(px + pw - 5)},{f(py + ph * 0.6)} V{f(py + ph - 5)} Z" fill="#7cc46a"/>'
        f'<circle cx="{f(px + pw * 0.75)}" cy="{f(py + ph * 0.3)}" r="{f(ph * 0.12)}" fill="#fde68a"/></g>'
    )
    # Smoke band.
    smoke = "#4a3a3a"
    for k in range(9):
        out.append(
            f'<ellipse cx="{f(x + w * (k / 8))}" cy="{f(y + h * 0.04)}" rx="{f(w * 0.12)}" ry="{f(h * 0.12)}" fill="{smoke}" opacity="0.75"/>'
        )
    # Flames: on the floor across the room and up the left wall.
    flame_colors = (
        ("#cf4446", "#ed6925", "#fb9b06", "#f7d13d") if st.sch.ramp_id != "viridis" else ("#cf4446", "#ed6925", "#fb9b06", "#fde725")
    )
    rng = random.Random(3)
    for layer, color in enumerate(flame_colors):
        scale_ = (1.0 - layer * 0.22) * intensity
        for k in range(int(w / 90) + 2):
            fx_ = x + k * 90 + rng.uniform(-20, 20)
            out.append(flame(fx_, floor_y + 30, 80 * scale_, 170 * scale_ * rng.uniform(0.8, 1.25), color))
        for k in range(4):
            fy_ = y + h * 0.2 + k * h * 0.17
            out.append(flame(x + 30, fy_ + 110, 60 * scale_, 140 * scale_, color))
            out.append(flame(x + w - 30, fy_ + 110, 60 * scale_, 140 * scale_, color))
    return wash(st, box, "".join(out))


def flame(cx: float, base: float, width: float, height: float, color: str) -> str:
    """One stylized flame with its base center at (cx, base); a negative height hangs down (ceiling fire)."""
    w2 = width / 2
    tip = base - height
    return (
        f'<path d="M{f(cx - w2)},{f(base)} C{f(cx - w2)},{f(base - height * 0.45)} {f(cx - w2 * 0.2)},{f(base - height * 0.6)} '
        f"{f(cx)},{f(tip)} C{f(cx + w2 * 0.15)},{f(base - height * 0.55)} {f(cx + w2)},{f(base - height * 0.4)} "
        f'{f(cx + w2)},{f(base)} Z" fill="{color}" opacity="0.95"/>'
    )


def space(st: Stage, box: Box, seed: int = 5) -> str:
    x, y, w, h = box
    out = [gradient_rect(st, box, "#05030f", mix("#0b0b1f", st.sch.ramp[2], 0.35))]
    rng = random.Random(seed)
    out.append(
        f'<ellipse cx="{f(x + w * 0.65)}" cy="{f(y + h * 0.35)}" rx="{f(w * 0.35)}" ry="{f(h * 0.25)}" fill="{st.sch.ramp[3]}" opacity="0.25"/>'
    )
    for _ in range(int(w * h / 4000)):
        r_ = rng.choice((1.2, 1.6, 2.2, 3))
        out.append(
            f'<circle cx="{f(x + rng.random() * w)}" cy="{f(y + rng.random() * h)}" r="{r_}" fill="#ffffff" opacity="{rng.uniform(0.4, 1):.2f}"/>'
        )
    for _ in range(3):
        out.append(f'<path d="{sparkle_path(x + rng.random() * w, y + rng.random() * h, 9)}" fill="#ffffff" opacity="0.9"/>')
    return wash(st, box, "".join(out))


def planet(st: Stage, cx: float, cy: float, r: float) -> str:
    """A big planet (an Earth-like globe in the scheme's colors)."""
    ocean = "#2f6fb0" if st.sch.ramp_id != "viridis" else st.sch.ramp[3]
    land = "#5fae4e" if st.sch.ramp_id != "viridis" else st.sch.ramp[7]
    gid = f"{st.prefix}-pl{int(cx)}"
    st.p.defs.append(f'<clipPath id="{gid}"><circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}"/></clipPath>')
    continents = "".join(
        f'<path d="M{f(cx + dx * r)},{f(cy + dy * r)} c{f(r * 0.3)},{f(-r * 0.2)} {f(r * 0.5)},{f(r * 0.1)} {f(r * 0.35)},{f(r * 0.3)} '
        f'c{f(-r * 0.1)},{f(r * 0.2)} {f(-r * 0.4)},{f(r * 0.15)} {f(-r * 0.35)},{f(-r * 0.3)} Z" fill="{land}"/>'
        for dx, dy in ((-0.6, -0.4), (0.1, -0.6), (-0.2, 0.2), (0.4, 0.1), (-0.7, 0.4))
    )
    return (
        f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r * 1.08)}" fill="{mix(ocean, "#ffffff", 0.4)}" opacity="0.25"/>'
        f'<g clip-path="url(#{gid})"><circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}" fill="{ocean}"/>{continents}'
        f'<circle cx="{f(cx + r * 0.35)}" cy="{f(cy + r * 0.35)}" r="{f(r)}" fill="#000000" opacity="0.28"/></g>'
        f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}" fill="none" {st.p.stroke_attrs()}/>'
    )


def street(st: Stage, box: Box) -> str:
    """A sunny city street with soft, blurred buildings."""
    x, y, w, h = box
    out = [gradient_rect(st, box, mix("#ffffff", st.sch.ramp[-1], 0.3), "#ffffff")]
    rng = random.Random(11)
    bx = x
    while bx < x + w:
        bw = rng.uniform(110, 220)
        bh = rng.uniform(h * 0.35, h * 0.7)
        col = mix(rng.choice(st.sch.ramp[3:8]), "#ffffff", 0.55)
        out.append(f'<rect x="{f(bx)}" y="{f(y + h * 0.75 - bh)}" width="{f(bw - 8)}" height="{f(bh)}" fill="{col}"/>')
        for wy in range(int(bh / 50)):
            for wx in range(int(bw / 50)):
                out.append(
                    f'<rect x="{f(bx + 14 + wx * 46)}" y="{f(y + h * 0.75 - bh + 16 + wy * 50)}" width="24" height="28" fill="#ffffff" opacity="0.55"/>'
                )
        bx += bw
    out.append(f'<rect x="{f(x)}" y="{f(y + h * 0.75)}" width="{f(w)}" height="{f(h * 0.25)}" fill="#c9c6cf"/>')
    out.append(f'<rect x="{f(x)}" y="{f(y + h * 0.75)}" width="{f(w)}" height="10" fill="#e9e7ee"/>')
    return wash(st, box, "".join(out))


def office(st: Stage, box: Box) -> str:
    """A plain office: a wall, a window and a floor line."""
    x, y, w, h = box
    wall = mix(st.sch.bg, st.sch.ramp[-2], 0.12) if not st.sch.dark else mix(st.sch.bg, st.sch.ramp[2], 0.3)
    out = [gradient_rect(st, box, wall, mix(wall, "#000000", 0.06))]
    out.append(f'<rect x="{f(x)}" y="{f(y + h * 0.8)}" width="{f(w)}" height="{f(h * 0.2)}" fill="{mix(wall, "#5a3a22", 0.35)}"/>')
    wx, wy, ww, wh = x + w * 0.62, y + h * 0.18, w * 0.26, h * 0.32
    out.append(
        f'<rect x="{f(wx)}" y="{f(wy)}" width="{f(ww)}" height="{f(wh)}" fill="{mix("#bfe6ff", st.sch.ramp[-1], 0.2)}" {st.p.stroke_attrs(0.8)}/>'
    )
    out.append(f'<path d="M{f(wx + ww / 2)},{f(wy)} V{f(wy + wh)} M{f(wx)},{f(wy + wh / 2)} H{f(wx + ww)}" {st.p.stroke_attrs(0.6)}/>')
    return wash(st, box, "".join(out))


def garden(st: Stage, box: Box) -> str:
    """A soft garden at dusk."""
    x, y, w, h = box
    out = [gradient_rect(st, box, mix(st.sch.ramp[2], "#ffffff", 0.35), mix(st.sch.ramp[-2], "#ffffff", 0.45))]
    out.append(f'<rect x="{f(x)}" y="{f(y + h * 0.72)}" width="{f(w)}" height="{f(h * 0.28)}" fill="#6fb05a"/>')
    for k in range(6):
        out.append(f'<circle cx="{f(x + w * (k / 5))}" cy="{f(y + h * 0.7)}" r="{f(h * 0.12)}" fill="#4f9a4a"/>')
    return wash(st, box, "".join(out))


def basement(st: Stage, box: Box) -> str:
    x, y, w, h = box
    out = [gradient_rect(st, box, "#3a3240", "#1c1820")]
    out.append(
        f'<path d="M{f(x + w / 2)},{f(y)} L{f(x + w * 0.2)},{f(y + h)} L{f(x + w * 0.8)},{f(y + h)} Z" fill="#fff6c8" opacity="0.12"/>'
    )
    out.append(f'<line x1="{f(x + w / 2)}" y1="{f(y)}" x2="{f(x + w / 2)}" y2="{f(y + h * 0.12)}" stroke="#111" stroke-width="4"/>')
    out.append(f'<circle cx="{f(x + w / 2)}" cy="{f(y + h * 0.14)}" r="16" fill="#fff6c8"/>')
    for bx in (x + 30, x + w - 170):
        out.append(f'<rect x="{f(bx)}" y="{f(y + h * 0.55)}" width="140" height="120" fill="#7a5a3a" stroke="#3a2a1a" stroke-width="5"/>')
        out.append(
            f'<path d="M{f(bx)},{f(y + h * 0.55)} l140,120 M{f(bx + 140)},{f(y + h * 0.55)} l-140,120" stroke="#3a2a1a" stroke-width="4"/>'
        )
    out.append(f'<rect x="{f(x)}" y="{f(y + h * 0.85)}" width="{f(w)}" height="{f(h * 0.15)}" fill="#2a2430"/>')
    return wash(st, box, "".join(out))


BACKDROPS = {
    "plain": plain,
    "meadow": meadow,
    "burning_room": burning_room,
    "space": space,
    "street": street,
    "office": office,
    "garden": garden,
    "basement": basement,
}
BACKDROP_HINTS = {
    "plain": "the scheme's surface with a soft gradient",
    "meadow": "sunlit meadow and sky",
    "burning_room": "a room on fire",
    "space": "deep space with stars",
    "street": "a sunny city street",
    "office": "an office wall with a window",
    "garden": "a soft garden at dusk",
    "basement": "a dim basement with crates",
}


# -- furniture and objects -----------------------------------------------------------------------------------------------


def table(st: Stage, cx: float, top: float, width: float, height: float, color: str = "#a0673e") -> str:
    p = st.p
    leg = mix(color, "#000000", 0.2)
    return (
        p.shape(f'<rect x="{f(cx - width * 0.42)}" y="{f(top + 10)}" width="16" height="{f(height - 10)}" rx="4"', leg, leg)
        + p.shape(f'<rect x="{f(cx + width * 0.42 - 16)}" y="{f(top + 10)}" width="16" height="{f(height - 10)}" rx="4"', leg, leg)
        + p.shape(f'<rect x="{f(cx - width / 2)}" y="{f(top)}" width="{f(width)}" height="22" rx="8"', mix(color, "#ffffff", 0.12), color)
    )


def chair(st: Stage, cx: float, seat: float, color: str = "#7d4f2f") -> str:
    p = st.p
    return (
        p.shape(f'<rect x="{f(cx - 64)}" y="{f(seat - 120)}" width="18" height="190" rx="6"', color, color)
        + p.shape(f'<rect x="{f(cx - 64)}" y="{f(seat)}" width="128" height="18" rx="6"', mix(color, "#ffffff", 0.1), color)
        + p.shape(f'<rect x="{f(cx + 46)}" y="{f(seat + 10)}" width="16" height="60" rx="5"', color, color)
    )


def mug(st: Stage, cx: float, base: float, size: float = 1.0, color: str | None = None) -> str:
    p = st.p
    color = color or mix(st.sch.accent(0), "#ffffff", 0.15)
    w, h = 50 * size, 56 * size
    return (
        p.hose(
            f"M{f(cx + w / 2)},{f(base - h * 0.75)} C{f(cx + w)},{f(base - h * 0.75)} {f(cx + w)},{f(base - h * 0.25)} {f(cx + w / 2)},{f(base - h * 0.25)}",
            color,
            9 * size,
        )
        + p.shape(
            f'<rect x="{f(cx - w / 2)}" y="{f(base - h)}" width="{f(w)}" height="{f(h)}" rx="{f(10 * size)}"',
            color,
            mix(color, "#000000", 0.2),
        )
        + f'<path d="M{f(cx - 8 * size)},{f(base - h - 10)} q-8,-12 0,-24 M{f(cx + 10 * size)},{f(base - h - 10)} q-8,-12 0,-24" fill="none" stroke="#ffffff" stroke-width="4" stroke-linecap="round" opacity="0.6"/>'
    )


def laptop(st: Stage, cx: float, base: float, size: float = 1.0, facing: str = "left") -> str:
    """An open laptop seen from the side, its screen glowing toward ``facing``."""
    p = st.p
    s = -1 if facing == "left" else 1
    w, h = 150 * size, 100 * size
    screen = mix(st.sch.ramp[-2], "#ffffff", 0.3)
    return (
        p.shape(
            f'<path d="M{f(cx - w / 2)},{f(base)} L{f(cx + w / 2)},{f(base)} L{f(cx + w / 2 - 8)},{f(base - 12)} L{f(cx - w / 2 + 8)},{f(base - 12)} Z"',
            "#3a3346",
            "#2a2433",
        )
        + p.shape(
            f'<path d="M{f(cx - s * w * 0.42)},{f(base - 12)} L{f(cx - s * w * 0.55)},{f(base - 12 - h)} L{f(cx - s * w * 0.42 + s * 14)},{f(base - 16 - h)} L{f(cx - s * w * 0.3)},{f(base - 12)} Z"',
            "#2a2433",
            "#1c1820",
        )
        + f'<ellipse cx="{f(cx + s * w * 0.1)}" cy="{f(base - 40 * size)}" rx="{f(w * 0.45)}" ry="{f(h * 0.4)}" fill="{screen}" opacity="0.18"/>'
    )


def screen(st: Stage, box: Box, trend: str = "up") -> str:
    """A monitor showing a chart line."""
    x, y, w, h = box
    p = st.p
    out = p.shape(f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" rx="14"', "#2a2433", "#1c1820")
    out += f'<rect x="{f(x + 14)}" y="{f(y + 14)}" width="{f(w - 28)}" height="{f(h - 28)}" rx="6" fill="{mix("#ffffff", st.sch.ramp[-1], 0.15)}"/>'
    pts = [0.2, 0.35, 0.3, 0.5, 0.48, 0.7, 0.85] if trend == "up" else [0.85, 0.7, 0.74, 0.5, 0.45, 0.25, 0.12]
    poly = " ".join(f"{f(x + 30 + i * (w - 60) / (len(pts) - 1))},{f(y + h - 30 - v * (h - 60))}" for i, v in enumerate(pts))
    out += f'<polyline points="{poly}" fill="none" stroke="{st.sch.accent(0) if not st.sch.dark else st.sch.ramp[5]}" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>'
    out += p.shape(f'<rect x="{f(x + w / 2 - 14)}" y="{f(y + h)}" width="28" height="36"', "#2a2433", "#2a2433")
    out += p.shape(f'<rect x="{f(x + w / 2 - 60)}" y="{f(y + h + 32)}" width="120" height="14" rx="6"', "#2a2433", "#2a2433")
    return out


def sign_board(st: Stage, box: Box, fill: str = "#ffffff") -> str:
    """A blank sign: text goes on it from a label slot."""
    x, y, w, h = box
    return st.p.shape(f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" rx="10"', fill, mix(fill, "#000000", 0.05))


def folding_table(st: Stage, cx: float, top: float, width: float) -> str:
    p = st.p
    leg = "#6b6478"
    return (
        f'<path d="M{f(cx - width * 0.4)},{f(top + 10)} L{f(cx - width * 0.25)},{f(top + 230)} M{f(cx + width * 0.4)},{f(top + 10)} L{f(cx + width * 0.25)},{f(top + 230)}" stroke="{leg}" stroke-width="10" stroke-linecap="round"/>'
        + p.shape(f'<rect x="{f(cx - width / 2)}" y="{f(top)}" width="{f(width)}" height="18" rx="6"', "#d9d4e2", "#b9b3c6")
    )


def head_profile(st: Stage, box: Box, level: int) -> str:
    """The expanding-brain head: one fixed head silhouette in profile, the brain growing brighter with ``level`` 1-4."""
    x, y, w, h = box
    # The whole head fits its row (crown to neck), and nothing glows into the next row.
    s = min(w / 540, h / 330) * 0.8
    cx, cy = x + w * 0.5, y + h * 0.6
    bg_top = ("#2a2430", "#1d2a55", "#3b1660", "#0b0420")[level - 1]
    bg_bottom = ("#141018", "#0e1630", "#1c0a33", "#000004")[level - 1]
    out = [gradient_rect(st, box, bg_top, bg_bottom)]
    glow = ("#ff9fb3", "#ffb0c4", st.sch.ramp[-2] if st.sch.ramp_id != "viridis" else "#ffe08a", "#ffffff")[level - 1]
    if level >= 3:
        rays = []
        for i in range(18):
            a = i / 18 * math.tau
            r0, r1 = 70 * s, (210 if level == 4 else 150) * s
            rays.append(
                f'<path d="M{f(cx + 20 * s + math.cos(a) * r0)},{f(cy - 60 * s + math.sin(a) * r0)} L{f(cx + 20 * s + math.cos(a) * r1)},{f(cy - 60 * s + math.sin(a) * r1)}" '
                f'stroke="{glow}" stroke-width="{f((9 if i % 2 else 4) * s)}" stroke-linecap="round" opacity="0.6"/>'
            )
        out.append("".join(rays))
    if level == 4:
        rng = random.Random(4)
        for _ in range(40):
            out.append(
                f'<circle cx="{f(x + rng.random() * w)}" cy="{f(y + rng.random() * h)}" r="{f(rng.uniform(1, 3) * s)}" fill="#ffffff" opacity="0.8"/>'
            )
        for k in range(3):
            out.append(
                f'<ellipse cx="{f(cx + 20 * s)}" cy="{f(cy - 60 * s)}" rx="{f((120 + k * 45) * s)}" ry="{f((40 + k * 16) * s)}" fill="none" '
                f'stroke="{st.sch.ramp[-3 - k]}" stroke-width="{f(5 * s)}" opacity="0.65" transform="rotate(-20 {f(cx + 20 * s)} {f(cy - 60 * s)})"/>'
            )
    head = (
        f"M{f(cx - 110 * s)},{f(cy + 150 * s)} C{f(cx - 120 * s)},{f(cy + 60 * s)} {f(cx - 150 * s)},{f(cy - 40 * s)} {f(cx - 110 * s)},{f(cy - 120 * s)} "
        f"C{f(cx - 70 * s)},{f(cy - 190 * s)} {f(cx + 60 * s)},{f(cy - 200 * s)} {f(cx + 110 * s)},{f(cy - 130 * s)} "
        f"C{f(cx + 140 * s)},{f(cy - 90 * s)} {f(cx + 140 * s)},{f(cy - 40 * s)} {f(cx + 130 * s)},{f(cy - 10 * s)} "
        f"L{f(cx + 160 * s)},{f(cy + 30 * s)} L{f(cx + 128 * s)},{f(cy + 40 * s)} C{f(cx + 135 * s)},{f(cy + 70 * s)} {f(cx + 110 * s)},{f(cy + 90 * s)} "
        f"{f(cx + 70 * s)},{f(cy + 85 * s)} L{f(cx + 60 * s)},{f(cy + 150 * s)} Z"
    )
    skin = ("#3d4a8a", "#4a5dc0", "#6a3fd0", "#b9a6ff")[level - 1]
    out.append(
        f'<path d="{head}" fill="{skin}" opacity="{(0.8, 0.85, 0.8, 0.55)[level - 1]}" stroke="{mix(skin, "#ffffff", 0.4)}" stroke-width="{f(4 * s)}"/>'
    )
    bx, by = cx + 10 * s, cy - 70 * s
    brain_r = (40, 54, 64, 72)[level - 1] * s
    if level >= 2:
        out.append(
            f'<circle cx="{f(bx)}" cy="{f(by)}" r="{f(brain_r * (1.6 + level * 0.25))}" fill="{glow}" opacity="{0.15 + level * 0.1:.2f}"/>'
        )
    brain = mix("#f59ab4", "#ffffff", (0, 0.2, 0.45, 0.85)[level - 1])
    out.append(
        f'<ellipse cx="{f(bx)}" cy="{f(by)}" rx="{f(brain_r * 1.25)}" ry="{f(brain_r)}" fill="{brain}" stroke="{mix(brain, "#8a2a4a", 0.5)}" stroke-width="{f(3 * s)}"/>'
    )
    folds = "".join(
        f'<path d="M{f(bx + dx * brain_r)},{f(by - brain_r * 0.6)} q{f(brain_r * 0.25)},{f(brain_r * 0.4)} 0,{f(brain_r * 0.7)} q{f(-brain_r * 0.2)},{f(brain_r * 0.3)} 0,{f(brain_r * 0.5)}" '
        f'fill="none" stroke="{mix(brain, "#8a2a4a", 0.45)}" stroke-width="{f(3 * s)}" stroke-linecap="round"/>'
        for dx in (-0.7, -0.2, 0.3, 0.8)
    )
    out.append(folds)
    eye = "#ffffff" if level >= 3 else "#c9d2ff"
    out.append(f'<ellipse cx="{f(cx + 92 * s)}" cy="{f(cy - 30 * s)}" rx="{f(9 * s)}" ry="{f(6 * s)}" fill="{eye}"/>')
    cid = f"{st.prefix}-brain{level}"
    st.p.defs.append(f'<clipPath id="{cid}"><rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}"/></clipPath>')
    return f'<g clip-path="url(#{cid})">{"".join(out)}</g>'


def butterfly(st: Stage, cx: float, cy: float, size: float) -> str:
    wing = mix(st.sch.ramp[-2], "#ffffff", 0.2)
    wing2 = st.sch.ramp[-4]
    s = size
    return (
        f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(s * 1.6)}" fill="{wing}" opacity="0.25"/>'
        + st.p.shape(
            f'<path d="M{f(cx)},{f(cy)} C{f(cx - s)},{f(cy - s * 1.2)} {f(cx - s * 1.3)},{f(cy - s * 0.2)} {f(cx)},{f(cy)} Z"',
            wing,
            wing2,
            outline=0.7,
        )
        + st.p.shape(
            f'<path d="M{f(cx)},{f(cy)} C{f(cx + s)},{f(cy - s * 1.2)} {f(cx + s * 1.3)},{f(cy - s * 0.2)} {f(cx)},{f(cy)} Z"',
            wing,
            wing2,
            outline=0.7,
        )
        + st.p.shape(
            f'<path d="M{f(cx)},{f(cy)} C{f(cx - s * 0.8)},{f(cy + s * 0.2)} {f(cx - s * 0.6)},{f(cy + s * 0.9)} {f(cx)},{f(cy)} Z"',
            wing2,
            wing2,
            outline=0.7,
        )
        + st.p.shape(
            f'<path d="M{f(cx)},{f(cy)} C{f(cx + s * 0.8)},{f(cy + s * 0.2)} {f(cx + s * 0.6)},{f(cy + s * 0.9)} {f(cx)},{f(cy)} Z"',
            wing2,
            wing2,
            outline=0.7,
        )
        + f'<ellipse cx="{f(cx)}" cy="{f(cy)}" rx="{f(s * 0.08)}" ry="{f(s * 0.35)}" fill="{INK_DARK}"/>'
    )


def flipchart(st: Stage, box: Box) -> str:
    x, y, w, h = box
    p = st.p
    return (
        f'<path d="M{f(x + w * 0.2)},{f(y + h * 0.9)} L{f(x + w * 0.1)},{f(y + h)} M{f(x + w * 0.8)},{f(y + h * 0.9)} L{f(x + w * 0.9)},{f(y + h)} M{f(x + w / 2)},{f(y + h * 0.9)} L{f(x + w / 2)},{f(y + h)}" stroke="#6b4a2b" stroke-width="8" stroke-linecap="round"/>'
        + p.shape(f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h * 0.9)}" rx="6"', "#ffffff", "#f4f4f6")
        + f'<rect x="{f(x - 8)}" y="{f(y + h * 0.88)}" width="{f(w + 16)}" height="14" rx="4" fill="#8a6a48"/>'
    )


def big_button(st: Stage, cx: float, cy: float, w: float = 380, h: float = 230) -> str:
    """The classic big red button (always red: recognizable colors stay)."""
    gid = f"{st.prefix}-btn{int(cx)}"
    st.p.defs.append(
        f'<radialGradient id="{gid}" cx="0.4" cy="0.35" r="0.75"><stop offset="0" stop-color="#ff6b5e"/><stop offset="1" stop-color="#c81d1d"/></radialGradient>'
    )
    rx, ry = w / 2, h / 2
    return (
        f'<ellipse cx="{f(cx)}" cy="{f(cy + ry * 0.45)}" rx="{f(rx * 1.08)}" ry="{f(ry * 1.1)}" fill="#2f2a3a" opacity="0.5"/>'
        f'<rect x="{f(cx - rx)}" y="{f(cy)}" width="{f(w)}" height="{f(ry * 0.38)}" fill="#8c1616"/>'
        f'<ellipse cx="{f(cx)}" cy="{f(cy + ry * 0.38)}" rx="{f(rx)}" ry="{f(ry)}" fill="#8c1616"/>'
        f'<ellipse cx="{f(cx)}" cy="{f(cy)}" rx="{f(rx)}" ry="{f(ry)}" fill="url(#{gid})" stroke="#6b0f0f" stroke-width="3"/>'
        f'<ellipse cx="{f(cx - rx * 0.2)}" cy="{f(cy - ry * 0.45)}" rx="{f(rx * 0.58)}" ry="{f(ry * 0.3)}" fill="#ffffff" opacity="0.2"/>'
    )


def object_(st: Stage, name: str, box: Box) -> str:
    """A generic prop fitted in ``box`` (the PROP_HINTS catalog)."""
    x, y, w, h = box
    cx, cy = x + w / 2, y + h / 2
    p = st.p
    a0, a1, a2 = st.sch.accent(0), st.sch.accent(1), st.sch.accent(2)
    s = min(w, h)
    if name == "laptop":
        return laptop(st, cx, y + h, s / 150, "right")
    if name in ("table", "desk"):
        return table(st, cx, y + h * 0.45, w, h * 0.55)
    if name == "mug":
        return mug(st, cx, y + h, s / 60)
    if name == "chart_screen":
        return screen(st, (x, y, w, h * 0.78))
    if name == "server":
        out = p.shape(f'<rect x="{f(x + w * 0.2)}" y="{f(y)}" width="{f(w * 0.6)}" height="{f(h)}" rx="10"', "#3a3346", "#2a2433")
        for k in range(int(h / 50)):
            yy = y + 18 + k * 50
            out += f'<rect x="{f(x + w * 0.26)}" y="{f(yy)}" width="{f(w * 0.48)}" height="34" rx="5" fill="#4a4258"/>'
            out += f'<circle cx="{f(x + w * 0.66)}" cy="{f(yy + 17)}" r="6" fill="{(a0, a1, "#5fd16a")[k % 3]}"/>'
        return out
    if name == "whiteboard":
        return flipchart(st, box)
    if name == "sign":
        return f'<rect x="{f(cx - 7)}" y="{f(y + h * 0.4)}" width="14" height="{f(h * 0.6)}" fill="#8a6a48"/>' + sign_board(
            st, (x, y, w, h * 0.5)
        )
    if name == "plant":
        out = "".join(
            p.shape(
                f'<ellipse cx="{f(cx + dx * s * 0.2)}" cy="{f(y + h * 0.35)}" rx="{f(s * 0.12)}" ry="{f(s * 0.3)}" transform="rotate({dx * 25} {f(cx)} {f(y + h * 0.6)})"',
                "#6fc05a",
                "#3f8f3a",
            )
            for dx in (-1.5, -0.5, 0.5, 1.5)
        )
        return out + p.shape(
            f'<path d="M{f(cx - s * 0.25)},{f(y + h * 0.6)} L{f(cx + s * 0.25)},{f(y + h * 0.6)} L{f(cx + s * 0.18)},{f(y + h)} L{f(cx - s * 0.18)},{f(y + h)} Z"',
            a0,
            mix(a0, "#000000", 0.2),
        )
    if name == "rocket":
        return (
            p.shape(
                f'<path d="M{f(cx)},{f(y)} C{f(cx + w * 0.3)},{f(y + h * 0.2)} {f(cx + w * 0.25)},{f(y + h * 0.7)} {f(cx + w * 0.18)},{f(y + h * 0.78)} L{f(cx - w * 0.18)},{f(y + h * 0.78)} C{f(cx - w * 0.25)},{f(y + h * 0.7)} {f(cx - w * 0.3)},{f(y + h * 0.2)} {f(cx)},{f(y)} Z"',
                "#f2f2f5",
                "#c9c9d2",
            )
            + p.shape(f'<circle cx="{f(cx)}" cy="{f(y + h * 0.35)}" r="{f(s * 0.1)}"', "#7cc7ff", "#3a86c8")
            + flame(cx, y + h * 0.78, w * 0.25, -h * 0.22, "#fb9b06")
        )
    if name == "cloud":
        return p.shape(
            f'<path d="M{f(x + w * 0.2)},{f(y + h * 0.8)} C{f(x)},{f(y + h * 0.8)} {f(x)},{f(y + h * 0.4)} {f(x + w * 0.25)},{f(y + h * 0.42)} C{f(x + w * 0.3)},{f(y + h * 0.05)} {f(x + w * 0.7)},{f(y + h * 0.05)} {f(x + w * 0.74)},{f(y + h * 0.4)} C{f(x + w)},{f(y + h * 0.38)} {f(x + w)},{f(y + h * 0.8)} {f(x + w * 0.8)},{f(y + h * 0.8)} Z"',
            "#ffffff",
            "#e7e7f0",
        )
    if name == "bucket":
        return p.shape(
            f'<path d="M{f(x + w * 0.15)},{f(y + h * 0.2)} L{f(x + w * 0.85)},{f(y + h * 0.2)} L{f(x + w * 0.75)},{f(y + h)} L{f(x + w * 0.25)},{f(y + h)} Z"',
            a1,
            mix(a1, "#000000", 0.2),
        )
    if name == "gauge":
        return (
            p.shape(
                f'<path d="M{f(x)},{f(cy + s * 0.2)} A{f(w / 2)},{f(w / 2)} 0 0 1 {f(x + w)},{f(cy + s * 0.2)} Z"', "#ffffff", "#ececf1"
            )
            + f'<path d="M{f(cx)},{f(cy + s * 0.2)} L{f(cx + w * 0.35)},{f(cy - s * 0.15)}" stroke="{a0}" stroke-width="8" stroke-linecap="round"/>'
        )
    if name == "lightbulb":
        return (
            f'<circle cx="{f(cx)}" cy="{f(y + h * 0.38)}" r="{f(s * 0.5)}" fill="{st.sch.glow}" opacity="0.25"/>'
            + p.shape(f'<circle cx="{f(cx)}" cy="{f(y + h * 0.38)}" r="{f(s * 0.3)}"', "#fff6b0", "#f7d13d")
            + p.shape(
                f'<rect x="{f(cx - s * 0.14)}" y="{f(y + h * 0.66)}" width="{f(s * 0.28)}" height="{f(s * 0.2)}" rx="4"',
                "#9aa0ad",
                "#7a7f8b",
            )
        )
    if name == "trophy":
        return p.shape(
            f'<path d="M{f(x + w * 0.25)},{f(y)} L{f(x + w * 0.75)},{f(y)} C{f(x + w * 0.75)},{f(y + h * 0.5)} {f(x + w * 0.25)},{f(y + h * 0.5)} {f(x + w * 0.25)},{f(y)} Z"',
            "#ffd34d",
            "#e0a91a",
        ) + p.shape(
            f'<rect x="{f(cx - w * 0.2)}" y="{f(y + h * 0.75)}" width="{f(w * 0.4)}" height="{f(h * 0.25)}" rx="4"', "#8a6a48", "#6b4a2b"
        )
    if name == "box":
        return p.shape(f'<rect x="{f(x)}" y="{f(y + h * 0.2)}" width="{f(w)}" height="{f(h * 0.8)}" rx="4"', "#d9a35b", "#b07a3a")
    if name == "stack":
        out = ""
        for k in range(int(h / 18)):
            out += f'<rect x="{f(x + (k % 3 - 1) * 6)}" y="{f(y + h - (k + 1) * 18)}" width="{f(w)}" height="16" rx="2" fill="#ffffff" stroke="#c9c6d2" stroke-width="2"/>'
        return out
    if name == "fire":
        return "".join(
            flame(cx, y + h, w * (1 - k * 0.25), h * (1 - k * 0.2), c) for k, c in enumerate(("#cf4446", "#ed6925", "#fb9b06", "#f7d13d"))
        )
    if name == "door":
        return (
            p.shape(f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" rx="6"', "#a0673e", "#7d4f2f")
            + f'<circle cx="{f(x + w * 0.8)}" cy="{f(cy)}" r="8" fill="#ffd34d"/>'
        )
    if name == "lightbulb_off":
        return p.shape(f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(s * 0.3)}"', "#d9d9e0", "#b9b9c3")
    if name == "balloon":
        return (
            f'<path d="M{f(cx)},{f(y + h)} C{f(cx + 20)},{f(y + h * 0.75)} {f(cx - 20)},{f(y + h * 0.6)} {f(cx)},{f(y + h * 0.45)}" fill="none" stroke="#6b6478" stroke-width="3"/>'
            + p.shape(
                f'<ellipse cx="{f(cx)}" cy="{f(y + h * 0.25)}" rx="{f(w * 0.3)}" ry="{f(h * 0.22)}"',
                mix(a0, "#ffffff", 0.15),
                mix(a0, "#000000", 0.1),
            )
        )
    if name == "butterfly":
        return butterfly(st, cx, cy, s * 0.4)
    if name == "planet":
        return planet(st, cx, cy, s * 0.45)
    if name == "magnet":
        return p.hose(
            f"M{f(x + w * 0.2)},{f(y)} L{f(x + w * 0.2)},{f(y + h * 0.55)} A{f(w * 0.3)},{f(w * 0.3)} 0 0 0 {f(x + w * 0.8)},{f(y + h * 0.55)} L{f(x + w * 0.8)},{f(y)}",
            "#e63946",
            w * 0.22,
        )
    if name == "funnel":
        return p.shape(
            f'<path d="M{f(x)},{f(y)} L{f(x + w)},{f(y)} L{f(cx + w * 0.08)},{f(y + h * 0.6)} L{f(cx + w * 0.08)},{f(y + h)} L{f(cx - w * 0.08)},{f(y + h)} L{f(cx - w * 0.08)},{f(y + h * 0.6)} Z"',
            a2,
            mix(a2, "#000000", 0.2),
        )
    if name == "ladder":
        out = f'<path d="M{f(x + w * 0.25)},{f(y)} L{f(x + w * 0.2)},{f(y + h)} M{f(x + w * 0.75)},{f(y)} L{f(x + w * 0.8)},{f(y + h)}" stroke="#8a6a48" stroke-width="10" stroke-linecap="round"/>'
        for k in range(1, 6):
            out += f'<line x1="{f(x + w * 0.24)}" y1="{f(y + h * k / 6)}" x2="{f(x + w * 0.76)}" y2="{f(y + h * k / 6)}" stroke="#8a6a48" stroke-width="8"/>'
        return out
    if name == "crystal_ball":
        return p.shape(
            f'<circle cx="{f(cx)}" cy="{f(y + h * 0.4)}" r="{f(s * 0.36)}"', mix(st.sch.ramp[-1], "#ffffff", 0.3), st.sch.ramp[4]
        ) + p.shape(
            f'<path d="M{f(cx - s * 0.3)},{f(y + h)} L{f(cx - s * 0.2)},{f(y + h * 0.72)} L{f(cx + s * 0.2)},{f(y + h * 0.72)} L{f(cx + s * 0.3)},{f(y + h)} Z"',
            "#8a6a48",
            "#6b4a2b",
        )
    if name == "puzzle":
        return p.shape(
            f'<rect x="{f(x)}" y="{f(y + h * 0.2)}" width="{f(w * 0.45)}" height="{f(h * 0.6)}" rx="8"', a0, mix(a0, "#000000", 0.2)
        ) + p.shape(
            f'<rect x="{f(x + w * 0.55)}" y="{f(y + h * 0.2)}" width="{f(w * 0.45)}" height="{f(h * 0.6)}" rx="8"',
            a1,
            mix(a1, "#000000", 0.2),
        )
    if name == "telescope":
        return (
            p.hose(f"M{f(x + w * 0.2)},{f(y + h * 0.6)} L{f(x + w * 0.85)},{f(y + h * 0.2)}", "#5b4a7a", s * 0.16)
            + f'<path d="M{f(cx)},{f(y + h * 0.45)} L{f(x + w * 0.2)},{f(y + h)} M{f(cx)},{f(y + h * 0.45)} L{f(x + w * 0.8)},{f(y + h)}" stroke="#6b6478" stroke-width="6"/>'
        )
    if name == "bridge":
        return p.hose(f"M{f(x)},{f(y + h * 0.7)} Q{f(cx)},{f(y + h * 0.1)} {f(x + w)},{f(y + h * 0.7)}", "#a0673e", h * 0.12)
    if name == "maze":
        out = p.shape(f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" rx="6"', "#6fb05a", "#4f9a4a")
        for k in range(1, 4):
            out += f'<rect x="{f(x + w * k / 8)}" y="{f(y + h * k / 8)}" width="{f(w * (1 - k / 4))}" height="{f(h * (1 - k / 4))}" fill="none" stroke="#e9e2c0" stroke-width="10"/>'
        return out
    return ""


def menu() -> str:
    backdrops = ", ".join(f"`{k}` ({v})" for k, v in BACKDROP_HINTS.items())
    props = ", ".join(f"`{k}` ({v})" for k, v in PROP_HINTS.items())
    return f"Backdrops: {backdrops}.\nProps: {props}."


def default_stage(sch: Scheme | None = None, look: str = "inferno_flat", prefix: str = "st") -> Stage:
    return Stage(sch or scheme(), look, prefix)
