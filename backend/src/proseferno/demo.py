"""Demo mode: a deterministic stand-in for Claude.

Used by the test suite and by ``proseferno --demo``, which lets you click
through the whole app with canned responses: no API keys, no cost.
"""

from __future__ import annotations

import asyncio
import io
import json
import random
from typing import Any

from PIL import Image
from pydantic import BaseModel

from proseferno.llm.base import Citation, OnDelta, ResearchResult, SystemBlock, UsageSink

VOICE_SOUL = """# Voice Soul: Test Persona

## Soul
Curious data person who explains things with a grin.

## Voice & Tone
- Wry and direct: "Shocking!"

## Images & Captions
Captions read "Source: X; Author: Name; Made with Tool".
**Visual style:** warm flat illustrations in inferno purples and oranges

## Lexicon
Never use: delve
"""

DRAFT = """# Pie Charts Are Lame

*A friendly roast of everyone's favorite circle.*

{{image:hero}}

Pie charts have a fan club. I am not in it. You probably have strong feelings too.

## Why People Love Pies

They look friendly. They are round. Nobody ever got fired for a pie chart, apparently.

{{image:img2}}

## What To Use Instead

Bar charts. Seriously, bar charts. They let you compare values without squinting.

{{image:img3}}

So the next time you reach for a pie, reach for a bar instead. Your readers will thank you.

{{image:meme}}
"""


class FakeLLM:
    def __init__(self, delay: float = 0.0) -> None:
        self.calls: list[dict[str, Any]] = []
        # Seconds between streamed chunks; demo mode uses a small delay so streaming is visible.
        self.delay = delay

    async def structured(
        self,
        *,
        task: str,
        system: list[SystemBlock],
        prompt: str,
        schema: type[BaseModel],
        effort: str,
        max_tokens: int = 16000,
        usage: UsageSink | None = None,
    ) -> Any:
        self.calls.append({"kind": "structured", "task": task, "schema": schema.__name__, "prompt": prompt, "system": system})
        if self.delay:
            await asyncio.sleep(self.delay * 20)
        if usage:
            usage({"input_tokens": 100, "output_tokens": 50, "requests": 1})
        return schema.model_validate(_structured_payload(schema.__name__, prompt))

    async def text(
        self,
        *,
        task: str,
        system: list[SystemBlock],
        prompt: str,
        effort: str,
        max_tokens: int = 64000,
        on_delta: OnDelta | None = None,
        usage: UsageSink | None = None,
    ) -> str:
        self.calls.append({"kind": "text", "task": task, "prompt": prompt, "system": system})
        if task == "voice soul synthesis":
            text = VOICE_SOUL
        elif task == "passage rewrite":
            text = "Bar charts win. Every. Single. Time."
        else:
            text = DRAFT
        if on_delta:
            step = 24 if self.delay else max(1, len(text) // 2)
            for start in range(0, len(text), step):
                if self.delay:
                    await asyncio.sleep(self.delay)
                await on_delta(text[start : start + step])
        if usage:
            usage({"input_tokens": 1000, "output_tokens": 500, "requests": 1})
        return text

    async def research(
        self,
        *,
        system: list[SystemBlock],
        prompt: str,
        effort: str,
        max_searches: int = 8,
        usage: UsageSink | None = None,
    ) -> ResearchResult:
        self.calls.append({"kind": "research", "prompt": prompt})
        return ResearchResult(
            text="# Best practices for technical blogging\n\n## Titles\n- Be specific.",
            citations=[Citation(url="https://example.com/guide", title="Guide")],
        )

    def tasks(self) -> list[str]:
        return [c.get("task", c["kind"]) for c in self.calls]


DIAGRAM_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 675"><rect width="1200" height="675" fill="#fff"/>'
    '<rect x="100" y="250" width="300" height="160" rx="20" fill="#781c6d"/>'
    '<text x="250" y="340" fill="#fcffa4" font-size="28" text-anchor="middle">Data</text></svg>'
)

HERO_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900"><defs>'
    '<linearGradient id="sky" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#1b0c41"/><stop offset=".55" stop-color="#781c6d"/>'
    '<stop offset="1" stop-color="#ed6925"/></linearGradient>'
    '<radialGradient id="sun" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#fcffa4"/>'
    '<stop offset="1" stop-color="#fb9b06"/></radialGradient>'
    '<filter id="soft"><feGaussianBlur stdDeviation="18"/></filter></defs>'
    '<rect width="1600" height="900" fill="url(#sky)"/><circle cx="1180" cy="300" r="190" fill="url(#sun)" opacity=".9"/>'
    '<ellipse cx="800" cy="820" rx="700" ry="80" fill="#000004" opacity=".35" filter="url(#soft)"/>'
    '<g transform="translate(560 260)"><rect x="40" y="180" width="320" height="320" rx="40" fill="#cf4446"/>'
    '<path d="M200 340 L200 180 A160 160 0 0 1 356 304 Z" fill="#fcffa4"/>'
    '<rect x="70" y="40" width="260" height="150" rx="36" fill="#f7d13d"/><circle cx="150" cy="115" r="22" fill="#1b0c41"/>'
    '<circle cx="250" cy="115" r="22" fill="#1b0c41"/><rect x="190" y="0" width="20" height="44" rx="10" fill="#fb9b06"/></g></svg>'
)

CHART_SPEC = json.dumps(
    {
        "title": "Pie vs bar accuracy",
        "data": {"values": [{"chart": "Pie", "accuracy": 62}, {"chart": "Bar", "accuracy": 91}]},
        "mark": "bar",
        "encoding": {"x": {"field": "chart", "type": "nominal"}, "y": {"field": "accuracy", "type": "quantitative"}},
    }
)


