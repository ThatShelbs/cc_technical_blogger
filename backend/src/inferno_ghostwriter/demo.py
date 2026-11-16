"""Demo mode: a deterministic stand-in for Claude.

Used by the test suite and by ``inferno-ghostwriter --demo``, which lets you click
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

from inferno_ghostwriter import demo_showcase as showcase
from inferno_ghostwriter.llm.base import Citation, OnDelta, ResearchResult, SystemBlock, UsageSink

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


PASSAGES = {
    "rewrite": "Bar charts win. Every. Single. Time.",
    "compact": "Bar charts win.",
    "expand": (
        "Bar charts win. Every. Single. Time. The eye compares lengths faster than angles, "
        "so the answer is on the page before the reader has finished the sentence."
    ),
    "add_source": "Bar charts win. Every. Single. Time. [The guide](https://example.com/guide) says the same.",
    "add_quote": (
        'Bar charts win. Every. Single. Time. As [the saying goes](https://example.com/guide), "Simplicity is the ultimate sophistication."'
    ),
}

# Canned research for each reference kind: (exact words, who said them). Quotes and posts must appear in the research.
REFERENCE_WORDS = {
    "quote": ("All models are wrong, but some are useful.", "George Box"),
    "social_post": ("Sort your bars. That is the whole post.", "Demo Analyst (@demo.analyst)"),
}


class FakeLLM:
    def __init__(self, delay: float = 0.0, *, showcase: bool = False) -> None:
        # showcase: the polished first-impression post (demo_showcase.py) instead of the small test fixtures.
        self.showcase = showcase
        self.calls: list[dict[str, Any]] = []
        self._reference_numbers = itertools.count(1)
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
        images: list[bytes] | None = None,
    ) -> Any:
        self.calls.append(
            {"kind": "structured", "task": task, "schema": schema.__name__, "prompt": prompt, "system": system, "images": len(images or [])}
        )
        if self.delay:
            await asyncio.sleep(self.delay * 20)
        if usage:
            usage({"input_tokens": 100, "output_tokens": 50, "requests": 1})
        return schema.model_validate(_structured_payload(schema.__name__, prompt, self.showcase))

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
        elif task.startswith("passage "):
            passages = showcase.PASSAGES if self.showcase else PASSAGES
            text = passages.get(task.removeprefix("passage "), passages["rewrite"])
        else:
            text = showcase.DRAFT if self.showcase else DRAFT
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
        self.calls.append({"kind": "research", "task": "research", "prompt": prompt})
        kind = re.search(r"^Reference kind: (\w+)", prompt, re.MULTILINE)
        if kind:
            # A new example URL every time, and never one the prompt says was tried (the counter restarts with the app),
            # so a redraw visibly finds something else.
            tried = prompt.split("already tried:", 1)[-1].split("\n", 1)[0] if "already tried:" in prompt else ""
            name = kind.group(1)
            number = next(n for n in self._reference_numbers if f"/{name.replace('_', '-')}/{n}," not in f"{tried},")
            url, title = f"https://example.com/{name.replace('_', '-')}/{number}", f"Example {name.replace('_', ' ')} {number}"
            words, who = (showcase.REFERENCE_WORDS if self.showcase else REFERENCE_WORDS).get(name, ("", ""))
            text = f"Found [{title}]({url})." + (f' {who} said "{words}"' if words else "")
            return ResearchResult(text=text, citations=[Citation(url=url, title=title, cited_text=words)])
        if "\n# Your beat: " in prompt:
            from inferno_ghostwriter.idealab.demo_data import demo_scout

            if self.delay:
                await asyncio.sleep(self.delay * 20)
            if usage:
                usage({"input_tokens": 500, "output_tokens": 300, "requests": 1})
            text, pages = demo_scout()
            return ResearchResult(text=text, citations=[Citation(url=url, title=title) for url, title in pages])
        if prompt.startswith("Find the real numbers for the opening chart"):
            text, url = (showcase.OPENING_RESEARCH, showcase.SOURCE_URL) if self.showcase else (DEMO_OPENING_RESEARCH, DEMO_SOURCE_URL)
            return ResearchResult(text=text, citations=[Citation(url=url, title="Example study", cited_text=text)])
        return ResearchResult(
            text="# Best practices for technical blogging\n\n## Titles\n- Be specific.\n\n"
            'As the saying goes, "Simplicity is the ultimate sophistication."',
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


# A believable voice mix for the waffle chart: categories repeat in this order over the sampled sentences.
_DEMO_MIX = ["Chatty", "Data", "Chatty", "Jokes", "Chatty", "How-to", "Data", "Chatty", "Jokes", "Data"]


def _voice_insights_payload(prompt: str) -> dict[str, Any]:
    section = prompt.split("Numbered sentences", 1)[-1].split("## Output", 1)[0]
    count = len(re.findall(r"^\d+\. ", section, flags=re.MULTILINE))
    return {
        "headline": "Mostly chatty, backed up by data.",
        "tone": [
            "Casual, self-deprecating, a little nerdy",
            "Short punchy sentences, then a quip",
            "Talks straight to you, the reader",
            "Owns mistakes out loud, then moves on",
        ],
        "signature_phrases": ["Here is a confession", "Everyone peeks", "the smallest", "quietly", "Not a real phrase"],
        "steer_clear": ["Hype words: leverage, unlock, game-changer", "Long throat-clearing intros"],
        "mix_categories": [
            {"name": "Chatty", "description": "Talks to the reader like a peer"},
            {"name": "Data", "description": "Numbers, results and evidence"},
            {"name": "Jokes", "description": "Asides and punchlines"},
            {"name": "How-to", "description": "Steps the reader can follow"},
        ],
        "sentence_categories": [{"index": i, "category": _DEMO_MIX[(i - 1) % len(_DEMO_MIX)]} for i in range(1, count + 1)],
        "image_habits": [
            "About one image every few hundred words",
            "Charts right after a colon lead-in",
            "Close with one joke image",
        ],
        "caption_example": "Source: X; Author: Name; Made with Tool",
    }


def _showcase_payload(name: str, prompt: str) -> dict[str, Any] | None:
    """The showcase post's version of a payload, or None to use the shared fixture."""
    if name == "ArticlePlan":
        return showcase.PLAN
    if name == "PostBrief":
        return {"brief": showcase.BRIEF}
    if name == "LinkedInPost":
        return showcase.LINKEDIN
    if name == "TitleOptions":
        return {"title_options": random.sample(showcase.TITLES, 5)}
    if name == "InterviewQuestions":
        return {"questions": showcase.INTERVIEW}
    if name == "SvgSpec":
        if "**hero**" in prompt or "**illustration**" in prompt or "Draw the opening image" in prompt:
            return {
                "svg": showcase.HERO_SVG,
                "alt": "A friendly ghost at a laptop beside a dashboard with a dipping line",
                "caption": "The ghost on call",
            }
        return {
            "svg": showcase.DIAGRAM_SVG,
            "alt": "Four steps before a model ships: eval, guardrails, monitor, rollback",
            "caption": "The pre-launch loop",
        }
    if name == "ChartSpec":
        return {
            "vega_lite_json": showcase.CHART_SPEC,
            "alt": "Line chart of model accuracy falling from 94% to 63% over eight weeks",
            "caption": "Accuracy after launch",
            "data_is_illustrative": True,
        }
    if name == "OpeningIdeas":
        return opening_ideas_payload(
            prompt,
            showcase.OPENING_CONCEPTS,
            "Plain labels; one clear takeaway",
            "Teams' monitoring practices, from a model-operations survey",
        )
    if name == "OpeningBuild":
        match = re.search(r"Template `([a-z0-9_]+)`", prompt)
        return opening_build_payload(match.group(1) if match else "cheat_grid", showcase.OPENING_BUILDS, "Shipping models, measured.")
    if name == "ReferenceEdits":
        return _reference_edits(prompt, showcase.REFERENCE_WORDS)
    if name == "MemeIdeas":
        return meme_ideas_payload(prompt, True)
    if name == "MemeBuild":
        match = re.search(r"Format `([a-z0-9_]+)`", prompt)
        return meme_build_payload(match.group(1) if match else "classic_caption", True)
    return None


