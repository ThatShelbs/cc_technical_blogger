"""Render every opening-image template into a gallery for a visual review, or make real openings for your posts.

    uv run python scripts/opening_gallery.py                           # every code template with canned words, free
    uv run python scripts/opening_gallery.py --palette "#0b1d2a #38bdf8 #f472b6"   # the same in a brand palette
    uv run python scripts/opening_gallery.py --real --yes              # real panel-picked openings for your latest posts (costs money)
    uv run python scripts/opening_gallery.py --real --yes --style data_chart --projects 2

Writes PNGs and an index.html to data/opening-gallery/ (git-ignored). Real runs print the panel's scores and the
render review for each opening, so prompt changes can be judged side by side.
"""

from __future__ import annotations

import argparse
import asyncio
import html
import sys
from pathlib import Path

from proseferno.demo import opening_build_payload
from proseferno.images.opening.room import load_state, total
from proseferno.images.opening.specs import OpeningBuild
from proseferno.images.opening.styles import BY_ID, STYLES
from proseferno.images.opening.templates import TEMPLATES, draw

ROOT = Path(__file__).resolve().parents[2]


def demo_cards(out: Path, palette: tuple[str, ...]) -> list[tuple[str, str, str]]:
    cards = []
    for template in TEMPLATES.values():
        build = OpeningBuild.model_validate(opening_build_payload(template.id))
        png, _, _ = draw(template, build, palette)
        (out / f"{template.id}.png").write_bytes(png)
        cards.append((f"{template.id}.png", f"{template.name} ({BY_ID[template.style].label})", build.alt))
    return cards


async def real_cards(out: Path, projects: int, style: str | None) -> list[tuple[str, str, str]]:
    from sqlmodel import Session, col, select

    from proseferno.db import Persona, Project, ProjectImage
    from proseferno.services import build_services
    from proseferno.voice import current_voice_profile

    services = build_services()
    cards = []
    with Session(services.engine) as session:
        rows = list(session.exec(select(Project).where(Project.status == "ready").order_by(col(Project.updated_at).desc()).limit(projects)))
        jobs = []
        for project in rows:
            hero = session.exec(select(ProjectImage).where(ProjectImage.project_id == project.id, ProjectImage.kind == "hero")).first()
            persona = session.get(Persona, project.persona_id)
            profile = current_voice_profile(session, project.persona_id)
            if hero and hero.id is not None and persona:
                jobs.append((project, hero.id, Persona.model_validate(persona.model_dump()), profile.markdown if profile else ""))
    for project, image_id, persona, voice in jobs:
        image = await services.images.create(
            image_id,
            persona=persona,
            title=project.title,
            markdown=project.markdown,
            voice_profile=voice,
            rethink=True,
            opening_style=style,
            brand_kit=project.brand_kit,
        )
        if not image.file_name:
            print(f"Project {project.id}: {image.error}", file=sys.stderr)
            continue
        state = load_state(image.spec) or {}
        for i, entry in enumerate(state.get("concepts", [])):
            mark = "*" if i == state.get("chosen") else " "
            print(f"{mark} {total(entry)[0]:>2}/40 {entry.get('style'):<12} {entry.get('concept', '')[:90]}")
        print(f"  review: {state.get('review')}")
        source = services.storage.image_dir(project.id or 0) / image.file_name
        target = out / f"project{project.id}-{image.file_name}"
        target.write_bytes(source.read_bytes())
        cards.append((target.name, f"{project.title}: {BY_ID[state['style']].label if state.get('style') in BY_ID else ''}", image.alt))
    return cards


def write_index(out: Path, cards: list[tuple[str, str, str]]) -> Path:
    figures = "\n".join(
        f'<figure><div class="band"><img src="{html.escape(src)}" alt="{html.escape(alt)}"></div>'
        f"<figcaption>{html.escape(title)}</figcaption></figure>"
        for src, title, alt in cards
    )
    page = (
        "<!doctype html><meta charset='utf-8'><title>Opening gallery</title><style>"
        "body{font-family:system-ui;background:#1b0c41;color:#fcffa4;margin:24px}"
        "main{display:grid;grid-template-columns:repeat(auto-fill,minmax(520px,1fr));gap:24px}"
        "figure{margin:0;background:#2a1650;padding:12px;border-radius:12px}img{display:block;width:100%;border-radius:8px}"
        # The dashed lines mark the 5:2 band every platform's thumbnail crop keeps.
        ".band{position:relative}.band::after{content:'';position:absolute;left:0;right:0;top:14.4%;bottom:14.4%;"
        "border-top:1px dashed #fcffa480;border-bottom:1px dashed #fcffa480;pointer-events:none}"
        f"figcaption{{margin-top:8px}}</style><h1>Opening gallery</h1><main>{figures}</main>"
    )
    index = out / "index.html"
    index.write_text(page, encoding="utf-8")
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "opening-gallery")
    parser.add_argument("--palette", default="", help="Space-separated brand colors (3+) for the canned templates.")
    parser.add_argument("--real", action="store_true", help="Pitch, judge and build openings for your latest ready posts (costs money).")
    parser.add_argument("--yes", action="store_true", help="Confirm a --real run.")
    parser.add_argument("--projects", type=int, default=3)
    parser.add_argument("--style", help="Constrain --real openings to one style id.")
    args = parser.parse_args()
    if args.style and args.style not in BY_ID:
        parser.error(f"Unknown style {args.style!r}. Choose from: {', '.join(s.id for s in STYLES)}")
    if args.real and not args.yes:
        parser.error("--real calls Claude and costs money; add --yes to confirm.")
    args.out.mkdir(parents=True, exist_ok=True)
    palette = tuple(args.palette.split())
    cards = asyncio.run(real_cards(args.out, args.projects, args.style)) if args.real else demo_cards(args.out, palette)
    print(f"Wrote {len(cards)} opening images: {write_index(args.out, cards)}")


if __name__ == "__main__":
    main()