DEMO_TITLES = [
    "Put the Pie Down",
    "Your Pie Chart Is Lying to You",
    "Bar Charts, Every Time",
    "I Tried to Love Pie Charts",
    "Pie Charts: A Polite Takedown",
    "Nobody Can Read Your Pie Chart",
    "The Case Against Slices",
    "Stop Making Me Compare Angles",
]


def _structured_payload(name: str, prompt: str = "") -> dict[str, Any]:
    if name == "SampleAnalysis":
        return {
            "summary": "A roast of word clouds.",
            "topic": "Data Visualization",
            "title_pattern": "Blunt opinion as title",
            "hook": "Opens with a trend statistic.",
            "structure": "Problem, story, limitations, alternatives.",
            "voice_traits": ["Wry: 'Shocking!'"],
            "tone": "Playful but informed",
            "sentence_rhythm": "Medium sentences with short punchlines.",
            "reader_relationship": "Talks to the reader as a peer.",
            "humor_devices": ["Sarcastic one-liners"],
            "storytelling": "Personal discovery arc.",
            "teaching_moves": ["Shows bad example then better one"],
            "credibility_moves": ["Cites sources"],
            "image_usage": "Every section has a chart; captions credit source and tool.",
            "closing": "Ends with a call to action.",
            "signature_phrases": ["So you're telling me"],
            "notable_quotes": ["Shocking!"],
            "techniques_to_borrow": ["Use a running joke"],
        }
    if name == "ArticlePlan":
        return {
            "title_options": ["Pie Charts Are Lame", "Stop Baking Pies", "The Pie Chart Problem", "Bars > Pies", "Slice of Truth"],
            "chosen_title": "Pie Charts Are Lame",
            "subtitle": "A friendly roast of everyone's favorite circle.",
            "hook": "Admit to hating pie charts.",
            "sections": [
                {"heading": "Why People Love Pies", "key_points": ["they look friendly"], "approx_words": 300, "include_code": False},
                {"heading": "What To Use Instead", "key_points": ["bar charts"], "approx_words": 300, "include_code": False},
            ],
            "closing": "Reach for a bar.",
            "joke": "A pie chart of things pie charts are good for.",
            "image_slots": [
                {"slot_id": "hero", "kind": "hero", "section_index": -1, "purpose": "Thumbnail", "brief": "A sad pie"},
                {"slot_id": "x1", "kind": "diagram", "section_index": 0, "purpose": "Show why pies mislead", "brief": "Flow diagram"},
                {"slot_id": "x2", "kind": "chart", "section_index": 1, "purpose": "Compare accuracy", "brief": "Bar chart"},
                {"slot_id": "meme", "kind": "meme", "section_index": 1, "purpose": "Closing laugh", "brief": "Pie meme"},
            ],
            "tags": ["Data Visualization", "Charts"],
        }
    if name == "TitleOptions":
        # Shuffled so "New options" visibly changes the list in demo mode.
        return {"title_options": random.sample(DEMO_TITLES, 5)}
    if name == "Critique":
        return {
            "voice": 8,
            "tone": 8,
            "structure": 8,
            "humor_match": 7,
            "education_match": 8,
            "skimmability": 9,
            "image_placement": 8,
            "overall": 8,
            "strengths": ["Punchy"],
            "issues": ["Opening is generic"],
            "revision_instructions": ["Open with a personal confession"],
        }
    if name == "SvgSpec":
        if "**hero**" in prompt or "**illustration**" in prompt:
            return {"svg": HERO_SVG, "alt": "A robot made of a pie chart under a setting sun", "caption": "The saddest pie"}
        return {"svg": DIAGRAM_SVG, "alt": "A diagram", "caption": "How pies mislead"}
    if name == "SvgMemeSpec":
        return {"svg": HERO_SVG, "alt": "A pie-chart robot", "caption": "Pie logic", "top_text": "Pie chart", "bottom_text": "Bar chart"}
    if name == "ChartSpec":
        return {"vega_lite_json": CHART_SPEC, "alt": "Bar chart", "caption": "Accuracy by chart type", "data_is_illustrative": True}
    if name == "PostBrief":
        return {"brief": "Why pie charts mislead\n- angles are hard to compare\n- use sorted bars\n- a tiny matplotlib example"}
    if name == "AIDetectionJudgement":
        return {
            "human_score": 82,
            "verdict": "Reads like the author: specific, opinionated and a little sarcastic.",
            "human_signals": ["Wry one-liners", "A concrete recommendation"],
            "ai_signals": ["The closing line is a tidy summary"],
            "flagged_passages": [
                {
                    "quote": "Your readers will thank you.",
                    "reason": "Stock closing line",
                    "suggestion": "End on a specific, slightly cheeky instruction instead.",
                }
            ],
        }
    if name == "LinkedInPost":
        return {
            "hook": "I stopped making pie charts in 2019. My dashboards got better overnight.",
            "body": "Humans compare lengths far better than angles.\n\nSo the next time you reach for a pie, reach for a sorted bar.\n\n"
            "What chart do you wish would disappear from slide decks?\n\nFull article in the comments.",
            "hashtags": ["DataVisualization", "Analytics", "data viz"],
        }
    if name == "Judgement":
        return {"reasoning": "Passage A has the author's wry asides.", "authentic": "A", "confidence": 3, "similarity": 7}
    raise AssertionError(f"FakeLLM has no payload for {name}")


def png_bytes(width: int = 64, height: int = 48, color: str = "#ed6925") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format="PNG")
    return buffer.getvalue()
