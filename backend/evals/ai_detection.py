"""AI-detection eval: how human do Proseferno's posts read next to the author's real posts?

Scores 0-100 (100 = authentic human prose, 0 = almost certainly flagged as AI) for:

1. the author's own posts (calibration: these should score high; if they do not, the
   detector is miscalibrated for this author, not the author for the detector), and
2. every post Proseferno has generated for the persona.

Each post is checked by the deterministic scan (free; calibrated to the author with each
real post held out of its own calibration) and, with --judge, by the Claude judge as well.

The scan alone costs nothing. --judge calls the real Claude API (roughly $0.02-0.05 per post
at the default effort). Run from backend/:

    uv run python evals/ai_detection.py --persona "Shelby"            # scan only, free
    uv run python evals/ai_detection.py --persona "Shelby" --judge --yes
    uv run python evals/ai_detection.py --demo --judge --yes            # wiring check, no API calls
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from proseferno.authenticity import analyze, author_profile
from proseferno.config import Settings, get_settings
from proseferno.db import Persona, Project, Sample
from proseferno.services import build_services
from proseferno.voice import current_voice_profile


def _mean(values: list[int]) -> float | None:
    return round(statistics.fmean(values), 1) if values else None


async def run(args: argparse.Namespace) -> int:
    settings = get_settings()
    if args.demo:
        settings = Settings(data_dir=Path(args.demo_dir), demo=True, _env_file=None)  # type: ignore[call-arg]
    services = build_services(settings)

    with Session(services.engine) as session:
        query = select(Persona).where(Persona.name == args.persona) if args.persona else select(Persona).where(Persona.is_active == True)  # noqa: E712
        persona = session.exec(query).first()
        if persona is None or persona.id is None:
            print("Persona not found. Use --persona NAME (or turn a persona on in the app).")
            return 2
        voice_profile = current_voice_profile(session, persona.id)
        samples = list(session.exec(select(Sample).where(Sample.persona_id == persona.id)))
        projects = [p for p in session.exec(select(Project).where(Project.persona_id == persona.id)) if p.markdown]
    own = [s for s in samples if s.kind == "own" and s.markdown][: args.max_samples]
    if not own and not projects:
        print(f"Persona '{persona.name}' has no posts of their own and no generated posts to score.")
        return 2

    print(f"\nAI-detection eval for '{persona.name}': {len(own)} real post(s), {len(projects)} generated post(s)")
    if args.judge and not args.yes:
        print(f"\n--judge calls the Claude API for {len(own) + len(projects)} posts (a few cents each). Re-run with --yes to proceed.")
        return 1

    usage: dict[str, int] = {}

    def add_usage(values: dict[str, int]) -> None:
        for key, value in values.items():
            usage[key] = usage.get(key, 0) + int(value or 0)

    async def check(markdown: str, calibration: list[Sample]) -> dict[str, Any]:
        return await analyze(
            llm=services.llm,
            settings=settings,
            markdown=markdown,
            voice_profile=voice_profile.markdown if voice_profile else "",
            profile=author_profile(calibration, voice_profile.baseline_stylometrics if voice_profile else None),
            use_judge=args.judge,
            usage=add_usage,
        )

    rows: list[dict[str, Any]] = []
    for sample in own:
        # Hold the post out of its own calibration so it cannot excuse itself.
        result = await check(sample.markdown, [s for s in samples if s.id != sample.id])
        rows.append({"kind": "real", "title": sample.title, **_row(result)})
        print(f"  real       {result['score']:>3}  {sample.title}")
    for project in projects:
        result = await check(project.markdown, samples)
        rows.append({"kind": "generated", "title": project.title, **_row(result)})
        print(f"  generated  {result['score']:>3}  {project.title}")

    real = [r["score"] for r in rows if r["kind"] == "real"]
    generated = [r["score"] for r in rows if r["kind"] == "generated"]
    tells = Counter(label for r in rows if r["kind"] == "generated" for label in r["tells"])
    summary = {
        "persona": persona.name,
        "voice_profile_version": voice_profile.version if voice_profile else None,
        "judge": args.judge,
        "model": settings.model,
        "real_mean": _mean(real),
        "generated_mean": _mean(generated),
        "gap": round(_mean(real) - _mean(generated), 1) if real and generated else None,  # type: ignore[operator]
        "generated_flagged": sum(1 for s in generated if s < 60),
        "top_generated_tells": dict(tells.most_common(6)),
        "usage": usage,
    }

    out_dir = settings.data_dir / "evals"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    (out_dir / f"ai-detection-{stamp}.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2), encoding="utf-8")
    report = [
        f"# AI-detection eval: {persona.name}",
        "",
        f"- Voice profile v{summary['voice_profile_version']}; {'scan + Claude judge' if args.judge else 'scan only'}",
        "- Score: 100 = authentic human prose, 0 = almost certainly flagged as AI-generated",
        f"- **Real posts: {summary['real_mean']}** (calibration; should be high)",
        f"- **Generated posts: {summary['generated_mean']}** "
        f"({summary['generated_flagged']} of {len(generated)} below 60, likely to be flagged by detectors)",
        f"- Gap (real - generated): {summary['gap']} (0 = indistinguishable)",
        "",
        "Most common tells in generated posts: " + (", ".join(f"{k} ({v})" for k, v in tells.most_common(6)) or "none"),
        "",
        "| Post | Kind | Score | Scan | Judge |",
        "|---|---|---|---|---|",
        *(
            f"| {r['title']} | {r['kind']} | {r['score']} | {r['scan_score']} | {'-' if r['judge_score'] is None else r['judge_score']} |"
            for r in rows
        ),
    ]
    report_path = out_dir / f"ai-detection-{stamp}.md"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n" + "\n".join(report))
    print(f"\nSaved {report_path}")
    return 0


def _row(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "score": result["score"],
        "scan_score": result["scan_score"],
        "judge_score": result["judge_score"],
        "tells": [s["label"] for s in result["signals"] if s["penalty"] > 0],
        "flagged": result["flagged"][:5],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--persona", help="Persona name (default: the active persona).")
    parser.add_argument("--judge", action="store_true", help="Also ask the Claude judge (costs money; needs --yes).")
    parser.add_argument("--max-samples", type=int, default=20, help="Score at most this many of the author's own posts.")
    parser.add_argument("--yes", action="store_true", help="Confirm that you accept the API cost of --judge.")
    parser.add_argument("--demo", action="store_true", help="Use canned responses (no API calls) to check the wiring.")
    parser.add_argument("--demo-dir", default=str(Path("..") / "data" / "demo"), help="Data folder to use with --demo.")
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
