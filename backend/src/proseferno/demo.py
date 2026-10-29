"""Demo mode: a deterministic stand-in for Claude.

Used by the test suite and by ``proseferno --demo``, which lets you click
through the whole app with canned responses: no API keys, no cost.
"""

from __future__ import annotations

import asyncio
import io
import itertools
import json
import random
import re
from typing import Any

from PIL import Image
from pydantic import BaseModel

from proseferno.llm.base import Citation, OnDelta, ResearchResult, SystemBlock, UsageSink

VOICE_PROFILE = """# Voice Profile: Test Persona

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
        if task == "voice profile synthesis":
            text = VOICE_PROFILE
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
            "callbacks": [
                {
                    "kind": "key_concept",
                    "idea": "Humans compare lengths far better than angles.",
                    "introduce_in": 0,
                    "revisit_in": [1],
                    "payoff": "The closing advice is just this idea, applied.",
                },
                {
                    "kind": "running_joke",
                    "idea": "The author's ongoing feud with the office pie chart.",
                    "introduce_in": -1,
                    "revisit_in": [0, 1],
                    "payoff": "The meme declares a winner.",
                },
            ],
            "image_slots": [
                {"slot_id": "hero", "kind": "hero", "section_index": -1, "purpose": "Thumbnail", "brief": "A sad pie"},
                {"slot_id": "x1", "kind": "diagram", "section_index": 0, "purpose": "Show why pies mislead", "brief": "Flow diagram"},
                {"slot_id": "x2", "kind": "chart", "section_index": 1, "purpose": "Compare accuracy", "brief": "Bar chart"},
                {"slot_id": "meme", "kind": "meme", "section_index": 1, "purpose": "Closing laugh", "brief": "Pie meme"},
            ],
            "tags": ["Data Visualization", "Charts"],
        }
    if name == "PostEdits":
        return _post_edits(prompt)
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
            "callbacks": 7,
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
        # Edits of memes made before the meme catalog existed.
        return {"svg": HERO_SVG, "alt": "A pie-chart robot", "caption": "Pie logic", "top_text": "Pie chart", "bottom_text": "Bar chart"}
    if name == "MemeIdeas":
        return meme_ideas_payload(prompt)
    if name == "MemeBuild":
        match = re.search(r"Format `([a-z0-9_]+)`", prompt)
        return meme_build_payload(match.group(1) if match else "classic_caption")
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


DEMO_TWEAK = " Honestly, they are mostly round because nobody stopped them."


def _post_edits(prompt: str) -> dict[str, Any]:
    """One small edit to the post in the prompt: append a sentence to its first body paragraph."""
    feedback = prompt.split("<feedback>", 1)[-1].split("</feedback>", 1)[0].lower()
    post = prompt.split("<post>", 1)[-1].split("</post>", 1)[0]
    paragraph = next(
        (
            line.strip()
            for line in post.splitlines()
            if line.strip() and not line.lstrip().startswith(("#", "*", "{{", "```", "-", ">", "|"))
        ),
        "",
    )
    image_changes = []
    if "image" in feedback or "diagram" in feedback:
        image_changes = [{"slot_id": "img2", "brief": "A flow diagram of how a pie chart hides the difference between slices"}]
    return {
        "summary": "Added a wry aside to the opening." + (" Redrew the diagram with a new idea." if image_changes else ""),
        "edits": [{"find": paragraph, "replace": paragraph + DEMO_TWEAK}] if paragraph else [],
        "image_changes": image_changes,
    }


def png_bytes(width: int = 64, height: int = 48, color: str = "#ed6925") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format="PNG")
    return buffer.getvalue()


# -- Memes ---------------------------------------------------------------------------
# One canned build per format: demo mode cycles through them, tests render every one,
# and scripts/meme_gallery.py lays them out for a visual review.

DEMO_BOT = (
    '<symbol id="bot" viewBox="0 0 200 260">'
    '<ellipse cx="100" cy="250" rx="70" ry="9" fill="#000004" opacity="0.25"/>'
    '<rect x="45" y="140" width="110" height="105" rx="28" fill="#4a0c6b"/>'
    '<rect x="68" y="160" width="64" height="34" rx="10" fill="#ed6925"/>'
    '<path d="M45,165 C20,150 14,128 22,110" stroke="#4a0c6b" stroke-width="18" fill="none" stroke-linecap="round"/>'
    '<path d="M155,165 C180,150 186,128 178,110" stroke="#4a0c6b" stroke-width="18" fill="none" stroke-linecap="round"/>'
    '<circle cx="22" cy="104" r="13" fill="#f7d13d"/><circle cx="178" cy="104" r="13" fill="#f7d13d"/>'
    '<rect x="30" y="38" width="140" height="110" rx="30" fill="#781c6d"/>'
    '<rect x="44" y="52" width="112" height="80" rx="20" fill="#1b0c41"/>'
    '<ellipse cx="78" cy="88" rx="12" ry="16" fill="#fcffa4"/><ellipse cx="122" cy="88" rx="12" ry="16" fill="#fcffa4"/>'
    '<path d="M84,114 Q100,124 116,114" stroke="#fcffa4" stroke-width="5" fill="none" stroke-linecap="round"/>'
    '<line x1="100" y1="38" x2="100" y2="14" stroke="#781c6d" stroke-width="6"/><circle cx="100" cy="10" r="9" fill="#fb9b06"/>'
    "</symbol>"
)

DEMO_MEME_TEXTS: dict[str, dict[str, str]] = {
    "nope_yep": {"nope": "A pie chart with 14 slices", "yep": "A sorted bar chart nobody can argue with"},
    "pointing_twins": {"left": "Our pie chart", "right": "Our donut chart", "bottom": "Same crime, different pastry"},
    "distracted": {"left": "3D exploding pie", "center": "Me building the dashboard", "right": "A sorted bar chart"},
    "expanding_brain": {
        "level1": "Pie chart",
        "level2": "Bar chart",
        "level3": "Sorted bar chart with direct labels",
        "level4": "Just say the number out loud",
    },
    "this_is_fine": {"bubble": "This is fine.", "fire": "14-slice pie in the board deck", "character": "Me, presenting"},
    "two_buttons": {"left_button": "Make the chart readable", "right_button": "Keep the CEO's favorite pie", "character": "Data analyst"},
    "midwit_bell_curve": {
        "left_says": "Use a bar chart",
        "middle_says": "Well, with a donut, a sunburst and an angle-preserving palette, a pie can work if the slices are...",
        "right_says": "Use a bar chart",
    },
    "gru_plan": {
        "step1": "Make a pie chart",
        "step2": "Add every category",
        "step3": "Nobody can compare the slices",
        "step4": "Nobody can compare the slices",
    },
    "joke_pie_3d": {"title": "What pie charts are good for", "footnote": "Source: every dashboard review, ever"},
    "spurious_correlation": {
        "title": "Pie charts in board decks vs. questionable decisions",
        "series_a": "Pie charts per deck",
        "series_b": "Decisions later reversed",
        "note": "r = 0.98. Correlation: strong. Causation: probably not. Probably.",
    },
    "venn": {"title": "Things that are round", "a": "Pizza", "b": "Pie charts", "c": "Good ideas", "center": "Pizza"},
    "comic_strip_3": {"p1": "Can you add a pie chart to the report?", "p2": "Apple or cherry?", "p3": "...Bar chart it is."},
    "comic_grid_4": {
        "p1": "We need one dashboard everyone trusts.",
        "p2": "One pie chart to rule them all?",
        "p3": "No.",
        "p4": "...Two pie charts?",
    },
    "chat_thread": {
        "channel": "data-viz",
        "m1_name": "Dana Exec",
        "m1": "Love the dashboard! Can we make the bar chart a pie?",
        "m2_name": "Sam Analyst",
        "m2": "It has 14 categories.",
        "m3_name": "Dana Exec",
        "m3": "Perfect, so it'll be colorful.",
        "m4_name": "Sam Analyst",
        "m4": "I'll start the 3D effects. Please tell my family I loved them.",
    },
    "terminal": {
        "title": "zsh - dashboards",
        "cmd1": "python make_chart.py --type pie",
        "out1": "Rendering 14 slices... done.\nWarning: humans cannot compare angles.",
        "cmd2": "python make_chart.py --type pie --force",
        "out2": "Rendering 14 slices... done. Warnings suppressed.",
        "cmd3": "git blame dashboard.png",
        "out3": "fatal: everyone was in that meeting",
    },
    "nutrition_label": {
        "product": "Per 1 Pie Chart",
        "serving": "Serving size: 1 slide (14 slices)",
        "calories": "0",
        "r1_name": "Angles nobody can compare",
        "r1_value": "92%",
        "r2_name": "Legend lookups",
        "r2_value": "140%",
        "r3_name": "Rainbow palette",
        "r3_value": "300%",
        "r4_name": "3D effects",
        "r4_value": "87%",
        "r5_name": "Board approval",
        "r5_value": "100%",
        "r6_name": "Actual insight",
        "r6_value": "2%",
        "footnote": "* Percent Daily Values are based on a 2,000-pixel dashboard. Your stakeholder's values may be higher.",
    },
    "alignment_chart": {
        "title": "Chart alignment chart",
        "lg": "Sorted bar chart, labeled axes",
        "ng": "Small multiples",
        "cg": "A table, honestly",
        "ln": "Line chart with 40 lines",
        "tn": "Default Excel column chart",
        "cn": "Dual-axis chart",
        "le": "Truncated y-axis",
        "ne": "Pie chart with 14 slices",
        "ce": "3D exploding pie in a board deck",
    },
    "classic_caption": {"top": "When the stakeholder asks for a pie chart", "bottom": "with 14 slices"},
}

DEMO_MEME_DATA: dict[str, list[dict[str, Any]]] = {
    "joke_pie_3d": [
        {"label": "Showing two slices", "value": 6, "series": ""},
        {"label": "Diagramming pizza", "value": 9, "series": ""},
        {"label": "Making bar charts look good", "value": 85, "series": ""},
    ],
    "spurious_correlation": [
        {"label": str(year), "value": value, "series": series}
        for series, values in (("a", (2.1, 2.6, 3.0, 3.9, 4.4, 5.1, 5.8, 6.6)), ("b", (11, 13, 14, 19, 21, 24, 28, 31)))
        for year, value in zip(range(2018, 2026), values, strict=True)
    ],
}

_DEMO_MEME_CYCLE = itertools.cycle(DEMO_MEME_TEXTS)


def meme_ideas_payload(prompt: str) -> dict[str, Any]:
    """Five concepts; demo mode cycles the chosen format so each post shows a different one."""
    only = re.search(r"Only use the format `([a-z0-9_]+)`", prompt)
    first = only.group(1) if only else next(_DEMO_MEME_CYCLE)
    others = [f for f in ("nope_yep", "joke_pie_3d", "terminal", "comic_strip_3", "venn") if f != first]
    formats = [first] * 5 if only else [first, *others[:4]]
    concepts = [
        {
            "format": fmt,
            "premise": f"Pie charts, roasted as {fmt.replace('_', ' ')} #{i + 1}.",
            "callback": "The post's claim that people compare lengths better than angles.",
            "texts": [{"slot": slot, "text": text, "speaker": ""} for slot, text in DEMO_MEME_TEXTS.get(fmt, {}).items()],
            "scores": {"relevance": 5, "recognizability": 4, "surprise": 4, "clarity": 5, "voice_fit": 4, "standalone": 4 - i % 2},
        }
        for i, fmt in enumerate(formats)
    ]
    return {"concepts": concepts, "chosen": 0, "why": "It pays off the post's main argument in one glance."}


def meme_build_payload(format_id: str) -> dict[str, Any]:
    from proseferno.images.memes.formats import BY_ID

    fmt = BY_ID.get(format_id) or BY_ID["classic_caption"]
    speakers = itertools.cycle(("left", "right"))
    words = DEMO_MEME_TEXTS.get(fmt.id, {})
    texts = [{"slot": s.name, "text": words.get(s.name, ""), "speaker": next(speakers) if s.bubble else ""} for s in fmt.slots]
    art = []
    for region in fmt.regions:
        _, _, w, h = region.box
        size = min(w, h) * 0.8
        backdrop = (
            f'<rect width="{w}" height="{h}" fill="#f7d13d"/>'
            f'<circle cx="{w / 2}" cy="{h / 2}" r="{size / 2}" fill="#fb9b06" opacity="0.4"/>'
        )
        bot = f'<use href="#bot" x="{(w - size * 0.77) / 2:.0f}" y="{h - size - 10:.0f}" width="{size * 0.77:.0f}" height="{size:.0f}"/>'
        art.append({"region": region.name, "svg": (backdrop if region.opaque else "") + bot})
    return {
        "texts": texts,
        "cast_defs": DEMO_BOT if fmt.regions else "",
        "art": art,
        "data": DEMO_MEME_DATA.get(fmt.id, []),
        "alt": f"A {fmt.name} meme about pie charts. Text: " + " / ".join(t["text"] for t in texts if t["text"]),
        "caption": "Pie logic",
    }