def _structured_payload(name: str, prompt: str = "", is_showcase: bool = False) -> dict[str, Any]:
    if is_showcase and (payload := _showcase_payload(name, prompt)) is not None:
        return payload
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
        return _humanize_edits(prompt) if "<targets>" in prompt else _post_edits(prompt)
    if name == "TwinVerdicts":
        return _twin_verdicts(prompt)
    if name == "InterviewQuestions":
        return {"questions": DEMO_INTERVIEW}
    if name == "ImageTextEdits":
        return _image_text_edits(prompt)
    if name == "ImagePlacement":
        return _image_placement(prompt)
    if name == "ReferencePlan":
        return _reference_plan(prompt)
    if name == "ReferenceEdits":
        return _reference_edits(prompt)
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
    if name == "OpeningIdeas":
        return opening_ideas_payload(prompt)
    if name == "OpeningVerdict":
        return opening_verdict_payload(prompt)
    if name == "OpeningBuild":
        match = re.search(r"Template `([a-z0-9_]+)`", prompt)
        return opening_build_payload(match.group(1) if match else "cheat_grid")
    if name == "RenderReview":
        return {"passes": True, "clickability": 8, "craft": 8, "problems": [], "fix": ""}
    if name == "SvgSpec":
        if "**hero**" in prompt or "**illustration**" in prompt or "Draw the opening image" in prompt:
            return {"svg": HERO_SVG, "alt": "A ghost made of a pie chart under a setting sun", "caption": "The saddest pie"}
        return {"svg": DIAGRAM_SVG, "alt": "A diagram", "caption": "How pies mislead"}
    if name == "SvgMemeSpec":
        # Edits of memes made before the meme catalog existed.
        return {"svg": HERO_SVG, "alt": "A pie-chart ghost", "caption": "Pie logic", "top_text": "Pie chart", "bottom_text": "Bar chart"}
    if name == "MemeIdeas":
        return meme_ideas_payload(prompt)
    if name == "MemeBuild":
        match = re.search(r"Format `([a-z0-9_]+)`", prompt)
        return meme_build_payload(match.group(1) if match else "classic_caption")
    if name == "MemeVerdict":
        return meme_verdict_payload(prompt)
    if name == "MemeReview":
        return {"passes": True, "funny": 8, "craft": 8, "problems": [], "fix": ""}
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
    if name == "VoiceInsights":
        return _voice_insights_payload(prompt)
    if name == "Judgement":
        return {"reasoning": "Passage A has the author's wry asides.", "authentic": "A", "confidence": 3, "similarity": 7}
    if name == "EvolutionPlan":
        return {
            "summary": "You trimmed the throat-clearing and swapped abstract lines for a concrete example.",
            "items": [
                {
                    "area": "Voice & Tone",
                    "change": "Open each section with the concrete example, then name the rule.",
                    "evidence": "You moved the bar-chart example above the explanation.",
                    "target": "profile",
                },
                {
                    "area": "Lexicon",
                    "change": "Cut hedges like 'it is worth noting'; say the thing.",
                    "evidence": "Removed: 'It is worth noting that'.",
                    "target": "profile",
                },
                {
                    "area": "Humor",
                    "change": "End a section on a one-line aside when the point is already made.",
                    "evidence": "Added: 'Honestly, it only misbehaved because nobody stopped them.'",
                    "target": "playbook",
                },
            ],
        }
    if name == "SecretSauce":
        return {
            "summary": "The title promised a fight and the post delivered one, with a fix readers could use the same day.",
            "items": [
                {
                    "area": "Titles",
                    "change": "Pick a side in the title and defend it in the first paragraph.",
                    "evidence": "'Pie Charts Are Lame' then 'I am not in it.'",
                    "target": "playbook",
                },
                {
                    "area": "Structure Blueprint",
                    "change": "Pair every complaint with a replacement the reader can use today.",
                    "evidence": "'What To Use Instead' follows the roast.",
                    "target": "playbook",
                },
            ],
        }
    if name == "ProfileEdits":
        # The Lexicon heading is in every demo and sample profile; the second change is left for the fallback rule.
        return {
            "summary": "Added a rule to the Lexicon.",
            "edits": [{"item": "c1", "find": "## Lexicon", "replace": "## Lexicon\n\n- Lead with the concrete example, then the rule."}],
        }
    if name == "ImprovementPlan":
        return {
            "weakness": "The focal point competes with the background.",
            "improvements": ["Enlarge the focal element and calm the background", "Cut any text that repeats the caption"],
            "keep": ["The central metaphor"],
            "fresh_angle": "Show the same idea from a surprising viewpoint.",
        }
    if name in ("TrendDigest", "IdeaBatch", "IdeaRanking"):
        from inferno_ghostwriter.idealab import demo_data

        return {"TrendDigest": demo_data.demo_digest, "IdeaBatch": demo_data.demo_batch, "IdeaRanking": demo_data.demo_ranking}[name](
            prompt
        )
    raise AssertionError(f"FakeLLM has no payload for {name}")


