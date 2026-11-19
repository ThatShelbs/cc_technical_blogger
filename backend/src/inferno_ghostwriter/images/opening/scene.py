# ruff: noqa: E501
"""Visual-metaphor openers staged from the kit: Claude directs, code draws.

A ``SceneSpec`` names a layout, a backdrop, up to three kit characters (warm, appealing, whole), kit props, at most one
custom object Claude draws for this post's metaphor (in its own 600x500 box, linted and snapped to the scheme) and up
to four short labels. Code places everything from the layout, so the focal point, the rule of thirds and the 5:2 crop
band are right every time, and text is fitted, never overflowing.
"""

from __future__ import annotations

from dataclasses import dataclass

from inferno_ghostwriter.images.base import ImageProviderError
from inferno_ghostwriter.images.kit import Character, draw
from inferno_ghostwriter.images.kit import props as kp
from inferno_ghostwriter.images.kit.face import EXPRESSIONS
from inferno_ghostwriter.images.kit.props import Stage
from inferno_ghostwriter.images.kit.rig import ACCESSORIES, KINDS, POSES, PROPS
from inferno_ghostwriter.images.lint import lint
from inferno_ghostwriter.images.opening.canvas import SAFE_BOTTOM, SAFE_TOP, Canvas, H, W, render, theme_from_scheme
from inferno_ghostwriter.images.opening.specs import SceneSpec
from inferno_ghostwriter.images.palettes import Scheme, mix
from inferno_ghostwriter.images.render import sanitize_svg

Box = tuple[float, float, float, float]

SLOTS_X = {"far_left": 190, "left": 420, "center": 800, "right": 1180, "far_right": 1410}
GROUND = 800  # feet just under the safe band, so heads and faces sit well inside it
HEIGHTS = {"large": 560, "medium": 430, "small": 300}
OBJECT_W, OBJECT_H = 600, 500


@dataclass(frozen=True)
class Layout:
    id: str
    hint: str
    object_box: Box | None  # x, y, w, h for the custom object (or the main prop)
    slots: tuple[str, ...]  # character slots in order of importance


LAYOUTS: dict[str, Layout] = {
    "hero_left": Layout(
        "hero_left",
        "a big character on the left third reacts to the object on the right",
        (820, 170, 680, 567),
        ("left", "far_left", "center"),
    ),
    "hero_right": Layout(
        "hero_right",
        "the object on the left, a big character on the right third reacts to it",
        (100, 170, 680, 567),
        ("right", "far_right", "center"),
    ),
    "center_stage": Layout(
        "center_stage",
        "the object dead centre and large; small characters at both sides",
        (480, 150, 640, 533),
        ("far_left", "far_right", "left"),
    ),
    "duo": Layout(
        "duo", "two characters face each other across the object between them", (560, 230, 480, 400), ("left", "right", "center")
    ),
    "character": Layout("character", "one big character centre stage with a prop; no custom object", None, ("center", "left", "right")),
    "object": Layout("object", "the object alone, large and centred; no characters", (350, 140, 900, 750), ()),
}
LAYOUT_MENU = "\n".join(f"- `{k}`: {v.hint}" for k, v in LAYOUTS.items())


def _label_box(slot: str, layout: Layout, index: int) -> Box:
    if slot == "object" and layout.object_box is not None:
        x, y, w, _h = layout.object_box
        return (x + w / 2 - 170, max(SAFE_TOP + 4, y - 20), 340, 64)
    x = SLOTS_X.get(slot, SLOTS_X["center"])
    return (x - 160, SAFE_TOP + 6 + (index % 2) * 76, 320, 64)


def _facing(slot: str, focus_x: float) -> str:
    return "right" if SLOTS_X.get(slot, 800) < focus_x else "left"


