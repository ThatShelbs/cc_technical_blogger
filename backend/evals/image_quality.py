# ruff: noqa: E501
"""Image-quality eval: opening images and closing memes for a fixed set of posts, judged and timed.

    uv run python evals/image_quality.py --demo              # wiring check with canned responses (free)
    uv run python evals/image_quality.py --yes               # real Claude (costs money: about 8 posts x 2 images)
    uv run python evals/image_quality.py --yes --posts 3 --only meme

Each post is the bundled sample content (the three sample posts) plus short briefs on the blog's core topics. For every
post the eval makes a fresh opening image and a fresh closing meme through the same rooms the app uses, then writes:

- a contact sheet (``index.html``) with each opener as a feed card (thumbnail crop plus title) and each meme,
- per image: the render panel's verdict, what blind readers saw in it, the pitch panel's spread, and seconds taken,
- ``results.json`` with the same numbers, so two runs (before and after a change) can be compared.

Output goes to data/image-eval/<timestamp>/ (git-ignored).
"""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import sys
import time
from datetime import datetime
from importlib import resources
from pathlib import Path
from typing import Any

from inferno_ghostwriter.config import Settings
from inferno_ghostwriter.images.memes import ArtDirection, MemeContext, MemeMaker
from inferno_ghostwriter.images.memes.generate import load_state
from inferno_ghostwriter.images.opening.feedcard import feed_card
from inferno_ghostwriter.images.opening.room import OpeningContext, OpeningRoom, fit_of
from inferno_ghostwriter.images.opening.room import load_state as load_opening_state
from inferno_ghostwriter.images.opening.styles import STYLES

ROOT = Path(__file__).resolve().parents[2]

BRIEFS = [
    (
        "Your A/B test is lying because you peeked",
        "Peeking at running experiments inflates false positives; use sequential tests or fix the sample size.",
    ),
    ("The dashboard nobody opens", "Most dashboards die unread; build for one decision and one reader instead."),
    (
        "From notebook to production without tears",
        "The six things that break when a notebook becomes a service, and how to catch them early.",
    ),
    ("Agents need evals, not vibes", "Building an LLM agent? Write the eval before the prompt; here is a cheap harness."),
    (
        "Correlation is not causation, but it is a clue",
        "How to go from an observed correlation to a causal claim with DAGs and a natural experiment.",
    ),
    (
        "Snowflake costs are a data model problem",
        "Most warehouse bills come from a handful of bad joins and full scans; fix the model, not the warehouse.",
    ),
    ("Leading a data team through the AI hype", "How a data leader decides what to build, what to buy and what to ignore."),
    (
        "Why your chart needs one less color",
        "Every extra color is a question the reader has to answer; design for the one comparison that matters.",
    ),
]


def posts(limit: int) -> list[tuple[str, str, str]]:
    """(title, brief, markdown): the bundled sample posts first, then the short briefs."""
    out = []
    package = resources.files("inferno_ghostwriter.sample_content")
    for name in ("peeking-at-your-ab-test.md", "dashboards-nobody-opens.md", "notebook-to-production.md"):
        text = package.joinpath(name).read_text(encoding="utf-8")
        title = next((line.lstrip("# ").strip() for line in text.splitlines() if line.startswith("# ")), name)
        out.append((title, "", text))
    for title, brief in BRIEFS[3:]:
        out.append((title, brief, f"# {title}\n\n{brief}\n"))
    return out[:limit]