DEMO_TWEAK = " Honestly, it only misbehaved because nobody stopped them."


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


DEMO_HUMANIZE = " Ask me how I know: one Tuesday, one dashboard, one very confused VP."
DEMO_INTERVIEW = [
    "What is the worst pie chart you have ever had to defend in a meeting?",
    "What finally made you switch to bar charts?",
    "Who is this post really for: analysts, or the people who ask them for charts?",
    "What is the one rule you would tape to every analyst's monitor?",
]


def _humanize_edits(prompt: str) -> dict[str, Any]:
    """Give the first target that appears in the post a specific, lived-in aside."""
    post = prompt.split("<post>", 1)[-1].split("</post>", 1)[0]
    targets = re.findall(r"<target number=\"\d+\"[^>]*>\n(.*?)\n</target>", prompt, flags=re.S)
    quote = next((t.strip() for t in targets if t.strip() and t.strip() in post), "")
    return {
        "summary": "Gave the most machine-like passage a concrete moment.",
        "edits": [{"find": quote, "replace": quote + DEMO_HUMANIZE}] if quote else [],
        "image_changes": [],
    }


def _twin_verdicts(prompt: str) -> dict[str, Any]:
    """Alternate the pick; fairly sure each time, so a demo post shows one caught passage and one that passed."""
    count = int(m.group(1)) if (m := re.search(r"Here are (\d+) pairs", prompt)) else 0
    return {
        "verdicts": [
            {
                "pair": i,
                "human": "A" if i % 2 else "B",
                "confidence": 75,
                "giveaway": "Every sentence lands with the same tidy rhythm" if i % 2 else "",
            }
            for i in range(1, count + 1)
        ]
    }


DEMO_IMAGE_SYNC = " The picture changed, so this line did too."
DEMO_PLACEMENT_EDIT = " The diagram below shows it."