def compose_scene(spec: SceneSpec, sch: Scheme, look: str = "inferno_flat") -> tuple[bytes, int, int, list[str]]:
    """Draw a scene; returns the PNG and any problems with Claude's object drawing (for a retry)."""
    layout = LAYOUTS.get(spec.layout) or (LAYOUTS["character"] if not spec.object_svg.strip() else LAYOUTS["hero_left"])
    canvas = Canvas(theme_from_scheme(sch))
    st = Stage(sch, look, prefix="op")
    problems: list[str] = []
    focus_x = (layout.object_box[0] + layout.object_box[2] / 2) if layout.object_box else 800

    # Backdrop, then a soft glow behind the focal point that pulls the eye in.
    backdrop = kp.BACKDROPS.get(spec.backdrop) if spec.backdrop != "plain" else None
    parts: list[str] = []
    if backdrop is not None:
        parts.append(backdrop(st, (0, 0, W, H)))
    glow_id = "op-glow"
    st.p.defs.append(
        f'<radialGradient id="{glow_id}"><stop offset="0" stop-color="{sch.glow}" stop-opacity="{0.32 if sch.dark else 0.22}"/>'
        f'<stop offset="1" stop-color="{sch.glow}" stop-opacity="0"/></radialGradient>'
    )
    gx = focus_x if layout.object_box else SLOTS_X.get(layout.slots[0] if layout.slots else "center", 800)
    parts.append(f'<ellipse cx="{gx}" cy="{(SAFE_TOP + SAFE_BOTTOM) / 2}" rx="560" ry="420" fill="url(#{glow_id})"/>')
    # A soft floor shadow line grounds characters on a plain surface.
    if backdrop is None:
        parts.append(
            f'<ellipse cx="800" cy="{GROUND + 6}" rx="760" ry="34" fill="{mix(sch.bg, "#000000", 0.25) if not sch.dark else mix(sch.bg, "#ffffff", 0.06)}" opacity="0.7"/>'
        )

    # Kit props.
    for k, prop in enumerate(spec.props[:3]):
        if prop.name not in kp.PROP_HINTS:
            continue
        size = {"large": 300, "medium": 220, "small": 150}.get(prop.size, 220)
        if layout.object_box is not None and not spec.object_svg.strip() and k == 0:
            x, y, w, h = layout.object_box
            box = (x + w * 0.1, y + h * 0.1, w * 0.8, h * 0.8)
        else:
            cx = SLOTS_X.get(prop.slot, 800)
            box = (cx - size / 2, GROUND - size, size, size)
        parts.append(kp.object_(st, prop.name, box))

    # The custom object: Claude's drawing, linted, snapped to the scheme and fitted to its box.
    if spec.object_svg.strip() and layout.object_box is not None:
        try:
            body = spec.object_svg.strip()
            if not body.lstrip().startswith("<svg"):
                body = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {OBJECT_W} {OBJECT_H}">{body}</svg>'
            report = lint(body, size=(OBJECT_W, OBJECT_H), budget=320, allowed_colors=sch.allowed, what="the object")
            problems += report.problems
            clean = sanitize_svg(report.svg)
            x, y, w, h = layout.object_box
            inner = clean.split(">", 1)[1].rsplit("</svg>", 1)[0] if clean.lstrip().startswith("<svg") else clean
            parts.append(
                f'<svg x="{x}" y="{y}" width="{w}" height="{h}" viewBox="0 0 {OBJECT_W} {OBJECT_H}" preserveAspectRatio="xMidYMid meet" overflow="hidden">{inner}</svg>'
            )
        except ImageProviderError as exc:
            problems.append(f"The object drawing could not be read: {exc}")

    # Characters: whole, on-model, facing the focal point.
    for k, c in enumerate(spec.characters[:3]):
        slot = c.slot if c.slot in SLOTS_X else (layout.slots[k] if k < len(layout.slots) else "center")
        height = HEIGHTS.get(c.size, HEIGHTS["large"])
        if layout.id == "center_stage":
            height = min(height, HEIGHTS["medium"])
        facing = c.facing if c.facing in ("left", "right") else _facing(slot, focus_x)
        ch = Character(
            c.kind if c.kind in KINDS else "ghost",
            c.expression if c.expression in EXPRESSIONS else "happy",
            c.pose if c.pose in POSES else "stand",
            facing,
            c.accessory if c.accessory in ACCESSORIES else "none",
            c.prop if c.prop in PROPS else "none",
            max(0, min(2, c.variant)),
        )
        parts.append(draw(ch, SLOTS_X[slot], GROUND, height, sch=sch, look=look).svg)

    canvas.add(st.defs() + "".join(parts))

    # Labels: pill tags, text fitted inside.
    for k, label in enumerate(spec.labels[:4]):
        text = " ".join(label.text.split()[:4])
        if not text:
            continue
        bx, by, bw, bh = _label_box(label.slot, layout, k)
        canvas.rect((int(bx), int(by), int(bw), int(bh)), sch.accent(0) if sch.dark else sch.deep, rx=32, opacity=0.95)
        canvas.text(
            (int(bx) + 18, int(by) + 8, int(bw) - 36, int(bh) - 16),
            text,
            "label",
            group="labels",
            fill="#14101f" if sch.dark else "#ffffff",
        )

    png, width, height = render(canvas)
    return png, width, height, problems


def scene_menu() -> str:
    from inferno_ghostwriter.images.kit import menu as kit_menu

    return f"Layouts:\n{LAYOUT_MENU}\n{kit_menu()}\n{kp.menu()}"