async def run(args: argparse.Namespace) -> int:
    if not args.demo and not args.yes:
        print("A real run calls Claude for every image and costs money. Re-run with --yes (or --demo for a free wiring check).")
        return 2
    if args.demo:
        from inferno_ghostwriter.demo import FakeLLM

        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        llm: Any = FakeLLM()
    else:
        from inferno_ghostwriter.services import build_services

        services = build_services()
        settings, llm = services.settings, services.llm

    out = ROOT / "data" / "image-eval" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    memes = MemeMaker(llm, settings)
    room = OpeningRoom(llm, settings, memes)
    art = ArtDirection(visual_style="clean, warm, modern editorial illustration")
    voice = resources.files("inferno_ghostwriter.sample_content").joinpath("voice_profile.md").read_text(encoding="utf-8")
    results: list[dict[str, Any]] = []
    eligible = tuple(s.id for s in STYLES if s.id != "meme")

    for k, (title, brief, markdown) in enumerate(posts(args.posts)):
        row: dict[str, Any] = {"title": title}
        if args.only in ("", "opening"):
            ctx = OpeningContext(
                title=title, markdown=markdown, voice_profile=voice, brief="", post_brief=brief, humor=5, eligible=eligible
            )
            started = time.monotonic()
            result = await room.make("", ctx, art)
            state = load_opening_state(result.spec) or {}
            (out / f"{k}-opening.png").write_bytes(feed_card(result.png, title, fit=fit_of(state)))
            review = state.get("review") or {}
            row["opening"] = {
                "seconds": round(time.monotonic() - started, 1),
                "style": state.get("style"),
                "scheme": state.get("scheme"),
                "verdict": review.get("verdict") or ("skipped" if review.get("skipped") else ""),
                "why": review.get("why", ""),
                "readings": (review.get("panel") or {}).get("readings", []),
                "match": (review.get("panel") or {}).get("match", []),
                "pitch_totals": [round(float((c.get("panel") or {}).get("total", 0)), 1) for c in state.get("concepts", [])],
            }
        if args.only in ("", "meme"):
            post = MemeContext(title=title, markdown=markdown, voice_profile=voice, brief="", humor=6)
            started = time.monotonic()
            meme = await memes.make("", post, art)
            state = load_state(meme.spec) or {}
            (out / f"{k}-meme.png").write_bytes(meme.png)
            review = state.get("review") or {}
            row["meme"] = {
                "seconds": round(time.monotonic() - started, 1),
                "format": state.get("format"),
                "look": state.get("look"),
                "scheme": state.get("scheme"),
                "verdict": review.get("verdict") or ("skipped" if review.get("skipped") else ""),
                "why": review.get("why", ""),
                "readings": (review.get("panel") or {}).get("readings", []),
                "match": (review.get("panel") or {}).get("match", []),
                "alt": meme.alt,
            }
        results.append(row)
        print(json.dumps(row)[:300])

    (out / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    cards = []
    for k, row in enumerate(results):
        for part in ("opening", "meme"):
            if part in row:
                info = row[part]
                facts = html.escape(json.dumps({key: info[key] for key in info if key not in ("alt",)}, indent=1))
                cards.append(
                    f'<figure><img src="{k}-{part}.png"><figcaption><b>{html.escape(row["title"])}</b> ({part})<pre>{facts}</pre></figcaption></figure>'
                )
    times = [row[p]["seconds"] for row in results for p in ("opening", "meme") if p in row]
    summary = f"{len(results)} posts, {len(times)} images, median {sorted(times)[len(times) // 2] if times else 0}s per image"
    (out / "index.html").write_text(
        "<!doctype html><meta charset=utf-8><title>Image eval</title><style>body{font:14px sans-serif;background:#f4f4f6}"
        "figure{display:inline-block;width:46%;margin:1%;vertical-align:top}img{width:100%;border:1px solid #ccc}"
        f"pre{{white-space:pre-wrap;font-size:11px}}</style><h1>Image eval</h1><p>{summary}</p>{''.join(cards)}",
        encoding="utf-8",
    )
    print(f"{summary}. Wrote {out / 'index.html'}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--demo", action="store_true", help="Canned responses; checks the wiring for free.")
    parser.add_argument("--yes", action="store_true", help="Confirm a real (paid) run.")
    parser.add_argument("--posts", type=int, default=8)
    parser.add_argument("--only", choices=("", "opening", "meme"), default="")
    sys.exit(asyncio.run(run(parser.parse_args())))


if __name__ == "__main__":
    main()
