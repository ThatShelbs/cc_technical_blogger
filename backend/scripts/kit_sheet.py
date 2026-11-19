# ruff: noqa: E501
"""Contact sheets of the character kit: every character in every expression, pose and look, and every opener layout.

    uv run python scripts/kit_sheet.py                 # all sheets (free, no model calls)
    uv run python scripts/kit_sheet.py --ramp viridis --surface white

Writes PNGs and an index.html to data/kit-sheet/ (git-ignored). Use it to review a kit change by eye: every character
should look whole, likeable and on-model at thumbnail size and at full size.
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path

from inferno_ghostwriter.images.kit import EXPRESSIONS, KINDS, POSES, STYLES, Character, draw
from inferno_ghostwriter.images.kit import props as kp
from inferno_ghostwriter.images.opening.scene import LAYOUTS, compose_scene
from inferno_ghostwriter.images.opening.specs import SceneSpec
from inferno_ghostwriter.images.palettes import RAMPS, SURFACES, Scheme, scheme
from inferno_ghostwriter.images.render import svg_to_png

ROOT = Path(__file__).resolve().parents[2]
CELL_W, CELL_H = 260, 330


def sheet(sch: Scheme, rows: list[list[Character]], look: str, prefix: str) -> bytes:
    cols = max(len(r) for r in rows)
    width, height = CELL_W * cols, CELL_H * len(rows)
    parts = [
        draw(c, CELL_W // 2 + x * CELL_W, CELL_H - 20 + y * CELL_H, 270, sch=sch, look=look, prefix=f"{prefix}{y}x{x}").svg
        for y, row in enumerate(rows)
        for x, c in enumerate(row)
    ]
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'<rect width="{width}" height="{height}" fill="{sch.bg}"/>{"".join(parts)}</svg>'
    )
    return svg_to_png(svg, width=width, background=sch.bg)[0]


def props_sheet(sch: Scheme) -> bytes:
    names = list(kp.PROP_HINTS)
    cols = 8
    rows = (len(names) + cols - 1) // cols
    st = kp.Stage(sch, "inferno_flat", "ps")
    body = "".join(kp.object_(st, n, (20 + (i % cols) * 220, 20 + (i // cols) * 220, 180, 180)) for i, n in enumerate(names))
    width, height = cols * 220, rows * 220
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"><rect width="{width}" height="{height}" fill="{sch.bg}"/>{st.defs()}{body}</svg>'
    return svg_to_png(svg, width=width, background=sch.bg)[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "kit-sheet")
    parser.add_argument("--ramp", default="inferno", choices=list(RAMPS))
    parser.add_argument("--surface", default="white", choices=list(SURFACES))
    args = parser.parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    sch = scheme(args.ramp, args.surface)
    cards: list[tuple[str, str]] = []

    exprs = list(EXPRESSIONS)
    rows = [[Character(k, e, "stand", "right", "none", "none", i % 3) for i, e in enumerate(exprs)] for k in KINDS]
    (out / "expressions.png").write_bytes(sheet(sch, rows, "inferno_flat", "e"))
    cards.append(("expressions.png", "Every character in every expression"))

    poses = list(POSES)
    rows = [[Character(k, "happy", p, "right", "none", "mug" if "hold" in p else "none") for p in poses] for k in KINDS]
    (out / "poses.png").write_bytes(sheet(sch, rows, "inferno_flat", "p"))
    cards.append(("poses.png", "Every character in every pose"))

    rows = [[Character(k, "beaming", "wave", "right") for k in KINDS] for _ in range(1)]
    for look in STYLES:
        name = f"look-{look}.png"
        (out / name).write_bytes(sheet(sch, rows, look, f"l{look}"))
        cards.append((name, f"The cast in the {look} look"))

    (out / "props.png").write_bytes(props_sheet(sch))
    cards.append(("props.png", "Every kit prop"))

    for layout in LAYOUTS:
        spec = SceneSpec(
            layout=layout,
            characters=[{"kind": "ghost", "expression": "shocked", "pose": "point", "slot": LAYOUTS[layout].slots[0]}]
            if LAYOUTS[layout].slots
            else [],
            props=[{"name": "chart_screen", "slot": "center", "size": "large"}],
            object_svg='<rect x="60" y="60" width="480" height="380" rx="40" fill="#ed6925"/><circle cx="300" cy="250" r="120" fill="#fcffa4"/>',
            labels=[{"text": "The idea", "slot": "object"}],
            alt="",
            caption="",
        )
        png, _, _, _ = compose_scene(spec, sch)
        name = f"scene-{layout}.png"
        (out / name).write_bytes(png)
        cards.append((name, f"Opener layout: {layout}"))

    page = "".join(f'<figure><img src="{html.escape(f)}"><figcaption>{html.escape(c)}</figcaption></figure>' for f, c in cards)
    (out / "index.html").write_text(
        f"<!doctype html><meta charset=utf-8><title>Kit sheet</title><style>body{{font:14px sans-serif;background:#eee}}"
        f"img{{max-width:100%;border:1px solid #ccc}}figure{{margin:24px}}</style>{page}",
        encoding="utf-8",
    )
    print(f"Wrote {len(cards)} sheets to {out / 'index.html'}")


if __name__ == "__main__":
    main()