def _paragraphs(post: str) -> list[str]:
    return [p.strip() for p in post.split("\n\n") if p.strip()]


def _image_text_edits(prompt: str) -> dict[str, Any]:
    """Like a careful editor: touch the text only when a changed image's format or style really changed."""
    changes = prompt.split("<post>", 1)[0].split("### `")[1:]
    post = prompt.split("<post>", 1)[-1].split("</post>", 1)[0]
    paragraphs = _paragraphs(post)
    edits = []
    for block in changes:
        slot = block.split("`", 1)[0]
        was, _, now = block.partition("Now:")
        key = lambda text: [line for line in text.splitlines() if line.startswith(("Format:", "Style:"))]  # noqa: E731
        if key(was) == key(now):
            continue
        tag = "{{image:" + slot + "}}"
        at = next((i for i, p in enumerate(paragraphs) if p == tag), None)
        before = next((p for p in reversed(paragraphs[: at or 0]) if not p.startswith(("#", "{", "```", "|", ">", "-"))), "")
        if before:
            edits.append({"find": before, "replace": before + DEMO_IMAGE_SYNC})
    return {"summary": "Matched the text to the new image." if edits else "", "edits": edits}


def _image_placement(prompt: str) -> dict[str, Any]:
    """A diagram right after the paragraph that holds the highlight, with one sentence pointing at it."""
    selection = prompt.split("<highlight>", 1)[-1].split("</highlight>", 1)[0].strip()
    post = prompt.split("<post>", 1)[-1].split("</post>", 1)[0]
    paragraph = next((p for p in _paragraphs(post) if selection and selection in p), selection)
    return {
        "kind": "diagram",
        "purpose": "Show the idea the highlighted passage describes",
        "brief": "A flow diagram of: " + selection[:200],
        "anchor_text": paragraph,
        "edits": [{"find": paragraph, "replace": paragraph + DEMO_PLACEMENT_EDIT}] if paragraph else [],
        "summary": "Added a diagram after that paragraph and pointed to it.",
    }


_REFERENCE_PLACEMENT = {
    "source": "inline",
    "quote": "blockquote",
    "social_post": "blockquote",
    "resource": "go_deeper",
    "related_article": "go_deeper",
}


def _reference_plan(prompt: str) -> dict[str, Any]:
    """Anchor references in the first sentence of each plain paragraph that has no link yet."""
    count = int(m.group(1)) if (m := re.search(r"Plan exactly (\d+)", prompt)) else 5
    kinds_line = m.group(1) if (m := re.search(r"Kinds you may use: (.+)", prompt)) else ""
    kinds = [k.strip() for k in kinds_line.split(",") if k.strip()] or list(_REFERENCE_PLACEMENT)
    post = prompt.split("<post>", 1)[-1].split("</post>", 1)[0]
    paragraphs = [
        block.strip()
        for block in post.split("\n\n")
        if block.strip() and not block.lstrip().startswith(("#", "*", "{{", "```", "-", ">", "|")) and "](http" not in block
    ]
    anchors = iter(re.split(r"(?<=[.!?])\s", p, maxsplit=1)[0] for p in paragraphs)
    slots: list[dict[str, Any]] = []
    for kind in itertools.islice(itertools.cycle(kinds), count * 2):
        if len(slots) >= count:
            break
        placement = _REFERENCE_PLACEMENT.get(kind, "inline")
        anchor = "" if placement == "go_deeper" else next(anchors, None)
        if anchor is None:
            continue
        slots.append({"kind": kind, "placement": placement, "anchor": anchor, "purpose": f"A {kind} for the reader", "query": kind})
    return {"slots": slots}


_SLOT_RE = re.compile(
    r'<slot id="(?P<id>[^"]+)" kind="(?P<kind>[^"]+)" placement="(?P<placement>[^"]+)">\nAnchor: (?P<anchor>.*?)\nPurpose:'
    r".*?Sources:\n- \[(?P<title>[^\]]*)\]\((?P<url>[^)]+)\)",
    re.DOTALL,
)


def _reference_edits(prompt: str, reference_words: dict[str, tuple[str, str]] = REFERENCE_WORDS) -> dict[str, Any]:
    """Work each slot's first source into its anchor: a link, a blockquote, or a "Go deeper" line."""
    edits = []
    for m in _SLOT_RE.finditer(prompt):
        kind, placement, anchor, title, url = m["kind"], m["placement"], m["anchor"], m["title"], m["url"]
        words, who = reference_words.get(kind, ("", ""))
        if placement == "go_deeper":
            find, replace = "", f"- [{title}]({url}) — worth a look if you want more."
        elif placement == "blockquote" and words:
            find, replace = anchor, f'{anchor}\n\n> "{words}" — [{who}]({url})'
        elif words:
            find, replace = anchor, f'{anchor} As [{who}]({url}) put it, "{words}"'
        else:
            find, replace = anchor, f"{anchor} [{title}]({url}) says the same."
        edits.append({"slot": m["id"], "find": find, "replace": replace, "url": url, "title": title, "speaker": who, "quote": words})
    return {"go_deeper_heading": "Go deeper", "edits": edits}


