"""Render every meme format into a contact sheet for a visual review.

    uv run python scripts/meme_gallery.py                      # canned demo builds, free
    uv run python scripts/meme_gallery.py --real --yes         # real Claude memes for your latest projects (costs money)
    uv run python scripts/meme_gallery.py --real --yes --format venn --projects 2

Writes PNGs and an index.html to data/meme-gallery/ (git-ignored).
"""

from __future__ import annotations

import argparse
import asyncio
import html
import sys
from pathlib import Path

from proseferno.demo import meme_build_payload
from proseferno.images.memes.compose import compose
from proseferno.images.memes.formats import FAMILIES, FORMATS, get_format
from proseferno.images.memes.specs import MemeBuild

ROOT = Path(__file__).resolve().parents[2]


def demo_cards(out: Path) -> list[tuple[str, str, str]]:
    cards = []
    for fmt in FORMATS:
        build = MemeBuild.model_validate(meme_build_payload(fmt.id))
        png, _, _ = compose(fmt, {t.slot: t for t in build.texts}, {a.region: a.svg for a in build.art}, build.cast_defs, build.data)
        (out / f"{fmt.id}.png").write_bytes(png)
        cards.append((f"{fmt.id}.png", f"{fmt.name} ({FAMILIES[fmt.family]})", build.alt))
    return cards


async def real_cards(out: Path, projects: int, only: str | None) -> list[tuple[str, str, str]]:
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
            meme = session.exec(select(ProjectImage).where(ProjectImage.project_id == project.id, ProjectImage.kind == "meme")).first()
            persona = session.get(Persona, project.persona_id)
            profile = current_voice_profile(session, project.persona_id)
            if meme and meme.id is not None and persona:
                jobs.append((project, meme.id, Persona.model_validate(persona.model_dump()), profile.markdown if profile else ""))
    for project, image_id, persona, voice in jobs:
        image = await services.images.create(
            image_id,
            persona=persona,
            title=project.title,
            markdown=project.markdown,
            voice_profile=voice,
            redraw=True,
            meme_format=only,
        )
        if image.file_name:
            source = services.storage.image_dir(project.id or 0) / image.file_name
            target = out / f"project{project.id}-{image.file_name}"
            target.write_bytes(source.read_bytes())
            cards.append((target.name, f"{project.title}: {image.caption}", image.alt))
        else:
            print(f"Project {project.id}: {image.error}", file=sys.stderr)
    return cards


def write_index(out: Path, cards: list[tuple[str, str, str]]) -> Path:
    figures = "\n".join(
        f'<figure><img src="{html.escape(src)}" alt="{html.escape(alt)}"><figcaption>{html.escape(title)}</figcaption></figure>'
        for src, title, alt in cards
    )
    page = (
        "<!doctype html><meta charset='utf-8'><title>Meme gallery</title><style>"
        "body{font-family:system-ui;background:#1b0c41;color:#fcffa4;margin:24px}"
        "main{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:24px}"
        "figure{margin:0;background:#2a1650;padding:12px;border-radius:12px}img{width:100%;border-radius:8px;background:#fff}"
        f"figcaption{{margin-top:8px}}</style><h1>Meme gallery</h1><main>{figures}</main>"
    )
    index = out / "index.html"
    index.write_text(page, encoding="utf-8")
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "meme-gallery")
    parser.add_argument("--real", action="store_true", help="Ask Claude for new memes for your latest ready projects (costs money).")
    parser.add_argument("--yes", action="store_true", help="Confirm a --real run.")
    parser.add_argument("--projects", type=int, default=3)
    parser.add_argument("--format", dest="only", help="Constrain --real memes to one format id.")
    args = parser.parse_args()
    if args.only and not get_format(args.only):
        parser.error(f"Unknown format {args.only!r}. Choose from: {', '.join(f.id for f in FORMATS)}")
    if args.real and not args.yes:
        parser.error("--real calls Claude and costs money; add --yes to confirm.")
    args.out.mkdir(parents=True, exist_ok=True)
    cards = asyncio.run(real_cards(args.out, args.projects, args.only)) if args.real else demo_cards(args.out)
    print(f"Wrote {len(cards)} memes: {write_index(args.out, cards)}")


if __name__ == "__main__":
    main()
