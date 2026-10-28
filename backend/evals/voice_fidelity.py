"""Voice-fidelity eval: can a careful reader tell Proseferno's post from the real author's?

For each held-out post the author really wrote:

1. Claude extracts the brief the author might have started from (topic + bullets).
2. Proseferno writes a post from that brief, *without* seeing the held-out post
   (it is excluded from the example posts given to the writer).
3. A blind judge sees an excerpt of the real post and of the generated post (in both
   orders, to cancel position bias) and picks which one the author wrote.
4. Measured style (sentence rhythm, paragraphs, "I/you" rate, ...) of both posts is
   scored against the author's baseline.

A judge accuracy near 50% means the generated posts are indistinguishable.

This calls the real Claude API and costs money (roughly $1-2 per held-out post with
Claude Opus 5.5). Run from backend/:

    uv run python evals/voice_fidelity.py --persona "Shelby" --holdout 3 --yes
    uv run python evals/voice_fidelity.py --demo --yes      # wiring check, no API calls
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlmodel import Session, select

from proseferno.authenticity import author_profile, scan
from proseferno.config import Settings, get_settings
from proseferno.db import Persona, Sample
from proseferno.ingest import parse_markdown
from proseferno.ingest.stylometrics import compute, fidelity
from proseferno.llm import LLM, SystemBlock
from proseferno.services import build_services
from proseferno.voice import latest_voice_profile
from proseferno.writer import Dials, resolve, write_post

EXCERPT_WORDS = 700


class PostBrief(BaseModel):
    brief: str = Field(
        description="A one-line topic, then 4-6 bullets: key points, story beats, code or data needs. Do not copy sentences."
    )


class Judgement(BaseModel):
    reasoning: str = Field(description="Two or three sentences comparing the passages to the voice profile.")
    authentic: Literal["A", "B"] = Field(description="The passage the author wrote.")
    confidence: int = Field(description="1 (a guess) to 5 (certain).")
    similarity: int = Field(description="1-10: how alike the two passages' voices are.")


JUDGE_SYSTEM = (
    "You are an expert editor who knows this author's writing intimately (their voice profile is below). "
    "One passage was written by the author; the other by an AI imitating them. Decide which is the author's. "
    "Judge voice, rhythm, humor, word choice and structure, not topic or factual content."
)


class Reporter:
    def __init__(self) -> None:
        self.usage: dict[str, int] = {}

    async def progress(self, fraction: float, message: str) -> None:
        print(f"      {message}")

    async def emit(self, event_type: str, data: Any) -> None:
        return None

    def add_usage(self, usage: dict[str, int]) -> None:
        for key, value in usage.items():
            self.usage[key] = self.usage.get(key, 0) + int(value or 0)


def excerpt(markdown: str, words: int = EXCERPT_WORDS) -> str:
    """Body text without title, images, captions or placeholders, cut at a paragraph boundary."""
    lines = [line for line in markdown.splitlines() if not re.match(r"^\s*(#\s|\[IMAGE\]|\[CAPTION\]|\{\{image:)", line)]
    out: list[str] = []
    count = 0
    for paragraph in "\n".join(lines).split("\n\n"):
        if count >= words:
            break
        out.append(paragraph)
        count += len(paragraph.split())
    return "\n\n".join(out).strip()


async def judge(llm: LLM, settings: Settings, voice_profile: str, real: str, generated: str, reporter: Reporter) -> list[bool]:
    """Ask twice with the order swapped; return whether each verdict picked the real post."""
    verdicts = []
    for real_first in (True, False):
        a, b = (real, generated) if real_first else (generated, real)
        result = await llm.structured(
            task="judge",
            system=[SystemBlock(JUDGE_SYSTEM), SystemBlock(f"# Voice profile\n\n{voice_profile}", cache=True)],
            prompt=f"<passage_a>\n{a}\n</passage_a>\n\n<passage_b>\n{b}\n</passage_b>",
            schema=Judgement,
            effort="high",
            usage=reporter.add_usage,
        )
        picked_real = (result.authentic == "A") == real_first
        verdicts.append(picked_real)
        print(
            f"      judge ({'real first' if real_first else 'generated first'}): picked {'REAL' if picked_real else 'GENERATED'} "
            f"(confidence {result.confidence}, similarity {result.similarity})"
        )
    return verdicts


async def run(args: argparse.Namespace) -> int:
    settings = get_settings()
    if args.demo:
        settings = Settings(data_dir=Path(args.demo_dir), demo=True, _env_file=None)  # type: ignore[call-arg]
    services = build_services(settings)
    llm = services.llm

    with Session(services.engine) as session:
        query = select(Persona).where(Persona.name == args.persona) if args.persona else select(Persona).where(Persona.is_active == True)  # noqa: E712
        persona = session.exec(query).first()
        if persona is None or persona.id is None:
            print("Persona not found. Use --persona NAME (or turn a persona on in the app).")
            return 2
        voice_profile = latest_voice_profile(session, persona.id)
        samples = list(session.exec(select(Sample).where(Sample.persona_id == persona.id)))
    if voice_profile is None:
        print(f"Persona '{persona.name}' has no voice profile yet.")
        return 2
    own = [s for s in samples if s.kind == "own" and 400 <= s.word_count <= args.max_words]
    if len(own) < 2:
        print("Need at least two of the author's own posts between 400 words and --max-words.")
        return 2
    rng = random.Random(args.seed)
    held_out = rng.sample(own, min(args.holdout, len(own) - 1))

    print(f"\nVoice-fidelity eval for '{persona.name}' (voice profile v{voice_profile.version}, model {settings.model})")
    print(f"Holding out {len(held_out)} post(s): " + ", ".join(f'"{s.title}"' for s in held_out))
    if not args.yes:
        print("\nThis calls the Claude API and costs money (roughly $1-2 per held-out post). Re-run with --yes to proceed.")
        return 1

    reporter = Reporter()
    rows: list[dict[str, Any]] = []
    for sample in held_out:
        print(f"\n  - {sample.title}")
        brief = await llm.structured(
            task="brief extraction",
            system=[SystemBlock("You reconstruct the short brief an author started from before writing a post.")],
            prompt=f"Write the brief for this post.\n\n<post>\n{sample.markdown}\n</post>",
            schema=PostBrief,
            effort="low",
            usage=reporter.add_usage,
        )
        others = [s for s in samples if s.id != sample.id]
        dials = resolve(
            Dials(target_words=max(300, min(6000, round(sample.word_count, -2))), image_count=max(2, min(15, sample.image_count or 2))),
            persona,
            brief.brief,
            default_revisions=settings.revision_passes,
        )
        post = await write_post(
            llm=llm, settings=settings, voice_profile=voice_profile, samples=others, prompt=brief.brief, dials=dials, reporter=reporter
        )
        real_text, generated_text = excerpt(sample.markdown), excerpt(post.markdown)
        verdicts = await judge(llm, settings, voice_profile.markdown, real_text, generated_text, reporter)
        generated_doc = parse_markdown(re.sub(r"\{\{image:[^}]+\}\}", "![x](x)", post.markdown))
        rows.append(
            {
                "title": sample.title,
                "brief": brief.brief,
                "judge_picked_real": verdicts,
                "style_score_real": fidelity(voice_profile.baseline_stylometrics, sample.stylometrics)["score"],
                "style_score_generated": fidelity(voice_profile.baseline_stylometrics, compute(generated_doc))["score"],
                # AI-detection scan (free): 100 = reads as human. The held-out post is not in the calibration.
                "human_score_real": scan(sample.markdown, author_profile(others, voice_profile.baseline_stylometrics)).score,
                "human_score_generated": scan(post.markdown, author_profile(others, voice_profile.baseline_stylometrics)).score,
                "generated_markdown": post.markdown,
            }
        )

    verdicts = [v for row in rows for v in row["judge_picked_real"]]
    summary = {
        "persona": persona.name,
        "voice_profile_version": voice_profile.version,
        "model": settings.model,
        "held_out": len(rows),
        "judge_accuracy": round(sum(verdicts) / len(verdicts), 3),
        "style_score_real_mean": round(statistics.fmean(r["style_score_real"] or 0 for r in rows), 1),
        "style_score_generated_mean": round(statistics.fmean(r["style_score_generated"] or 0 for r in rows), 1),
        "human_score_real_mean": round(statistics.fmean(r["human_score_real"] for r in rows), 1),
        "human_score_generated_mean": round(statistics.fmean(r["human_score_generated"] for r in rows), 1),
        "usage": reporter.usage,
    }
    out_dir = settings.data_dir / "evals"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    (out_dir / f"voice-fidelity-{stamp}.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2), encoding="utf-8")
    report = [
        f"# Voice-fidelity eval: {persona.name}",
        "",
        f"- Voice profile v{voice_profile.version}, model `{settings.model}`, {len(rows)} held-out post(s)",
        f"- **Judge accuracy: {summary['judge_accuracy']:.0%}** (50% = indistinguishable from the real author; 100% = always spotted)",
        f"- Style score vs. baseline (out of 100): real posts {summary['style_score_real_mean']}, "
        f"generated {summary['style_score_generated_mean']}",
        f"- Human score from the AI-detection scan (100 = reads as human): real posts {summary['human_score_real_mean']}, "
        f"generated {summary['human_score_generated_mean']} (see evals/ai_detection.py for the full report)",
        "",
        "| Held-out post | Judge picked real (2 orders) | Style real | Style generated | Human real | Human generated |",
        "|---|---|---|---|---|---|",
        *(
            f"| {r['title']} | {sum(r['judge_picked_real'])}/2 | {r['style_score_real']} | {r['style_score_generated']} "
            f"| {r['human_score_real']} | {r['human_score_generated']} |"
            for r in rows
        ),
    ]
    report_path = out_dir / f"voice-fidelity-{stamp}.md"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n" + "\n".join(report))
    print(f"\nSaved {report_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--persona", help="Persona name (default: the active persona).")
    parser.add_argument("--holdout", type=int, default=3, help="How many of the author's posts to hold out.")
    parser.add_argument("--max-words", type=int, default=2500, help="Skip posts longer than this (cost control).")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--yes", action="store_true", help="Confirm that you accept the API cost.")
    parser.add_argument("--demo", action="store_true", help="Use canned responses (no API calls) to check the wiring.")
    parser.add_argument("--demo-dir", default=str(Path("..") / "data" / "demo"), help="Data folder to use with --demo.")
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