def png_bytes(width: int = 64, height: int = 48, color: str = "#ed6925") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format="PNG")
    return buffer.getvalue()


# -- Memes ---------------------------------------------------------------------------
# One canned build per format: demo mode cycles through them, tests render every one,
# and scripts/meme_gallery.py lays them out for a visual review.

DEMO_GHOST = (
    '<symbol id="ghost" viewBox="0 0 200 260">'
    '<ellipse cx="100" cy="250" rx="70" ry="9" fill="#000004" opacity="0.25"/>'
    '<path d="M30 235 C14 130 40 30 100 30 C160 30 186 130 170 235 C156 214 140 246 124 228 C112 248 92 214 76 232 C62 244 44 214 30 235 Z" fill="#a52c60"/>'
    '<path d="M44 225 C32 140 54 50 100 50 C146 50 168 140 156 225 C142 208 130 232 116 216 C104 234 90 208 76 222 C64 232 54 210 44 225 Z" fill="#ed6925" opacity="0.85"/>'
    '<ellipse cx="78" cy="108" rx="12" ry="18" fill="#1b0c41"/><ellipse cx="122" cy="108" rx="12" ry="18" fill="#1b0c41"/>'
    '<ellipse cx="81" cy="102" rx="4" ry="6" fill="#fcffa4"/><ellipse cx="125" cy="102" rx="4" ry="6" fill="#fcffa4"/>'
    '<path d="M84 146 Q100 158 116 146" stroke="#1b0c41" stroke-width="5" fill="none" stroke-linecap="round"/>'
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
    "right_right": {
        "p1": "We can use this dataset to answer everything.",
        "p2": "For the better, right?",
        "p3": "",
        "p4": "Right?",
    },
    "always_has_been": {"planet": "Pie charts", "question": "Wait, it's all pie charts?", "answer": "Always has been."},
    "change_my_mind": {"sign": "Sorted bar charts beat pies", "caption": "Change my mind."},
    "shocked_strip": {"p1": "We skipped the axis labels.", "p2": "Nobody knows what the chart says.", "p3": "?!"},
    "is_this_a": {"person": "Me, building the dashboard", "thing": "A pie chart", "question": "Is this a bar chart?"},
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
_SHOWCASE_MEME_CYCLE = itertools.cycle(showcase.MEME_FORMATS)
_DEMO_LOOK_CYCLE = itertools.cycle(("kawaii", "viridis_lab", "retro_comic", "corporate_slate", "soft_3d", "magma_noir"))


def meme_ideas_payload(prompt: str, is_showcase: bool = False) -> dict[str, Any]:
    """Five concepts; demo mode cycles the chosen format so each post shows a different one."""
    only = re.search(r"Only use the format `([a-z0-9_]+)`", prompt)
    texts_by_format = {**DEMO_MEME_TEXTS, **showcase.MEME_TEXTS} if is_showcase else DEMO_MEME_TEXTS
    first = only.group(1) if only else next(_SHOWCASE_MEME_CYCLE if is_showcase else _DEMO_MEME_CYCLE)
    pool = (
        ("nope_yep", "terminal", "comic_strip_3", "venn")
        if is_showcase
        else ("nope_yep", "joke_pie_3d", "terminal", "comic_strip_3", "venn")
    )
    others = [f for f in pool if f != first]
    formats = [first] * 5 if only else [first, *others[:4]]
    concepts = [
        {
            "format": fmt,
            "premise": f"{'Friday deploys' if is_showcase else 'Pie charts'}, roasted as {fmt.replace('_', ' ')} #{i + 1}.",
            "callback": "The post's running joke about shipping on a Friday."
            if is_showcase
            else "The post's claim that people compare lengths better than angles.",
            "texts": [{"slot": slot, "text": text, "speaker": ""} for slot, text in texts_by_format.get(fmt, {}).items()],
            "data": DEMO_MEME_DATA.get(fmt, []),
            "caption": "Friday logic" if is_showcase else "Pie logic",
            "look": next(_DEMO_LOOK_CYCLE),
            "scores": {"relevance": 5, "recognizability": 4, "surprise": 4, "clarity": 5, "voice_fit": 4, "standalone": 4 - i % 2},
        }
        for i, fmt in enumerate(formats)
    ]
    return {
        "angles": ["Pie charts and angles", "The 14-slice board deck"],
        "concepts": concepts,
        "chosen": 0,
        "why": "It pays off the post's main argument in one glance.",
    }


def meme_verdict_payload(prompt: str) -> dict[str, Any]:
    """The panel likes the first pitch best and leaves its words as they are."""
    count = len(re.findall(r"^\d+\. \[", prompt, flags=re.MULTILINE)) or 5
    scores = [
        {
            "concept": i,
            "feed_reader": 8 - i % 3,
            "comedy_editor": 7,
            "author": 8,
            "gets_it": 8,
            "note": "Lands on the post's own claim; the risk is that it is familiar.",
        }
        for i in range(count)
    ]
    return {"scores": scores, "chosen": 0, "punch_up": [], "summary": "It pays off the post's argument in one glance."}


def meme_build_payload(format_id: str, is_showcase: bool = False) -> dict[str, Any]:
    from inferno_ghostwriter.images.memes.formats import BY_ID

    fmt = BY_ID.get(format_id) or BY_ID["classic_caption"]
    speakers = itertools.cycle(("left", "right"))
    words = ({**DEMO_MEME_TEXTS, **showcase.MEME_TEXTS} if is_showcase else DEMO_MEME_TEXTS).get(fmt.id, {})
    texts = [{"slot": s.name, "text": words.get(s.name, ""), "speaker": next(speakers) if s.bubble else ""} for s in fmt.slots]
    art = []
    for region in fmt.regions:
        _, _, w, h = region.box
        size = min(w, h) * 0.8
        backdrop = (
            f'<rect width="{w}" height="{h}" fill="#f7d13d"/>'
            f'<circle cx="{w / 2}" cy="{h / 2}" r="{size / 2}" fill="#fb9b06" opacity="0.4"/>'
        )
        ghost = (
            f'<use href="#ghost" x="{(w - size * 0.77) / 2:.0f}" y="{h - size - 10:.0f}" width="{size * 0.77:.0f}" height="{size:.0f}"/>'
        )
        art.append({"region": region.name, "svg": (backdrop if region.opaque else "") + ghost})
    return {
        "texts": texts,
        "cast_defs": DEMO_GHOST if fmt.regions else "",
        "art": art,
        "data": DEMO_MEME_DATA.get(fmt.id, []),
        "alt": f"A {fmt.name} meme about {'shipping models on a Friday' if is_showcase else 'pie charts'}. Text: "
        + " / ".join(t["text"] for t in texts if t["text"]),
        "caption": "Friday logic" if is_showcase else "Pie logic",
    }


# -- Opening images ------------------------------------------------------------------
# One canned build per template: tests render every one, demo mode draws the chosen one, and
# scripts/opening_gallery.py lays them out for a visual review. Every number is in DEMO_OPENING_RESEARCH,
# so the fact check passes the way it would with real research.

DEMO_SOURCE_URL = "https://example.com/chart-reading-study"
DEMO_OPENING_RESEARCH = (
    "A 2024 chart-reading study ([Example chart study](https://example.com/chart-reading-study)) asked 1,200 analysts to "
    "compare values. Accuracy was 62% with pie charts and 91% with sorted bar charts; donuts scored 58%, stacked bars 74% "
    "and tables 88%. Median time to answer fell from 14 seconds to 6 seconds. Pie chart use in dashboards fell from 38% in "
    "2019 to 31% in 2021, 24% in 2023 and 17% in 2025, while sorted bar charts rose from 41% to 63% and tables from 22% to "
    "25%. Readers who saw 3 slices or fewer scored 84%; with 8 or more slices, 41%. On a 10-point reader rating, pie charts "
    "scored 4 for clarity, 3 for precision, 9 for familiarity and 6 for looks; sorted bars scored 9, 8, 8 and 6."
)
_SOURCE = [{"title": "Example chart study, 2024", "url": DEMO_SOURCE_URL}]


def _items(*rows: tuple[str, str]) -> list[dict[str, str]]:
    return [{"label": label, "detail": detail} for label, detail in rows]


def _rows(*rows: tuple[str, float, str]) -> list[dict[str, Any]]:
    return [{"label": label, "value": value, "series": series} for label, value, series in rows]


DEMO_OPENING_BUILDS: dict[str, dict[str, Any]] = {
    "cheat_grid": {
        "headline": "Pick the right chart in 10 seconds",
        "subhead": "Six rules that retire the pie chart for good",
        "items": _items(
            ("Compare values", "Sorted bars, largest first"),
            ("Show a trend", "One line per series, labelled at the end"),
            ("Parts of a whole", "Stacked bar, three parts at most"),
            ("Before and after", "Dumbbell: two dots and a bar"),
            ("Many categories", "Small multiples, shared axis"),
            ("Exact numbers", "A table. Honestly."),
        ),
    },
    "versus": {
        "headline": "Stop slicing. Start sorting.",
        "subhead": "The same data, two ways to show it",
        "left_label": "Pie chart",
        "right_label": "Sorted bar chart",
        "items": _items(
            ("Compare angles by eye", "Compare lengths on one baseline"),
            ("Legend lookups for every slice", "Labels sit right on the bars"),
            ("Breaks past five categories", "Handles twenty without trouble"),
        ),
    },
    "big_number": {
        "headline": "Your readers are guessing",
        "subhead": "of analysts compared two pie slices correctly",
        "number": "62%",
        "items": _items(("With sorted bars: 91%", "")),
        "data": _rows(("Pie chart accuracy", 62, ""), ("Sorted bar accuracy", 91, "")),
        "sources": _SOURCE,
    },
    "flow": {
        "headline": "From pie to bar in four moves",
        "subhead": "",
        "items": _items(
            ("List the slices", "Every category and its value"),
            ("Sort them", "Largest first, always"),
            ("Draw bars", "One baseline, no 3D"),
            ("Label directly", "Values on the bars, no legend"),
        ),
    },
    "matrix_2x2": {
        "headline": "Where your chart belongs",
        "subhead": "Accuracy against effort for the usual suspects",
        "left_label": "Effort to read",
        "right_label": "Accuracy",
        "items": _items(
            ("Tables", "Precise but slow to scan"),
            ("Sorted bars", "Fast and accurate"),
            ("3D pies", "Slow and wrong"),
            ("Pie charts", "Fast to make, easy to misread"),
        ),
    },
    "stack": {
        "headline": "Anatomy of a readable chart",
        "subhead": "",
        "items": _items(
            ("Message", "A title that states the finding"),
            ("Encoding", "Length on a shared baseline beats angle"),
            ("Labels", "Direct labels instead of a legend"),
            ("Data", "Sorted, deduplicated, honest"),
        ),
    },
    "cycle": {
        "headline": "The dashboard review loop",
        "subhead": "",
        "items": _items(
            ("Ask", "What decision does it serve?"),
            ("Draw", "Pick the plainest chart"),
            ("Test", "Can a stranger read it?"),
            ("Trim", "Cut what nobody used"),
        ),
    },
    "funnel": {
        "headline": "Where chart readers drop off",
        "subhead": "",
        "items": _items(
            ("Glance", "Every reader looks at the chart"),
            ("Decode", "Fewer work out the encoding"),
            ("Compare", "Fewer still compare values"),
            ("Act", "Only a clear chart gets a decision"),
        ),
    },
    "timeline": {
        "headline": "The slow decline of the pie chart",
        "subhead": "",
        "items": _items(
            ("1801", "Playfair draws the first pie"),
            ("1984", "Spreadsheets make pies one click away"),
            ("2010s", "Dashboards fill with 3D slices"),
            ("Today", "Sorted bars win the argument"),
        ),
    },
    "line_annotated": {
        "headline": "Pie charts are quietly disappearing",
        "subhead": "Share of dashboards with at least one pie chart",
        "unit": "%",
        "annotation": "Down by more than half in six years",
        "data": _rows(("2019", 38, ""), ("2021", 31, ""), ("2023", 24, ""), ("2025", 17, "")),
        "sources": _SOURCE,
    },
    "slope": {
        "headline": "Dashboards are trading pies for bars",
        "subhead": "Share of dashboards using each chart, 2019 and 2025",
        "unit": "%",
        "data": _rows(
            ("Pie charts", 38, "2019"),
            ("Pie charts", 17, "2025"),
            ("Sorted bars", 41, "2019"),
            ("Sorted bars", 63, "2025"),
            ("Tables", 22, "2019"),
            ("Tables", 25, "2025"),
        ),
        "sources": _SOURCE,
    },
    "dumbbell": {
        "headline": "Same data, very different accuracy",
        "subhead": "Share of readers who compared values correctly",
        "unit": "%",
        "data": _rows(
            ("All readers", 62, "Pie chart"),
            ("All readers", 91, "Sorted bars"),
            ("8+ slices", 41, "Pie chart"),
            ("8+ slices", 88, "Sorted bars"),
        ),
        "sources": _SOURCE,
    },
    "waterfall": {
        "headline": "Where the pie chart lost its readers",
        "subhead": "Accuracy, from sorted bars down to the pie",
        "unit": "%",
        "data": _rows(
            ("Sorted bars", 91, "total"),
            ("Tables", -3, ""),
            ("Stacked bars", -14, ""),
            ("Pie charts", -12, ""),
            ("Pie result", 62, "total"),
        ),
        "sources": _SOURCE,
    },
    "tornado": {
        "headline": "Slice count makes or breaks a pie",
        "subhead": "Accuracy with few slices and with many",
        "unit": "%",
        "data": _rows(
            ("Pie charts", 84, "3 slices or fewer"),
            ("Pie charts", 41, "8 slices or more"),
            ("Donuts", 58, "3 slices or fewer"),
            ("Donuts", 41, "8 slices or more"),
        ),
        "sources": _SOURCE,
    },
    "ranked_bar": {
        "headline": "Pie charts finish second to last",
        "subhead": "Share of readers who compared values correctly",
        "unit": "%",
        "data": _rows(("Sorted bars", 91, ""), ("Tables", 88, ""), ("Stacked bars", 74, ""), ("Pie charts", 62, ""), ("Donuts", 58, "")),
        "sources": _SOURCE,
    },
    "heatmap": {
        "headline": "Accuracy falls as slices pile up",
        "subhead": "Share of correct comparisons",
        "unit": "%",
        "data": _rows(
            ("3 or fewer", 84, "Pie charts"),
            ("8 or more", 41, "Pie charts"),
            ("3 or fewer", 91, "Sorted bars"),
            ("8 or more", 88, "Sorted bars"),
        ),
        "sources": _SOURCE,
    },
    "spider": {
        "headline": "Familiar is not the same as clear",
        "subhead": "Reader ratings out of 10",
        "data": _rows(
            *((axis, value, "Pie charts") for axis, value in (("Clarity", 4), ("Precision", 3), ("Familiarity", 9), ("Looks", 6))),
            *((axis, value, "Sorted bars") for axis, value in (("Clarity", 9), ("Precision", 8), ("Familiarity", 8), ("Looks", 6))),
        ),
        "sources": _SOURCE,
    },
}


_DEMO_OPENING_CONCEPTS: dict[str, dict[str, str]] = {
    "editorial": {
        "hook": "Everyone has squinted at a pie chart; here is why.",
        "concept": "A baker's scale weighing pie slices against neat bar-shaped loaves; the scale tips toward the bars.",
    },
    "data_art": {
        "hook": "Messy slices sorting themselves into clean bars is oddly satisfying.",
        "concept": "Streams of coloured particles pour out of a pie and settle into sorted, glowing bars.",
    },
    "meme": {"hook": "Every analyst has been asked for this chart.", "concept": "A stakeholder asking for a 14-slice pie chart."},
    "cheat_sheet": {"hook": "Save this before your next dashboard review.", "concept": "Six rules for picking the right chart."},
    "data_chart": {"hook": "The numbers settle the argument.", "concept": "Pie chart use in dashboards falling year after year."},
    "big_number": {"hook": "One number every chart maker should know.", "concept": "How often readers compare pie slices correctly."},
    "versus": {"hook": "The same data, two very different reads.", "concept": "Pie chart against sorted bar chart, point by point."},
    "framework": {"hook": "The four moves from pie to bar.", "concept": "A four-step flow from a pie chart to a sorted bar chart."},
    "receipt": {"hook": "The one line of code that fixes it.", "concept": "A code editor changing kind='pie' to kind='barh' after a sort."},
}


def opening_ideas_payload(
    prompt: str,
    words_by_style: dict[str, dict[str, str]] = _DEMO_OPENING_CONCEPTS,
    content: str = "Sorted bars; direct labels; no 3D",
    data_claim: str = "Pie chart accuracy against sorted bars, from a chart-reading study",
) -> dict[str, Any]:
    """Concepts in the styles the prompt allows: the post's best-fit style first, then the open styles."""
    from inferno_ghostwriter.images.opening.styles import BY_ID

    count = int(m.group(1)) if (m := re.search(r"Pitch exactly (\d+)", prompt)) else 6
    section = prompt.split("<styles>", 1)[-1].split("</styles>", 1)[0]
    allowed = re.findall(r"^- `([a-z_]+)`", section, flags=re.MULTILINE)
    fits = re.findall(r"`([a-z_]+)`", m.group(1)) if (m := re.search(r"best fits for this post first: (.+)", prompt)) else []
    if len(allowed) == 1:
        styles = allowed * count
    else:
        lead = [s for s in fits if s in allowed and s not in ("editorial", "data_art")][:1]
        styles = [*lead, "editorial", "editorial", "data_art"]
        styles += [s for s in allowed if s not in styles]
        styles = (styles * count)[:count]
    concepts = []
    for i, style in enumerate(styles):
        words = words_by_style.get(style, words_by_style["editorial"])
        templates = BY_ID[style].templates if style in BY_ID else []
        concepts.append(
            {
                "style": style,
                "template": templates[i % len(templates)] if templates else "",
                "hook": words["hook"],
                "concept": f"{words['concept']} (idea {i + 1})",
                "content": content,
                "data_claim": data_claim if BY_ID.get(style) and BY_ID[style].needs_data else "",
            }
        )
    return {"concepts": concepts}


def opening_verdict_payload(prompt: str) -> dict[str, Any]:
    """The panel likes the first concept best, then each later one a little less."""
    count = len(re.findall(r"^Concept \d+:", prompt, flags=re.MULTILINE))
    scores = [
        {
            "concept": i,
            "scroller": max(3, 9 - i),
            "art_director": max(3, 9 - i),
            "fact_checker": 8,
            "author": max(5, 9 - i),
            "note": "Clear at a glance; it needs crisp labels." if i == 0 else "Solid, but less of a hook.",
        }
        for i in range(count)
    ]
    return {"scores": scores, "summary": "The first idea says the post's point fastest."}


def opening_build_payload(
    template_id: str, builds: dict[str, dict[str, Any]] = DEMO_OPENING_BUILDS, caption: str = "Pie charts, measured."
) -> dict[str, Any]:
    build = builds.get(template_id) or builds.get("cheat_grid") or DEMO_OPENING_BUILDS["cheat_grid"]
    return {
        "subhead": "",
        "items": [],
        "data": [],
        "number": "",
        "unit": "",
        "left_label": "",
        "right_label": "",
        "annotation": "",
        "sources": [],
        "alt": f"Opening image: {build['headline']}.",
        "caption": caption,
        **build,
    }
