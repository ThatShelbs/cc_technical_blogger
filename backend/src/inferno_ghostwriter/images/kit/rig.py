# ruff: noqa: E501
"""The character rig: our own cast, drawn by code from named parts, so every character is on-model and whole.

A ``Character`` is a kind (ghost, dog, cat, person, robot), an expression, a pose, a facing, an accessory and a prop.
``draw`` returns its SVG and named anchors (head top, mouth, hands, seat), so scenes can aim speech bubbles at the
mouth and put a mug in the hand. Limbs start inside the body and end at the hands, and heads overlap their bodies, so a
floating head or a detached arm cannot happen.

Characters are drawn facing right in a local frame with the ground at y = 0 and about 300 units tall; ``facing="left"``
mirrors them. The cast is our own design: never a real person's likeness and never someone else's character.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from inferno_ghostwriter.images.kit.face import EXPRESSIONS, draw_face, extras, f
from inferno_ghostwriter.images.kit.paint import Painter
from inferno_ghostwriter.images.kit.style import Coat, KitStyle, coat, kit_style
from inferno_ghostwriter.images.palettes import Scheme, mix, scheme

KINDS = ("ghost", "dog", "cat", "person", "robot")
KIND_HINTS = {
    "ghost": "the friendly Inferno Ghostwriter ghost (the house star)",
    "dog": "a round, friendly cartoon pup",
    "cat": "a round cartoon cat",
    "person": "a stylized chibi person (no likeness of anyone real)",
    "robot": "a friendly retro robot with a screen face",
}

Point = tuple[float, float]


@dataclass(frozen=True)
class Arm:
    """Where one hand goes, relative to its shoulder, in arm lengths; ``bend`` curves the limb (+ down/out)."""

    dx: float
    dy: float
    bend: float = 0.35
    hand: str = "mitten"  # mitten | point | palm | fist
    to: str = ""  # aim at a face point instead: "face", "chin", "brow"


@dataclass(frozen=True)
class Pose:
    right: Arm  # the arm on the side the character faces
    left: Arm
    sit: bool = False
    lean: float = 0.0  # degrees, + leans toward the facing side
    hint: str = ""


REST_R = Arm(0.32, 0.88, 0.3)
REST_L = Arm(-0.32, 0.88, -0.3)

POSES: dict[str, Pose] = {
    "stand": Pose(REST_R, REST_L, hint="standing, arms relaxed"),
    "wave": Pose(Arm(0.55, -0.9, -0.3, "palm"), REST_L, hint="waving hello"),
    "point": Pose(Arm(1.05, -0.05, -0.1, "point"), REST_L, lean=4, hint="pointing ahead (toward what it faces)"),
    "point_up": Pose(Arm(0.35, -1.05, -0.2, "point"), REST_L, hint="pointing up, 'aha'"),
    "arms_up": Pose(Arm(0.6, -0.9, -0.3, "palm"), Arm(-0.6, -0.9, 0.3, "palm"), hint="both arms up: celebrating or panicking"),
    "shrug": Pose(Arm(0.95, -0.3, 0.5, "palm"), Arm(-0.95, -0.3, -0.5, "palm"), hint="shrugging, palms up"),
    "hold": Pose(Arm(0.55, 0.38, 0.45, "fist"), REST_L, hint="holding something at chest height (use with a prop)"),
    "hold_both": Pose(Arm(0.62, 0.28, 0.45, "fist"), Arm(0.2, 0.42, 0.45, "fist"), hint="holding something in front with both hands"),
    "typing": Pose(Arm(0.78, 0.62, 0.45, "mitten"), Arm(0.32, 0.7, 0.45, "mitten"), lean=6, hint="typing on a laptop in front"),
    "facepalm": Pose(Arm(0, 0, 0.5, "palm", to="face"), REST_L, hint="facepalm"),
    "chin": Pose(Arm(0, 0, 0.6, "fist", to="chin"), REST_L, hint="hand on chin, thinking"),
    "wipe": Pose(Arm(0, 0, 0.6, "palm", to="brow"), REST_L, hint="wiping sweat off its brow"),
    "block": Pose(Arm(0.8, -0.6, -0.2, "palm"), REST_L, hint="hand up, palm out: 'no thanks'"),
    "block_back": Pose(REST_R, Arm(-1.15, -1.45, 0.3, "palm"), hint="turned away with a hand up behind it, palm out (the 'nope' panel)"),
    "reach": Pose(Arm(0.95, 0.15, 0.2, "point"), REST_L, lean=5, hint="reaching forward hesitantly"),
    "present": Pose(Arm(0.95, -0.15, 0.3, "palm"), Arm(0.45, 0.1, 0.4, "palm"), hint="presenting something to the side it faces"),
    "proud": Pose(Arm(0.55, 0.62, 0.95, "fist"), Arm(-0.55, 0.62, -0.95, "fist"), hint="hands on hips, chest out"),
    "sit": Pose(Arm(0.5, 0.55, 0.45, "mitten"), Arm(-0.2, 0.75, -0.3, "mitten"), sit=True, hint="sitting"),
    "sit_hold": Pose(Arm(0.6, 0.3, 0.5, "fist"), Arm(-0.2, 0.75, -0.3, "mitten"), sit=True, hint="sitting, holding a mug"),
    "sit_type": Pose(Arm(0.78, 0.55, 0.45, "mitten"), Arm(0.36, 0.62, 0.45, "mitten"), sit=True, lean=6, hint="sitting at a laptop"),
    "float": Pose(Arm(0.55, 0.2, 0.5, "mitten"), Arm(-0.55, 0.2, -0.5, "mitten"), hint="floating, arms out"),
}

ACCESSORIES = (
    "none",
    "bowler",
    "top_hat",
    "cap",
    "beanie",
    "party_hat",
    "crown",
    "glasses",
    "sunglasses",
    "bow",
    "scarf",
    "tie",
    "headphones",
    "astronaut",
    "hood",
    "jacket",
    "lanyard",
    "goggles",
)
PROPS = ("none", "mug", "phone", "paper", "pointer", "magnifier", "balloon", "flag", "cloth", "pencil", "wrench", "flower")


@dataclass(frozen=True)
class Character:
    kind: str = "ghost"
    expression: str = "happy"
    pose: str = "stand"
    facing: str = "right"
    accessory: str = "none"
    prop: str = "none"
    variant: int = 0
    label: str = ""  # optional name for alt text


@dataclass
class Drawn:
    svg: str
    anchors: dict[str, Point]
    bbox: tuple[float, float, float, float]  # x0, y0, x1, y1 in the scene


@dataclass
class _Body:
    back: list[str] = field(default_factory=list)  # behind the body (tail, back ears)
    body: list[str] = field(default_factory=list)
    over: list[str] = field(default_factory=list)  # in front of the face (floppy ears, hair fringe)
    head: tuple[float, float, float] = (0.0, -200.0, 90.0)  # cx, cy, r
    face: Point = (0.0, -200.0)
    face_u: float = 1.0
    spacing: float = 30.0
    mouth_dy: float = 34.0
    animal: bool = False
    eye_color: str | None = None
    shoulders: tuple[Point, Point] = ((60.0, -120.0), (-60.0, -120.0))  # right, left
    arm_len: float = 62.0
    arm_w: float = 24.0
    arm_color: str = "#ffffff"
    hand_color: str = "#ffffff"
    hand: str = "mitten"  # mitten | paw | claw
    top: float = -290.0
    width: float = 100.0
    seat: Point = (0.0, -60.0)
    tuck: bool = False  # limbs grow out of the body: their outline goes behind it, so no seam shows on the body
    rest: tuple[Arm, Arm] | None = None  # this body's own relaxed arms (right, left)


# -- bodies -------------------------------------------------------------------------------------------------------------


def _ghost(c: Coat, p: Painter, pose: Pose) -> _Body:
    b = _Body()
    d = (
        "M-80,-200 C-80,-254 -44,-292 4,-292 C52,-292 86,-256 86,-200 C86,-150 90,-104 96,-62 "
        "C99,-38 90,-16 76,-17 C64,-18 60,-38 46,-37 C33,-36 31,-12 16,-12 C1,-12 -3,-33 -16,-33 "
        "C-29,-33 -34,-14 -50,-15 C-72,-16 -96,-8 -118,-22 C-134,-32 -140,-52 -134,-68 "
        "C-124,-52 -108,-46 -94,-54 C-82,-62 -80,-90 -80,-122 C-80,-150 -80,-176 -80,-200 Z"
    )
    b.body.append(p.shape(f'<path d="{d}"', c.top, c.bottom))
    b.body.append(p.highlight(-34, -250, 24, 12))
    b.head = (4, -205, 86)
    b.face = (16, -200)
    b.spacing, b.mouth_dy = 29, 32
    b.shoulders = ((62, -124), (-58, -124))
    b.arm_len, b.arm_w = 52, 30
    # The arm matches the body where it grows out of it (the body gradient's tone at shoulder height).
    b.arm_color = b.hand_color = mix(c.top, c.bottom, 0.36)
    b.tuck = True
    # Little flippers that poke out of the sides, like the logo's ghost.
    b.rest = (Arm(0.95, 0.42, 0.25), Arm(-0.95, 0.42, -0.25))
    b.top, b.width = -292, 96
    b.seat = (0, -40)
    return b


def _dog(c: Coat, p: Painter, pose: Pose) -> _Body:
    b = _Body()
    # Tail (behind), wagging up.
    b.back.append(p.hose("M-52,-58 C-86,-62 -98,-92 -88,-118", c.bottom, 22))
    # Body: a soft pear, sitting upright.
    body = "M-58,-118 C-70,-80 -74,-34 -60,-10 C-40,4 40,4 60,-10 C74,-34 70,-80 58,-118 C40,-142 -40,-142 -58,-118 Z"
    b.body.append(p.shape(f'<path d="{body}"', c.top, c.bottom))
    # Haunches and back feet.
    for side in (-1, 1):
        b.body.append(p.shape(f'<ellipse cx="{side * 50}" cy="-34" rx="30" ry="36"', c.top, c.bottom))
    b.body.append(f'<ellipse cx="0" cy="-70" rx="34" ry="44" fill="{mix(c.top, "#ffffff", 0.55)}" opacity="0.8"/>')
    # Head.
    hx, hy, hr = 6, -205, 86
    b.body.append(p.shape(f'<ellipse cx="{hx}" cy="{hy}" rx="{hr + 6}" ry="{hr}"', c.top, c.bottom))
    b.body.append(p.highlight(hx - 40, hy - 48, 22, 11))
    # Muzzle, nose.
    b.body.append(p.shape(f'<ellipse cx="{hx + 10}" cy="{hy + 38}" rx="40" ry="29"', mix(c.top, "#ffffff", 0.6), c.top, outline=0.6))
    b.body.append(
        f'<path d="M{hx - 3},{hy + 18} Q{hx + 10},{hy + 12} {hx + 23},{hy + 18} Q{hx + 22},{hy + 32} {hx + 10},{hy + 34} '
        f'Q{hx - 2},{hy + 32} {hx - 3},{hy + 18} Z" fill="#1c1418"/>'
        f'<ellipse cx="{hx + 5}" cy="{hy + 20}" rx="5" ry="3" fill="#ffffff" opacity="0.7"/>'
    )
    # Floppy ears in front of the head sides.
    for side, ex in ((-1, hx - 74), (1, hx + 82)):
        ear = (
            f"M{ex - side * 6},{hy - 62} C{ex + side * 26},{hy - 70} {ex + side * 34},{hy - 10} {ex + side * 22},{hy + 30} "
            f"C{ex + side * 12},{hy + 52} {ex - side * 18},{hy + 40} {ex - side * 20},{hy + 10} C{ex - side * 22},{hy - 20} "
            f"{ex - side * 22},{hy - 50} {ex - side * 6},{hy - 62} Z"
        )
        b.over.append(p.shape(f'<path d="{ear}"', c.second, mix(c.second, "#000000", 0.15)))
    b.head = (hx, hy, hr)
    b.face = (hx + 10, hy - 6)
    b.spacing, b.mouth_dy = 30, 46
    b.animal = True
    b.shoulders = ((28, -110), (-28, -110))
    b.arm_len, b.arm_w = 64, 28
    b.arm_color = b.hand_color = mix(c.top, c.bottom, 0.35)
    b.hand = "paw"
    b.top, b.width = -295, 105
    b.seat = (0, -30)
    return b


def _cat(c: Coat, p: Painter, pose: Pose) -> _Body:
    b = _Body()
    b.back.append(p.hose("M-50,-30 C-110,-30 -120,-90 -96,-140 C-90,-152 -78,-152 -80,-138", c.bottom, 20))
    body = "M-54,-116 C-66,-78 -70,-34 -56,-10 C-38,4 38,4 56,-10 C70,-34 66,-78 54,-116 C36,-138 -36,-138 -54,-116 Z"
    b.body.append(p.shape(f'<path d="{body}"', c.top, c.bottom))
    for side in (-1, 1):
        b.body.append(p.shape(f'<ellipse cx="{side * 46}" cy="-32" rx="27" ry="33"', c.top, c.bottom))
    b.body.append(f'<ellipse cx="0" cy="-68" rx="30" ry="40" fill="{mix(c.top, "#ffffff", 0.5)}" opacity="0.75"/>')
    hx, hy, hr = 6, -200, 84
    for side in (-1, 1):
        ex = hx + side * 52
        ear = f"M{ex - side * 32},{hy - 58} L{ex + side * 18},{hy - 118} L{ex + side * 34},{hy - 40} Z"
        b.back.append(p.shape(f'<path d="{ear}"', c.top, c.bottom))
        inner = f"M{ex - side * 16},{hy - 62} L{ex + side * 14},{hy - 100} L{ex + side * 22},{hy - 52} Z"
        b.back.append(f'<path d="{inner}" fill="#ffb3c1" opacity="0.85"/>')
    b.body.append(p.shape(f'<ellipse cx="{hx}" cy="{hy}" rx="{hr + 8}" ry="{hr}"', c.top, c.bottom))
    b.body.append(p.highlight(hx - 40, hy - 46, 22, 11))
    # Tabby stripes on the forehead.
    if c.second != c.top:
        for dx in (-14, 0, 14):
            b.body.append(
                f'<path d="M{hx + dx},{hy - 82} L{hx + dx * 0.8},{hy - 58}" stroke="{c.second}" stroke-width="7" stroke-linecap="round"/>'
            )
    b.body.append(f'<path d="M{hx + 3},{hy + 22} L{hx + 17},{hy + 22} L{hx + 10},{hy + 31} Z" fill="#ff8fa3"/>')
    whisker = mix(c.top, "#000000", 0.45) if c.top != "#3a3540" else "#e8e4ee"
    for side in (-1, 1):
        for k in (-1, 0, 1):
            x0 = hx + 10 + side * 34
            b.over.append(
                f'<path d="M{x0},{hy + 30 + k * 7} L{x0 + side * 42},{hy + 26 + k * 13}" stroke="{whisker}" stroke-width="3" '
                f'stroke-linecap="round" opacity="0.8"/>'
            )
    b.head = (hx, hy, hr)
    b.face = (hx + 10, hy - 8)
    b.spacing, b.mouth_dy = 31, 44
    b.animal = True
    b.shoulders = ((26, -108), (-26, -108))
    b.arm_len, b.arm_w = 62, 26
    b.arm_color = b.hand_color = mix(c.top, c.bottom, 0.35)
    b.hand = "paw"
    b.top, b.width = -318, 100
    b.seat = (0, -30)
    return b


def _person(c: Coat, p: Painter, pose: Pose, variant: int) -> _Body:
    b = _Body()
    skin, shirt, hair = c.top, c.second, c.accent
    pants = mix(shirt, "#1c1a24", 0.7)
    if pose.sit:
        for side in (-1, 1):
            x = side * 20
            b.body.append(p.hose(f"M{x},-58 L{x + 60},-56 L{x + 64},-8", pants, 30))
            b.body.append(p.shape(f'<ellipse cx="{x + 76}" cy="-8" rx="24" ry="12"', "#2b2633", "#18151c"))
    else:
        for side in (-1, 1):
            x = side * 22
            b.body.append(p.hose(f"M{x},-70 L{x},-14", pants, 32))
            b.body.append(p.shape(f'<ellipse cx="{x + 8}" cy="-10" rx="26" ry="13"', "#2b2633", "#18151c"))
    torso = "M-48,-136 C-56,-110 -54,-76 -50,-52 C-30,-44 30,-44 50,-52 C54,-76 56,-110 48,-136 C28,-150 -28,-150 -48,-136 Z"
    b.body.append(p.shape(f'<path d="{torso}"', shirt, mix(shirt, "#000000", 0.18)))
    hx, hy, hr = 4, -215, 76
    style_id = variant % 4
    # Hair behind the head (long hair and buns hang behind).
    if style_id == 1:
        b.back.append(
            p.shape(
                f'<path d="M{hx - 82},{hy - 10} C{hx - 92},{hy + 60} {hx - 70},{hy + 92} {hx - 40},{hy + 96} L{hx + 50},{hy + 96} C{hx + 80},{hy + 90} {hx + 92},{hy + 60} {hx + 84},{hy - 10} Z"',
                hair,
                mix(hair, "#000000", 0.2),
            )
        )
    if style_id == 2:
        b.back.append(p.shape(f'<circle cx="{hx - 6}" cy="{hy - 86}" r="34"', hair, mix(hair, "#000000", 0.2)))
    b.body.append(p.shape(f'<circle cx="{hx}" cy="{hy}" r="{hr}"', skin, mix(skin, "#000000", 0.06)))
    # Ears.
    b.body.append(p.shape(f'<ellipse cx="{hx - hr + 2}" cy="{hy + 8}" rx="13" ry="17"', skin, skin, outline=0.8))
    # Hair on top (fringe over the forehead, never over the eyes).
    fringe = {
        0: f"M{hx - 78},{hy - 4} C{hx - 84},{hy - 70} {hx - 40},{hy - 92} {hx + 6},{hy - 90} C{hx + 60},{hy - 88} {hx + 86},{hy - 54} {hx + 78},{hy - 10} C{hx + 60},{hy - 36} {hx + 30},{hy - 48} {hx + 4},{hy - 44} C{hx - 30},{hy - 50} {hx - 58},{hy - 34} {hx - 78},{hy - 4} Z",
        1: f"M{hx - 80},{hy + 4} C{hx - 88},{hy - 72} {hx - 34},{hy - 94} {hx + 10},{hy - 90} C{hx + 64},{hy - 86} {hx + 90},{hy - 50} {hx + 80},{hy + 4} C{hx + 70},{hy - 30} {hx + 40},{hy - 52} {hx + 20},{hy - 52} C{hx + 6},{hy - 30} {hx - 30},{hy - 40} {hx - 50},{hy - 36} C{hx - 66},{hy - 26} {hx - 74},{hy - 10} {hx - 80},{hy + 4} Z",
        2: f"M{hx - 76},{hy - 8} C{hx - 80},{hy - 72} {hx - 36},{hy - 92} {hx + 4},{hy - 90} C{hx + 52},{hy - 90} {hx + 84},{hy - 60} {hx + 76},{hy - 10} C{hx + 50},{hy - 44} {hx - 40},{hy - 48} {hx - 76},{hy - 8} Z",
        3: f"M{hx - 74},{hy - 26} C{hx - 76},{hy - 70} {hx - 40},{hy - 88} {hx + 2},{hy - 86} C{hx + 46},{hy - 86} {hx + 76},{hy - 66} {hx + 74},{hy - 26} C{hx + 58},{hy - 52} {hx + 30},{hy - 60} {hx},{hy - 60} C{hx - 30},{hy - 60} {hx - 56},{hy - 52} {hx - 74},{hy - 26} Z",
    }[style_id]
    b.over.append(p.shape(f'<path d="{fringe}"', hair, mix(hair, "#000000", 0.2)))
    b.head = (hx, hy, hr)
    b.face = (hx + 10, hy + 6)
    b.spacing, b.mouth_dy = 28, 34
    b.shoulders = ((44, -126), (-44, -126))
    b.arm_len, b.arm_w = 64, 22
    b.arm_color = shirt
    b.hand_color = skin
    b.top, b.width = hy - hr - 18, 90
    b.seat = (0, -56)
    return b


def _robot(c: Coat, p: Painter, pose: Pose) -> _Body:
    b = _Body()
    metal, metal2, panel, glow = c.top, c.bottom, c.second, c.eye
    for side in (-1, 1):
        x = side * 26
        b.body.append(p.hose(f"M{x},-60 L{x},-18", metal2, 22))
        b.body.append(
            p.shape(f'<rect x="{x - 26}" y="-22" width="52" height="22" rx="10"', mix(metal2, "#000000", 0.2), mix(metal2, "#000000", 0.35))
        )
    b.body.append(p.shape('<rect x="-62" y="-140" width="124" height="96" rx="26"', panel, mix(panel, "#000000", 0.25)))
    b.body.append(
        p.shape(
            '<rect x="-30" y="-120" width="60" height="38" rx="9"', mix(panel, "#ffffff", 0.55), mix(panel, "#ffffff", 0.3), outline=0.6
        )
    )
    for i, col in enumerate((c.accent, glow, c.cheek)):
        b.body.append(f'<circle cx="{-14 + i * 14}" cy="-101" r="5" fill="{col}"/>')
    hx, hy = 4, -212
    b.back.append(p.hose(f"M{hx},{hy - 64} L{hx},{hy - 100}", metal2, 8))
    b.back.append(p.shape(f'<circle cx="{hx}" cy="{hy - 106}" r="13"', c.accent, mix(c.accent, "#000000", 0.25)))
    b.body.append(p.shape(f'<rect x="{hx - 88}" y="{hy - 68}" width="176" height="136" rx="38"', metal, metal2))
    for side in (-1, 1):
        b.body.append(p.shape(f'<rect x="{hx + side * 92 - 10}" y="{hy - 22}" width="20" height="44" rx="8"', metal2, metal2, outline=0.8))
    screen = "#160d2a"
    b.body.append(f'<rect x="{hx - 70}" y="{hy - 50}" width="140" height="100" rx="26" fill="{screen}"/>')
    b.body.append(p.highlight(hx - 52, hy - 54, 20, 8, -10))
    b.head = (hx, hy, 74)
    b.face = (hx + 6, hy - 10)
    b.face_u = 0.82
    b.spacing, b.mouth_dy = 32, 36
    b.eye_color = glow
    b.shoulders = ((60, -124), (-60, -124))
    b.arm_len, b.arm_w = 62, 18
    b.arm_color = metal2
    b.hand_color = metal
    b.hand = "claw"
    b.top, b.width = hy - 120, 100
    b.seat = (0, -50)
    return b


# -- limbs, hands, accessories, props ------------------------------------------------------------------------------------


def _target(arm: Arm, shoulder: Point, b: _Body) -> Point:
    fx, fy = b.face
    if b.hand == "paw" and arm in (REST_R, REST_L):
        return shoulder[0] * 0.95, -14
    if arm.to == "face":
        return fx + 2, fy + 4
    if arm.to == "chin":
        return fx + 6, fy + b.mouth_dy + 24
    if arm.to == "brow":
        # The temple on the far side, so the arm runs up beside the face instead of across it.
        return fx + 62, fy - 50
    return shoulder[0] + arm.dx * b.arm_len, shoulder[1] + arm.dy * b.arm_len


def _limb(shoulder: Point, hand: Point, bend: float) -> str:
    (sx, sy), (hx, hy) = shoulder, hand
    mx, my = (sx + hx) / 2, (sy + hy) / 2
    dx, dy = hx - sx, hy - sy
    length = math.hypot(dx, dy) or 1
    # Perpendicular offset for the elbow; positive bends toward the outside/down.
    nx, ny = -dy / length, dx / length
    cx, cy = mx + nx * bend * length * 0.35, my + ny * bend * length * 0.35
    return f"M{f(sx)},{f(sy)} Q{f(cx)},{f(cy)} {f(hx)},{f(hy)}"


def _hand(kind: str, grip: str, at: Point, toward: Point, size: float, color: str, p: Painter) -> str:
    x, y = at
    ang = math.degrees(math.atan2(at[1] - toward[1], at[0] - toward[0]))
    r = size * 0.62
    out = p.shape(f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(r)}"', color, mix(color, "#000000", 0.12))
    if grip == "point":
        fx_, fy_ = x + math.cos(math.radians(ang)) * r * 1.5, y + math.sin(math.radians(ang)) * r * 1.5
        out += p.hose(f"M{f(x)},{f(y)} L{f(fx_)},{f(fy_)}", color, size * 0.42)
        out += f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(r * 0.9)}" fill="{color}"/>'
    elif grip == "palm" and kind != "claw":
        # A thumb nub.
        tx, ty = x + math.cos(math.radians(ang - 70)) * r, y + math.sin(math.radians(ang - 70)) * r
        out += p.shape(f'<circle cx="{f(tx)}" cy="{f(ty)}" r="{f(r * 0.45)}"', color, color, outline=0.8)
    if kind == "paw":
        for k in (-1, 0, 1):
            a = math.radians(ang + k * 28)
            out += (
                f'<path d="M{f(x + math.cos(a) * r * 0.35)},{f(y + math.sin(a) * r * 0.35)} '
                f'L{f(x + math.cos(a) * r * 0.85)},{f(y + math.sin(a) * r * 0.85)}" stroke="{mix(color, "#000000", 0.35)}" '
                f'stroke-width="{f(max(1.5, r * 0.12))}" stroke-linecap="round"/>'
            )
    if kind == "claw":
        out += f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(r * 0.38)}" fill="{mix(color, "#000000", 0.3)}"/>'
    return out


def _accessory(name: str, b: _Body, c: Coat, p: Painter, kind: str) -> tuple[str, str]:
    """(behind, in front) of the character."""
    hx, hy, hr = b.head
    top = hy - hr
    deep = mix(c.accent, "#1b0c41", 0.55)
    if name == "bowler":
        return "", (
            p.shape(f'<ellipse cx="{f(hx + 4)}" cy="{f(top + 10)}" rx="{f(hr * 0.78)}" ry="13"', deep, deep)
            + p.shape(
                f'<path d="M{f(hx - hr * 0.48)},{f(top + 8)} C{f(hx - hr * 0.5)},{f(top - 52)} {f(hx + hr * 0.56)},{f(top - 52)} {f(hx + hr * 0.54)},{f(top + 8)} Z"',
                mix(deep, "#ffffff", 0.12),
                deep,
            )
            + f'<rect x="{f(hx - hr * 0.48)}" y="{f(top - 6)}" width="{f(hr * 1.02)}" height="10" fill="{c.accent}" opacity="0.85"/>'
        )
    if name == "top_hat":
        return "", (
            p.shape(f'<ellipse cx="{f(hx + 4)}" cy="{f(top + 8)}" rx="{f(hr * 0.8)}" ry="12"', deep, deep)
            + p.shape(f'<rect x="{f(hx - hr * 0.44)}" y="{f(top - 86)}" width="{f(hr * 0.96)}" height="94" rx="8"', deep, deep)
            + f'<rect x="{f(hx - hr * 0.44)}" y="{f(top - 14)}" width="{f(hr * 0.96)}" height="14" fill="{c.accent}"/>'
        )
    if name == "cap":
        return "", (
            p.shape(
                f'<path d="M{f(hx - hr * 0.86)},{f(top + 44)} C{f(hx - hr * 0.9)},{f(top - 22)} {f(hx + hr * 0.8)},{f(top - 26)} {f(hx + hr * 0.86)},{f(top + 40)} Z"',
                c.accent,
                mix(c.accent, "#000000", 0.2),
            )
            + p.shape(
                f'<path d="M{f(hx + hr * 0.5)},{f(top + 38)} C{f(hx + hr * 1.2)},{f(top + 30)} {f(hx + hr * 1.45)},{f(top + 46)} {f(hx + hr * 1.4)},{f(top + 54)} C{f(hx + hr * 1.1)},{f(top + 52)} {f(hx + hr * 0.7)},{f(top + 50)} {f(hx + hr * 0.5)},{f(top + 50)} Z"',
                mix(c.accent, "#000000", 0.15),
                mix(c.accent, "#000000", 0.25),
            )
        )
    if name == "beanie":
        return "", (
            p.shape(
                f'<path d="M{f(hx - hr * 0.9)},{f(top + 46)} C{f(hx - hr * 0.95)},{f(top - 30)} {f(hx + hr * 0.95)},{f(top - 30)} {f(hx + hr * 0.9)},{f(top + 46)} Z"',
                c.accent,
                mix(c.accent, "#000000", 0.2),
            )
            + p.shape(
                f'<rect x="{f(hx - hr * 0.94)}" y="{f(top + 30)}" width="{f(hr * 1.88)}" height="24" rx="11"',
                mix(c.accent, "#000000", 0.15),
                mix(c.accent, "#000000", 0.25),
            )
            + p.shape(f'<circle cx="{f(hx)}" cy="{f(top - 22)}" r="15"', "#ffffff", "#e5e5ea")
        )
    if name == "party_hat":
        return "", (
            p.shape(
                f'<path d="M{f(hx - 34)},{f(top + 14)} L{f(hx + 8)},{f(top - 82)} L{f(hx + 46)},{f(top + 14)} Z"',
                c.accent,
                mix(c.accent, "#000000", 0.2),
            )
            + p.shape(f'<circle cx="{f(hx + 8)}" cy="{f(top - 86)}" r="11"', "#ffffff", "#ffffff")
        )
    if name == "crown":
        return "", p.shape(
            f'<path d="M{f(hx - 46)},{f(top + 16)} L{f(hx - 52)},{f(top - 34)} L{f(hx - 22)},{f(top - 8)} L{f(hx + 4)},{f(top - 46)} L{f(hx + 30)},{f(top - 8)} L{f(hx + 58)},{f(top - 34)} L{f(hx + 52)},{f(top + 16)} Z"',
            "#ffd34d",
            "#e0a91a",
        )
    if name in ("glasses", "sunglasses", "goggles"):
        fx, fy = b.face
        s = b.spacing * b.face_u
        lens = "#1c1418" if name == "sunglasses" else "#ffffff"
        opacity = "1" if name == "sunglasses" else "0.25"
        r = 22.0 if name != "goggles" else 25.0
        frame = c.accent if name == "goggles" else "#1c1418"
        return "", (
            f'<g fill="{lens}" fill-opacity="{opacity}" stroke="{frame}" stroke-width="6">'
            f'<circle cx="{f(fx - s)}" cy="{f(fy)}" r="{r}"/><circle cx="{f(fx + s)}" cy="{f(fy)}" r="{r}"/></g>'
            f'<path d="M{f(fx - s + r)},{f(fy - 2)} Q{f(fx)},{f(fy - 12)} {f(fx + s - r)},{f(fy - 2)}" fill="none" stroke="{frame}" stroke-width="6"/>'
        )
    if name == "bow":
        bx, by = hx + hr * 0.55, top + 18
        return "", (
            p.shape(
                f'<path d="M{f(bx)},{f(by)} L{f(bx - 30)},{f(by - 20)} L{f(bx - 30)},{f(by + 20)} Z"',
                c.accent,
                mix(c.accent, "#000000", 0.2),
            )
            + p.shape(
                f'<path d="M{f(bx)},{f(by)} L{f(bx + 30)},{f(by - 20)} L{f(bx + 30)},{f(by + 20)} Z"',
                c.accent,
                mix(c.accent, "#000000", 0.2),
            )
            + p.shape(f'<circle cx="{f(bx)}" cy="{f(by)}" r="9"', mix(c.accent, "#000000", 0.15), c.accent)
        )
    if name == "scarf":
        sx, sy = b.shoulders[0][0], b.shoulders[0][1] - 18
        return "", (
            p.hose(f"M{f(-sx * 0.9)},{f(sy)} Q0,{f(sy + 22)} {f(sx * 0.9)},{f(sy)}", c.accent, 26)
            + p.hose(f"M{f(sx * 0.4)},{f(sy + 10)} L{f(sx * 0.62)},{f(sy + 62)}", mix(c.accent, "#000000", 0.12), 22)
        )
    if name == "tie":
        tx, ty = b.face[0] - 6, b.shoulders[0][1] - 10
        return "", p.shape(
            f'<path d="M{f(tx - 9)},{f(ty)} L{f(tx + 9)},{f(ty)} L{f(tx + 13)},{f(ty + 62)} L{f(tx)},{f(ty + 78)} L{f(tx - 13)},{f(ty + 62)} Z"',
            c.accent,
            mix(c.accent, "#000000", 0.2),
        )
    if name == "lanyard":
        sx, sy = b.shoulders[0]
        return "", (
            f'<path d="M{f(-sx * 0.6)},{f(sy - 4)} L{f(b.face[0] - 4)},{f(sy + 48)} L{f(sx * 0.6)},{f(sy - 4)}" fill="none" stroke="{c.accent}" stroke-width="6"/>'
            + p.shape(f'<rect x="{f(b.face[0] - 22)}" y="{f(sy + 44)}" width="40" height="50" rx="6"', "#ffffff", "#eeeef2", outline=0.7)
        )
    if name == "headphones":
        return "", (
            f'<path d="M{f(hx - hr * 0.98)},{f(hy)} C{f(hx - hr)},{f(top - 30)} {f(hx + hr)},{f(top - 30)} {f(hx + hr * 0.98)},{f(hy)}" fill="none" stroke="{deep}" stroke-width="12"/>'
            + p.shape(
                f'<rect x="{f(hx - hr - 18)}" y="{f(hy - 26)}" width="30" height="56" rx="12"', c.accent, mix(c.accent, "#000000", 0.2)
            )
            + p.shape(
                f'<rect x="{f(hx + hr - 12)}" y="{f(hy - 26)}" width="30" height="56" rx="12"', c.accent, mix(c.accent, "#000000", 0.2)
            )
        )
    if name == "astronaut":
        r = hr * 1.32
        return (
            p.shape(f'<circle cx="{f(hx)}" cy="{f(hy + 6)}" r="{f(r + 8)}"', "#f2f2f5", "#c9c9d2"),
            f'<circle cx="{f(hx)}" cy="{f(hy + 6)}" r="{f(r)}" fill="#bfe6ff" fill-opacity="0.18" stroke="#ffffff" stroke-width="5" stroke-opacity="0.8"/>'
            f'<path d="M{f(hx - r * 0.6)},{f(hy - r * 0.55)} Q{f(hx - r * 0.2)},{f(hy - r * 0.9)} {f(hx + r * 0.25)},{f(hy - r * 0.82)}" fill="none" stroke="#ffffff" stroke-width="9" stroke-linecap="round" opacity="0.7"/>',
        )
    if name == "hood":
        r = hr * 1.18
        cloak = mix(c.accent, "#1b0c41", 0.75)
        return (
            p.shape(
                f'<path d="M{f(hx - r)},{f(hy + r * 1.8)} C{f(hx - r * 1.1)},{f(hy - r * 0.6)} {f(hx - r * 0.6)},{f(hy - r * 1.15)} {f(hx)},{f(hy - r * 1.15)} C{f(hx + r * 0.6)},{f(hy - r * 1.15)} {f(hx + r * 1.1)},{f(hy - r * 0.6)} {f(hx + r)},{f(hy + r * 1.8)} Z"',
                cloak,
                mix(cloak, "#000000", 0.3),
            ),
            p.shape(
                f'<path d="M{f(hx - r * 0.98)},{f(hy + 10)} C{f(hx - r)},{f(hy - r * 1.2)} {f(hx + r)},{f(hy - r * 1.2)} {f(hx + r * 0.98)},{f(hy + 10)} C{f(hx + r * 0.7)},{f(hy - r * 0.62)} {f(hx - r * 0.7)},{f(hy - r * 0.62)} {f(hx - r * 0.98)},{f(hy + 10)} Z"',
                cloak,
                mix(cloak, "#000000", 0.25),
            ),
        )
    if name == "jacket":
        # A puffer jacket: one puffy silhouette with scalloped sides (each quilted row bulges), broad shoulders, a
        # high collar under the chin and a zip. Always orange: a recognizable color stays.
        dark = mix(JACKET, "#000000", 0.25)
        sx, sy = b.shoulders[0]
        cx = (b.shoulders[0][0] + b.shoulders[1][0]) / 2
        w_ = max(abs(sx), abs(b.shoulders[1][0])) + 28
        top_y, bottom_y = sy - 6, min(sy + 104, -14)
        rows = 3
        step = (bottom_y - top_y) / rows
        left, right = cx - w_, cx + w_
        d = f"M{f(cx - w_ * 0.5)},{f(top_y)} C{f(cx - w_ * 0.95)},{f(top_y)} {f(left - 8)},{f(top_y + step * 0.3)} {f(left - 4)},{f(top_y + step)} "
        for k in range(1, rows):
            d += f"Q{f(left - 18)},{f(top_y + (k + 0.5) * step)} {f(left - 2 + k * 2)},{f(top_y + (k + 1) * step)} "
        d += f"Q{f(cx)},{f(bottom_y + 16)} {f(right + 2 - (rows - 1) * 2)},{f(bottom_y)} "
        for k in range(rows - 1, 0, -1):
            d += f"Q{f(right + 18)},{f(top_y + (k + 0.5) * step)} {f(right + 4)},{f(top_y + k * step)} "
        d += f"C{f(right + 8)},{f(top_y + step * 0.3)} {f(cx + w_ * 0.95)},{f(top_y)} {f(cx + w_ * 0.5)},{f(top_y)} Z"
        out = p.shape(f'<path d="{d}"', mix(JACKET, "#ffffff", 0.12), JACKET)
        for k in range(1, rows):
            y_ = top_y + k * step
            out += f'<path d="M{f(left + 4)},{f(y_)} Q{f(cx)},{f(y_ + 12)} {f(right - 4)},{f(y_)}" fill="none" stroke="{dark}" stroke-width="5" stroke-linecap="round"/>'
            out += f'<path d="M{f(cx - w_ * 0.55)},{f(y_ - step * 0.55)} Q{f(cx)},{f(y_ - step * 0.48)} {f(cx + w_ * 0.4)},{f(y_ - step * 0.58)}" fill="none" stroke="#ffffff" stroke-width="6" stroke-linecap="round" opacity="0.3"/>'
        out += p.shape(f'<rect x="{f(cx - w_ * 0.62)}" y="{f(top_y - 20)}" width="{f(w_ * 1.24)}" height="34" rx="17"', JACKET, dark)
        out += f'<path d="M{f(cx + 8)},{f(top_y + 10)} L{f(cx + 8)},{f(bottom_y + 6)}" stroke="{dark}" stroke-width="5" stroke-linecap="round"/>'
        return "", out
    return "", ""


def _prop(name: str, at: Point, c: Coat, p: Painter) -> tuple[str, str]:
    """(behind the hand, in front of the hand) for a prop held at ``at``."""
    x, y = at
    if name == "mug":
        mug = mix(c.accent, "#ffffff", 0.2)
        return (
            p.hose(f"M{f(x + 26)},{f(y - 18)} C{f(x + 48)},{f(y - 18)} {f(x + 48)},{f(y + 12)} {f(x + 26)},{f(y + 12)}", mug, 9),
            p.shape(f'<rect x="{f(x - 22)}" y="{f(y - 30)}" width="50" height="56" rx="10"', mug, mix(mug, "#000000", 0.2))
            + f'<path d="M{f(x - 8)},{f(y - 40)} q-8,-12 0,-24 M{f(x + 10)},{f(y - 40)} q-8,-12 0,-24" fill="none" stroke="#ffffff" stroke-width="4" stroke-linecap="round" opacity="0.7"/>',
        )
    if name == "phone":
        return "", p.shape(
            f'<rect x="{f(x - 16)}" y="{f(y - 44)}" width="34" height="62" rx="7"', "#2b2633", "#18151c"
        ) + f'<rect x="{f(x - 11)}" y="{f(y - 38)}" width="24" height="46" rx="3" fill="{mix(c.accent, "#ffffff", 0.5)}"/>'
    if name == "paper":
        return p.shape(f'<rect x="{f(x - 30)}" y="{f(y - 66)}" width="58" height="76" rx="4"', "#ffffff", "#ececf1"), "".join(
            f'<rect x="{f(x - 22)}" y="{f(y - 56 + k * 12)}" width="{42 - (k % 2) * 10}" height="4" rx="2" fill="#b9b6c4"/>'
            for k in range(4)
        )
    if name == "pointer":
        return p.hose(f"M{f(x)},{f(y)} L{f(x + 92)},{f(y - 56)}", "#8a5a2b", 7), ""
    if name == "magnifier":
        return p.hose(f"M{f(x)},{f(y)} L{f(x + 30)},{f(y - 30)}", "#5b4a3a", 12), (
            f'<circle cx="{f(x + 50)}" cy="{f(y - 50)}" r="30" fill="#cfefff" fill-opacity="0.35" stroke="#2b2633" stroke-width="9"/>'
        )
    if name == "balloon":
        return (
            f'<path d="M{f(x)},{f(y)} C{f(x + 20)},{f(y - 60)} {f(x - 20)},{f(y - 120)} {f(x + 10)},{f(y - 170)}" fill="none" stroke="#6b6478" stroke-width="3"/>'
            + p.shape(
                f'<ellipse cx="{f(x + 10)}" cy="{f(y - 222)}" rx="44" ry="54"',
                mix(c.accent, "#ffffff", 0.15),
                mix(c.accent, "#000000", 0.1),
            )
            + p.highlight(x - 6, y - 244, 12, 18, 20),
            "",
        )
    if name == "flag":
        return (
            p.hose(f"M{f(x)},{f(y + 20)} L{f(x)},{f(y - 140)}", "#5b4a3a", 7)
            + p.shape(
                f'<path d="M{f(x)},{f(y - 140)} L{f(x + 90)},{f(y - 118)} L{f(x)},{f(y - 92)} Z"', c.accent, mix(c.accent, "#000000", 0.2)
            ),
            "",
        )
    if name == "cloth":
        return "", p.shape(
            f'<path d="M{f(x - 26)},{f(y - 14)} Q{f(x)},{f(y - 30)} {f(x + 26)},{f(y - 12)} L{f(x + 20)},{f(y + 26)} Q{f(x)},{f(y + 12)} {f(x - 22)},{f(y + 24)} Z"',
            "#ffffff",
            "#e3e3ea",
        )
    if name == "pencil":
        return p.hose(f"M{f(x - 10)},{f(y + 30)} L{f(x + 20)},{f(y - 50)}", "#f7d13d", 12), ""
    if name == "wrench":
        return p.hose(
            f"M{f(x - 4)},{f(y + 20)} L{f(x + 26)},{f(y - 50)}", "#9aa0ad", 12
        ) + f'<circle cx="{f(x + 30)}" cy="{f(y - 58)}" r="15" fill="none" stroke="#9aa0ad" stroke-width="10"/>', ""
    if name == "flower":
        return p.hose(f"M{f(x)},{f(y)} L{f(x + 8)},{f(y - 70)}", "#35b779", 6) + "".join(
            f'<circle cx="{f(x + 8 + 14 * math.cos(a))}" cy="{f(y - 78 + 14 * math.sin(a))}" r="11" fill="#ff8fb8"/>'
            for a in (0, 1.26, 2.51, 3.77, 5.03)
        ) + f'<circle cx="{f(x + 8)}" cy="{f(y - 78)}" r="9" fill="#f7d13d"/>', ""
    return "", ""


# -- assembly -----------------------------------------------------------------------------------------------------------


_counter = [0]
JACKET = "#f28c28"  # the puffer jacket is always orange: a recognizable color stays


def draw(
    ch: Character,
    x: float,
    y: float,
    height: float,
    *,
    sch: Scheme | None = None,
    look: str | None = None,
    style: KitStyle | None = None,
    prefix: str | None = None,
) -> Drawn:
    """Draw ``ch`` standing on (x, y) at ``height`` scene units tall (about the top of its head to the ground)."""
    sch = sch or scheme()
    style = style or kit_style(look)
    kind = ch.kind if ch.kind in KINDS else "ghost"
    pose = POSES.get(ch.pose, POSES["stand"])
    expression = ch.expression if ch.expression in EXPRESSIONS else "happy"
    c = coat(kind, sch, style, ch.variant)
    _counter[0] += 1
    natural_height = 300.0
    s = height / natural_height
    if style.head != 1.0:
        s *= 1.0
    p = Painter(style, c.line, prefix or f"k{_counter[0]}", scale=s, ground=c.top if style.shading == "line" else "none")
    if kind == "ghost":
        b = _ghost(c, p, pose)
    elif kind == "dog":
        b = _dog(c, p, pose)
    elif kind == "cat":
        b = _cat(c, p, pose)
    elif kind == "person":
        b = _person(c, p, pose, ch.variant)
    else:
        b = _robot(c, p, pose)

    parts: list[str] = []
    acc_back, acc_front = _accessory(ch.accessory, b, c, p, kind)
    parts += [acc_back, *b.back]
    tuck_at = len(parts)

    sleeve = ch.accessory == "jacket"
    if sleeve:
        b.arm_color = JACKET
        b.tuck = False
    # Arms: shoulders sit inside the body, so the limb always connects.
    hands: dict[str, Point] = {}
    arm_parts, hand_parts, tucked, prop_back, prop_front = [], [], [], "", ""
    for side, arm, shoulder in (("right", pose.right, b.shoulders[0]), ("left", pose.left, b.shoulders[1])):
        is_rest = arm in (REST_R, REST_L)
        if b.rest and is_rest:
            arm = b.rest[0] if side == "right" else b.rest[1]
        target = _target(arm, shoulder, b)
        hands[side] = target
        inset = (shoulder[0] * 0.82, shoulder[1] + 4)
        if b.hand == "paw" and is_rest:
            inset = (shoulder[0] * 0.95, -72)
        bend = 0.04 if b.hand == "paw" and is_rest else arm.bend
        limb = _limb(inset, target, bend)
        width = b.arm_w * (1.12 if sleeve else 1.0)
        if b.tuck and not arm.to:
            # The whole limb sits behind the body: only the part that pokes out shows, so it grows out of the side.
            tucked.append(p.hose(limb, b.arm_color, width))
        else:
            arm_parts.append(p.hose(limb, b.arm_color, width))
        if side == "right" and ch.prop != "none":
            prop_back, prop_front = _prop(ch.prop, target, c, p)
        if b.tuck and arm.hand == "mitten" and not arm.to and not (side == "right" and ch.prop != "none"):
            # A ghost's resting arm ends in the hose's own round tip: a soft flipper, not a ball on a stick.
            hand_parts.append("")
            continue
        hand_parts.append(_hand(b.hand, arm.hand, target, shoulder, b.arm_w * 1.25, b.hand_color, p))

    hx, hy, hr = b.head
    u = b.face_u
    ex_back, ex_front = extras(EXPRESSIONS[expression].extras, hx, hy, hr, u, c, c.line if c.line != "none" else c.eye)
    face_svg = draw_face(
        expression,
        b.face[0],
        b.face[1],
        u,
        c,
        style,
        spacing=b.spacing,
        mouth_dy=b.mouth_dy,
        animal=b.animal,
        eye_color=b.eye_color,
    )
    hand_on_face = pose.right.to in ("face", "brow", "chin")
    parts[tuck_at:tuck_at] = tucked
    parts += [ex_back, *b.body, face_svg]
    parts += b.over
    parts.append(acc_front)
    parts.append(prop_back)
    parts += arm_parts
    parts += hand_parts
    parts.append(prop_front)
    parts.append(ex_front)
    if hand_on_face:
        # A hand on the face sits over the eyes and mouth.
        parts.append(hand_parts[0])

    inner = "".join(x_ for x_ in parts if x_)
    lean = pose.lean
    mirror = ch.facing == "left"
    sx = -s if mirror else s
    transform = f"translate({f(x)},{f(y)}) scale({f(sx)},{f(s)})" + (f" rotate({f(lean)} 0 -40)" if lean else "")
    defs = f"<defs>{''.join(p.defs)}</defs>" if p.defs else ""
    filt = ""
    if style.wobble:
        fid = f"{p.prefix}-wob"
        defs += (
            f'<defs><filter id="{fid}" x="-10%" y="-10%" width="120%" height="120%"><feTurbulence type="fractalNoise" '
            f'baseFrequency="0.014" numOctaves="1" seed="{_counter[0] % 97}"/><feDisplacementMap in="SourceGraphic" scale="{f(4 / s)}" '
            f'xChannelSelector="R" yChannelSelector="G"/></filter></defs>'
        )
        filt = f' filter="url(#{fid})"'
    svg = f'{defs}<g transform="{transform}"{filt}>{inner}</g>'

    def scene_point(pt: Point) -> Point:
        px, py = pt
        if lean:
            a = math.radians(lean)
            px, py = px * math.cos(a) - (py + 40) * math.sin(a), px * math.sin(a) + (py + 40) * math.cos(a) - 40
        return x + (-px if mirror else px) * s, y + py * s

    anchors = {
        "head_top": scene_point((hx, b.top)),
        "head": scene_point((hx, hy)),
        "mouth": scene_point((b.face[0], b.face[1] + b.mouth_dy)),
        "hand_r": scene_point(hands["right"]),
        "hand_l": scene_point(hands["left"]),
        "seat": scene_point(b.seat),
        "feet": (x, y),
    }
    half = max(b.width, 110) * s
    extra = 70 * s if kind in ("ghost", "dog", "cat") else 0
    left = x - (half + (extra if not mirror else 0))
    right = x + half + (extra if mirror else 0)
    xs = [left, right, *(pt[0] for pt in anchors.values())]
    ys = [y, anchors["head_top"][1], *(pt[1] for pt in anchors.values())]
    return Drawn(svg, anchors, (min(xs), min(ys), max(xs), max(ys)))


def menu() -> str:
    """The cast, expressions, poses, accessories and props, as a prompt reads them."""
    from inferno_ghostwriter.images.kit.face import EXPRESSION_HINTS

    kinds = "; ".join(f"`{k}` ({h})" for k, h in KIND_HINTS.items())
    exprs = ", ".join(f"`{e}` ({h})" for e, h in EXPRESSION_HINTS.items())
    poses = ", ".join(f"`{k}` ({v.hint})" for k, v in POSES.items())
    return (
        f"Characters: {kinds}.\nExpressions: {exprs}.\nPoses: {poses}.\n"
        f"Accessories: {', '.join(f'`{a}`' for a in ACCESSORIES)}.\nHand props: {', '.join(f'`{a}`' for a in PROPS)}."
    )
