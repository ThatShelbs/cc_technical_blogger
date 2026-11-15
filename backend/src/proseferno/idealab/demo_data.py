"""Canned Idea Lab content for tests and demo mode: no network, no model.

Everything here is invented and generic on purpose (example.com links, no real products or people), so the demo
never shows made-up news about a real company.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from proseferno.idealab.collect import Signal

_BASE = "https://example.com/idea-lab"

# (source_id, source name, group, slug, title, engagement)
_SIGNALS: list[tuple[str, str, str, str, str, int]] = [
    ("hn_ai", "Hacker News: AI", "community", "agent-evals-thread", "Ask: how do you evaluate an agent before it ships?", 412),
    ("hn_llm", "Hacker News: LLM", "community", "prompt-caching-costs", "We cut our LLM bill by 60% with prompt caching", 388),
    (
        "se_stats",
        "Cross Validated: hot questions",
        "community",
        "ab-test-power-question",
        "How do I size an A/B test when traffic is tiny?",
        57,
    ),
    (
        "tds",
        "Towards Data Science",
        "creator",
        "boosting-vs-deep-tabular",
        "Gradient boosting still beats deep learning on tabular data",
        140,
    ),
    (
        "medium_data_science",
        "Medium: data science",
        "creator",
        "boosting-benchmark",
        "I benchmarked five tabular models so you don't have to",
        96,
    ),
    (
        "github_agents",
        "GitHub: new AI agent repositories",
        "code",
        "agent-eval-kit",
        "example/agent-eval-kit: test harness for tool-using agents",
        2300,
    ),
    (
        "hf_daily_papers",
        "Hugging Face Daily Papers",
        "research",
        "small-models-paper",
        "Small models match large ones on structured extraction",
        120,
    ),
    ("news_healthcare", "News: AI in Healthcare", "industry", "clinical-notes-pilots", "Hospitals pilot AI summaries of clinical notes", 0),
    ("news_insurance", "News: AI in Insurance", "industry", "claims-triage", "Insurers move claims triage to machine learning", 0),
    ("openai_news", "Vendor blog", "vendor", "agent-sdk-evals", "Agent SDK adds built-in evaluation and tracing", 0),
]

# (kind, label, summary, heat, industries, evidence slugs)
_TRENDS: list[tuple[str, str, str, int, list[str], list[str]]] = [
    (
        "launch",
        "Agent frameworks add built-in evaluation",
        "A widely used agent SDK shipped evaluation and tracing in the box, and an open source test harness for tool-using agents "
        "passed two thousand stars in a week. Teams that skipped evaluation now have no excuse.",
        9,
        ["Technology"],
        ["agent-sdk-evals", "agent-eval-kit", "agent-evals-thread"],
    ),
    (
        "claim",
        "Gradient boosting is all you need for tabular data",
        "A well-known competition winner argued again that boosted trees beat deep learning on tabular problems, and several "
        "writers published benchmarks agreeing. Critics say the benchmarks ignore very large and multimodal tables.",
        8,
        [],
        ["boosting-vs-deep-tabular", "boosting-benchmark"],
    ),
    (
        "creator_wave",
        "Everyone is writing about prompt caching costs",
        "At least four popular posts this fortnight cover cutting LLM bills with prompt caching. Almost none measure what "
        "caching does to latency or explain when it does not pay.",
        7,
        [],
        ["prompt-caching-costs"],
    ),
    (
        "industry_pattern",
        "Hospitals and insurers are all piloting document triage",
        "Health systems are piloting AI summaries of clinical notes while insurers move claims triage to machine learning: "
        "the same project, reading messy documents and routing them, in two regulated industries at once.",
        6,
        ["Healthcare", "Insurance"],
        ["clinical-notes-pilots", "claims-triage"],
    ),
    (
        "question",
        "How to size an A/B test with very little traffic",
        "A recurring question on Q&A sites and forums: what to do when the sample size calculator says the test needs a year. "
        "The top answers disagree with each other.",
        6,
        [],
        ["ab-test-power-question"],
    ),
    (
        "launch",
        "Small models match large ones on structured extraction",
        "A new paper shows small open models matching much larger ones on structured extraction when given good schemas, "
        "which changes the cost case for a common production task.",
        5,
        [],
        ["small-models-paper"],
    ),
]

_SUBJECTS = [
    "agent evaluation",
    "gradient boosting",
    "prompt caching",
    "A/B test power",
    "causal inference",
    "dashboard design",
    "feature stores",
    "vector search",
    "model monitoring",
    "data contracts",
    "experiment platforms",
    "document triage",
    "structured extraction",
    "forecast accuracy",
]

_TEMPLATES: dict[str, list[str]] = {
    "emerging": [
        "What the latest {s} release changes for your team on Monday",
        "The {s} announcement left out the hard part",
        "Is {s} finally ready for production? I checked",
        "{S} just got easier, and that is the problem",
        "Three things nobody mentioned about the {s} news",
    ],
    "builder": [
        "{S}, part two: what I got wrong last time",
        "A deeper cut: the one {s} section readers asked about",
        "{S} a year later: an honest update",
        "The practical follow-up to my {s} rant",
        "Your {s} questions, answered with code",
    ],
    "expander": [
        "A weekend project: build a tiny {s} tool from scratch",
        "How to explain {s} to an executive in five minutes",
        "The {s} tutorial I wish existed when I started",
        "Leading a team through its first {s} rollout",
        "{S} by the numbers: a chart-first walkthrough",
    ],
    "reader_questions": [
        "The complete answer to the {s} question everyone keeps asking",
        "Stop guessing: a worked example for {s}",
        "{S} when the textbook method does not apply",
    ],
    "counter_take": [
        "No, {s} is not all you need",
        "The popular take on {s} is half right",
        "Where the {s} argument breaks down in practice",
    ],
    "sparks": [
        "From a note to a post: my half-formed {s} idea",
        "The {s} thought I could not shake",
        "What I actually meant about {s}",
    ],
}

_TYPES = ["how_to", "auto", "opinion", "auto", "case_study"]
_SHELF = ["this_week", "this_month", "evergreen"]
_THEMES = ["Agents", "Experimentation", "Modeling", "LLM Costs", "Analytics", "Leadership"]


def demo_signals() -> list[Signal]:
    now = datetime.now(UTC)
    return [
        Signal(
            source_id=source_id,
            source_name=name,
            group=group,
            url=f"{_BASE}/{slug}",
            title=title,
            summary="An invented example item for demo mode.",
            published_at=now - timedelta(days=1 + i % 6),
            engagement=engagement,
        )
        for i, (source_id, name, group, slug, title, engagement) in enumerate(_SIGNALS)
    ]


def demo_scout() -> tuple[str, list[tuple[str, str]]]:
    """Scout findings and the pages they cite: every demo trend's links, so the digest passes the link check."""
    titles = {slug: title for _, _, _, slug, title, _ in _SIGNALS}
    text = "\n".join(f"- **{label}** {summary}" for _, label, summary, _, _, _ in _TRENDS)
    return text, [(f"{_BASE}/{slug}", title) for slug, title in titles.items()]


