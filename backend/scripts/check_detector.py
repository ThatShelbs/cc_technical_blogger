"""Check the AI detectors on real text: human posts should land inside their own range, AI text outside.

    uv run python scripts/check_detector.py --human my_posts/*.md --ai drafts/*.md [--models light,curvature] [--setup]

Each human post is compared with the others (left out of its own calibration), as a post is compared with the
author's own posts in the app. ``--models`` picks the detectors (default: all three; ``light`` is built in and needs no
download). ``--setup`` installs the trained models first (a one-time download of about 1.3 GB). Runs on this computer
only; nothing is sent anywhere.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
from pathlib import Path

from inferno_ghostwriter.authenticity.local_detector import clean_selection, detector_report, get_detector, setup_detector, shutdown, status
from inferno_ghostwriter.config import Settings


def read(paths: list[str]) -> list[tuple[str, str]]:
    return [(Path(p).name, Path(p).read_text(encoding="utf-8")) for p in paths]


async def run(args: argparse.Namespace) -> int:
    models = clean_selection(args.models.split(","))
    settings = Settings(**({"data_dir": Path(args.data_dir)} if args.data_dir else {}), detector_models=models)  # type: ignore[call-arg]
    if args.setup and not status(settings)["ready"]:
        print("Setting up the detector models (one time, about 1.3 GB)...", flush=True)
        print(setup_detector(settings))
    state = status(settings)
    detector = get_detector(settings)
    if not state["ready"] or detector is None:
        print(f"Detectors are not ready: {state['detail']} (use --setup)")
        return 1
    human, ai = read(args.human), read(args.ai)
    rows: list[tuple[str, str, int | None, list[dict[str, object]]]] = []
    try:
        for kind, posts in (("human", human), ("ai", ai)):
            for name, text in posts:
                others = [t for n, t in human if n != name]
                result = await detector_report(settings=settings, detector=detector, markdown=text, author_texts=others)
                rows.append((kind, name, result["score"], result["models"]))
    finally:
        shutdown()
    for kind, name, score, models in rows:
        parts = ", ".join(f"{m['id']}={m['value']} ({m['score']})" for m in models)
        print(f"{kind:5} {score!s:>4}  {name}: {parts}")
    for kind in ("human", "ai"):
        scores = [s for k, _, s, _ in rows if k == kind and s is not None]
        if scores:
            print(f"mean {kind}: {statistics.fmean(scores):.1f} over {len(scores)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--human", nargs="+", required=True, help="Markdown or text files written by the author.")
    parser.add_argument("--ai", nargs="*", default=[], help="Markdown or text files written by a model.")
    parser.add_argument("--models", default="light,curvature,classifier", help="Comma-separated detector ids.")
    parser.add_argument("--data-dir", help="Where the models and calibration live (default: the app's data folder).")
    parser.add_argument("--setup", action="store_true", help="Install and download the models first if needed.")
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