def demo_digest(prompt: str) -> dict[str, Any]:
    query = re.search(r"The writer's own search: (.+)", prompt)
    trends = [
        {
            "kind": kind,
            "label": label,
            "summary": summary,
            "heat": heat,
            "industries": industries,
            "evidence_urls": [f"{_BASE}/{s}" for s in slugs],
        }
        for kind, label, summary, heat, industries, slugs in _TRENDS
    ]
    if query:
        # "Send another search" visibly adds something of its own.
        topic = query.group(1).strip()
        trends = [
            {
                "kind": "launch",
                "label": f"New this week: {topic}"[:80],
                "summary": f"What the extra search found about {topic}: an invented example finding for demo mode.",
                "heat": 7,
                "industries": [],
                "evidence_urls": [f"{_BASE}/agent-sdk-evals"],
            }
        ]
    # One trend with a link nobody found: the link check must drop it.
    trends.append(
        {
            "kind": "claim",
            "label": "An unverifiable rumour",
            "summary": "Not backed by any page.",
            "heat": 9,
            "industries": [],
            "evidence_urls": ["https://example.com/not-a-real-source"],
        }
    )
    return {"trends": trends}


def _labels_in(prompt: str, kinds: tuple[str, ...]) -> list[str]:
    return [m.group(2) for m in re.finditer(r"^- \[(\w+), heat \d+/10\] (.+?): ", prompt, re.MULTILINE) if not kinds or m.group(1) in kinds]


def demo_batch(prompt: str) -> dict[str, Any]:
    approach = m.group(1) if (m := re.search(r"^Approach: (\w+)", prompt, re.MULTILINE)) else "emerging"
    count = int(m.group(1)) if (m := re.search(r"Write exactly (\d+) ideas", prompt)) else 5
    taken = prompt.split("# Titles already proposed", 1)[-1].split("# Article types", 1)[0].lower()
    labels = _labels_in(prompt, ())
    posts = re.findall(r'^- "(.+?)" \(', prompt, re.MULTILINE)
    templates = _TEMPLATES.get(approach, _TEMPLATES["emerging"])
    ideas: list[dict[str, Any]] = []
    for n, subject in enumerate(_SUBJECTS * len(templates)):
        if len(ideas) >= count:
            break
        # Each pass over the subjects moves every subject on to its next template.
        template = templates[(n % len(_SUBJECTS) + n // len(_SUBJECTS)) % len(templates)]
        title = template.format(s=subject, S=subject[0].upper() + subject[1:])
        if title.lower() in taken or any(i["title"] == title for i in ideas):
            continue
        ideas.append(
            {
                "title": title,
                "brief": f"A practical look at {subject} for working data teams: what matters, what to skip, and one thing to try.",
                "angle": f"Told from hands-on experience with {subject}, with the mistakes left in.",
                "outline": [
                    f"The moment {subject} went wrong for me",
                    f"What most posts about {subject} leave out",
                    "A small worked example with numbers",
                    "When this advice does not apply",
                    "What to do on Monday",
                ],
                "why_now": f"{subject[0].upper() + subject[1:]} is being discussed widely this month.",
                "shelf_life": _SHELF[n % len(_SHELF)],
                "article_type": _TYPES[n % len(_TYPES)],
                "trend_labels": [labels[n % len(labels)]] if labels else [],
                "builds_on": posts[n % len(posts)] if posts and approach == "builder" else "",
                "tags": ["sequel"] if approach == "builder" and n % 3 == 0 else [],
            }
        )
    return {"ideas": ideas}


def demo_ranking(prompt: str) -> dict[str, Any]:
    items = []
    for match in re.finditer(r"^\[(\d+)\] ", prompt, re.MULTILINE):
        i = int(match.group(1))
        items.append(
            {
                "index": i,
                "theme": _THEMES[i % len(_THEMES)],
                "timeliness": 3 + (i * 7) % 7,
                "demand": 4 + (i * 5) % 6,
                "fit": 5 + (i * 3) % 5,
                "differentiation": 3 + (i * 11) % 7,
                "effort": 4 + (i * 2) % 6,
                "note": "Timely, and close to what this author already does well."
                if i % 2
                else "A fresh angle, but it needs original work first.",
            }
        )
    return {"themes": _THEMES, "items": items}
