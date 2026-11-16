"""The showcase demo post: what a first-time visitor sees in demo mode and in the example persona.

Topic: shipping machine learning responsibly ("with great models comes great responsibility"), told
with a straight face and a pager. Everything here is canned content for ``FakeLLM(showcase=True)``;
the test suite keeps using ``FakeLLM()`` and its own small fixtures. No real people, companies or products.
"""

from __future__ import annotations

import json
from typing import Any

EXAMPLE_PROMPT = "Why shipping a model is a promise, and the habits that keep it: evals, drift checks and a rollback plan"
TITLE = "With Great Models Comes Great Responsibility (and a Pager)"
SUBTITLE = "A field guide to shipping machine learning without becoming the incident."

DRAFT = f"""# {TITLE}

*{SUBTITLE}*

{{{{image:hero}}}}

Somebody once said that with great power comes great responsibility. They were not talking about a gradient-boosted model that approves loans, but they could have been. Mine hit 94% accuracy in the notebook. I shipped it on a Friday. You can see where this is going.

## The Launch Is the Easy Part

A model in a notebook is a hypothesis. A model in production is a promise, and the world keeps changing the terms. Customers behave differently in December. A partner renames a column. Someone upstream "fixes" a null into a zero, with the best of intentions and no warning.

Here is the loop I run now, before anything ships:

{{{{image:img2}}}}

Three questions. Did it pass an eval that looks like real life, not like the training set? Is something watching it? Who gets paged, and what do they do at 3 a.m.? If the third answer is "me, and I'll figure it out," you are not done.

## Make the Model Prove It Is Still Right

The cheapest guardrail I know is a drift check that compares this week's inputs with the training data and complains when they stop matching. It is about five lines:

```python
from scipy.stats import ks_2samp


def drifted(train, live, alpha=0.01):
    \"\"\"True when live data no longer looks like what we trained on.\"\"\"
    return ks_2samp(train, live).pvalue < alpha
```

Run it on your top features every day, and write the alert for a tired person: which feature moved, how far, and the one-line command that rolls back.

Here is what happens without it. In this (made-up, but painfully familiar) launch, accuracy slid for six weeks. A customer noticed in week 2. The dashboard noticed in week 6.

{{{{image:img3}}}}

## The Responsible Part

Responsibility is not a lecture, and it is not a compliance deck. It is a handful of boring habits: evaluate on data that looks like tomorrow, monitor the inputs and not just the accuracy, keep a human in the loop for anything irreversible, and write the rollback plan before the launch plan. Great power, meet great monitoring.

I still love shipping models. I just ship them like I expect them to misbehave, because eventually they do, and the only choice left is whether you hear about it from a dashboard or from a customer.

{{{{image:meme}}}}
"""

PASSAGES = {
    "rewrite": "Evaluate on data that looks like tomorrow, not on data that looks like last year.",
    "compact": "Ship it like you expect it to misbehave.",
    "expand": (
        "Ship it like you expect it to misbehave. Models do not fail loudly; they get a little worse every week, "
        "and the first person to notice is usually the one you least wanted to hear from."
    ),
    "add_source": "Ship it like you expect it to misbehave. [Hidden technical debt](https://example.com/guide) makes the same case at length.",
    "add_quote": (
        'Ship it like you expect it to misbehave. As [the saying goes](https://example.com/guide), "All models are wrong, but some are useful."'
    ),
}

TITLES = [
    "With Great Models Comes Great Responsibility (and a Pager)",
    "Your Model Is a Promise, Not a Prototype",
    "I Shipped on a Friday and Other Confessions",
    "The Rollback Plan Comes First",
    "Great Power, Meet Great Monitoring",
    "Nobody Pages the Notebook",
    "Ship It Like It Will Misbehave",
    "94% Accurate and Completely Wrong",
]

BRIEF = (
    "Why shipping a model is a promise\n- the notebook number is a hypothesis\n- evals, monitoring and an owner for the pager\n"
    "- a small drift check in Python\n- write the rollback plan first"
)

PLAN: dict[str, Any] = {
    "title_options": TITLES[:5],
    "chosen_title": TITLE,
    "subtitle": SUBTITLE,
    "hook": "Confess to shipping a 94% model on a Friday.",
    "sections": [
        {
            "heading": "The Launch Is the Easy Part",
            "key_points": ["a model in production is a promise"],
            "approx_words": 250,
            "include_code": False,
        },
        {
            "heading": "Make the Model Prove It Is Still Right",
            "key_points": ["a five-line drift check"],
            "approx_words": 250,
            "include_code": True,
        },
        {
            "heading": "The Responsible Part",
            "key_points": ["boring habits", "rollback plan first"],
            "approx_words": 200,
            "include_code": False,
        },
    ],
    "closing": "Hear about the failure from a dashboard, not a customer.",
    "joke": "A model so confident it approves its own change request.",
    "callbacks": [
        {
            "kind": "key_concept",
            "idea": "A model in production is a promise, not a prototype.",
            "introduce_in": 0,
            "revisit_in": [2],
            "payoff": "The closing habits are how you keep the promise.",
        },
        {
            "kind": "running_joke",
            "idea": "Shipping on a Friday.",
            "introduce_in": -1,
            "revisit_in": [0],
            "payoff": "The meme gives the Friday launch its verdict.",
        },
    ],
    "image_slots": [
        {
            "slot_id": "hero",
            "kind": "hero",
            "section_index": -1,
            "purpose": "Thumbnail",
            "brief": "A friendly ghost watching a model dashboard",
        },
        {
            "slot_id": "x1",
            "kind": "diagram",
            "section_index": 0,
            "purpose": "Show the pre-launch loop",
            "brief": "Eval, guardrails, monitor, rollback",
        },
        {
            "slot_id": "x2",
            "kind": "chart",
            "section_index": 1,
            "purpose": "Show decay and who noticed",
            "brief": "Accuracy by week with two annotations",
        },
        {"slot_id": "meme", "kind": "meme", "section_index": 2, "purpose": "Closing laugh", "brief": "Friday deploy meme"},
    ],
    "tags": ["Machine Learning", "MLOps", "Responsible AI"],
}

LINKEDIN = {
    "hook": "I shipped a 94% accurate model on a Friday. By Monday it was the most expensive guess I had ever made.",
    "body": "A model in a notebook is a hypothesis. A model in production is a promise.\n\nThe habits that keep the promise are boring: evals that look "
    "like tomorrow, a drift check on your top features, a human for anything irreversible, and a rollback plan written before the launch plan.\n\n"
    "What is the one alert you wish you had set up sooner?\n\nFull article in the comments.",
    "hashtags": ["MachineLearning", "MLOps", "ResponsibleAI"],
}

INTERVIEW = [
    "What is the worst thing a model of yours did quietly for weeks?",
    "Who got the page, and what did they wish they had been told?",
]

HERO_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900"><defs>'
    '<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#1b0c41"/><stop offset=".55" stop-color="#781c6d"/>'
    '<stop offset="1" stop-color="#ed6925"/></linearGradient>'
    '<linearGradient id="gh" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fcffa4" stop-opacity=".95"/>'
    '<stop offset="1" stop-color="#fb9b06" stop-opacity=".55"/></linearGradient>'
    '<filter id="soft"><feGaussianBlur stdDeviation="22"/></filter></defs>'
    '<rect width="1600" height="900" fill="url(#bg)"/>'
    '<ellipse cx="800" cy="800" rx="640" ry="70" fill="#000004" opacity=".35" filter="url(#soft)"/>'
    '<g transform="translate(900 150)"><rect width="520" height="340" rx="26" fill="#1b0c41" stroke="#fb9b06" stroke-width="5"/>'
    '<polyline points="40,90 120,100 200,120 280,190 360,240 440,270" fill="none" stroke="#fcffa4" stroke-width="10" stroke-linecap="round"/>'
    '<polyline points="40,200 440,200" fill="none" stroke="#cf4446" stroke-width="8" stroke-dasharray="14 12"/>'
    '<circle cx="440" cy="270" r="14" fill="#fb9b06"/></g>'
    '<g transform="translate(300 230)"><path d="M0 520 C-20 250 120 40 300 40 C480 40 600 250 560 520 C520 470 480 560 430 500 '
    'C390 560 330 470 280 530 C230 480 160 570 110 500 C70 560 30 480 0 520 Z" fill="url(#gh)"/>'
    '<ellipse cx="220" cy="250" rx="30" ry="46" fill="#1b0c41"/><ellipse cx="370" cy="250" rx="30" ry="46" fill="#1b0c41"/>'
    '<path d="M240 350 Q295 390 350 350" stroke="#1b0c41" stroke-width="10" fill="none" stroke-linecap="round"/></g>'
    '<g transform="translate(420 700)"><rect width="520" height="26" rx="13" fill="#000004" opacity=".7"/>'
    '<path d="M60 0 L100 -70 L420 -70 L470 0 Z" fill="#1b0c41" stroke="#fb9b06" stroke-width="4"/></g></svg>'
)

DIAGRAM_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 675"><rect width="1200" height="675" fill="#fffaf0"/>'
    "<style>text{font-family:Inter,Arial,sans-serif;text-anchor:middle}.t{font-size:30px;font-weight:700;fill:#fcffa4}"
    ".s{font-size:20px;fill:#fcffa4}.h{font-size:34px;font-weight:700;fill:#1b0c41}</style>"
    '<text class="h" x="600" y="70">The pre-launch loop</text>'
    '<g><rect x="60" y="220" width="240" height="170" rx="24" fill="#4a0c6b"/><text class="t" x="180" y="290">1. Eval</text>'
    '<text class="s" x="180" y="330">Looks like real life</text></g>'
    '<g><rect x="340" y="220" width="240" height="170" rx="24" fill="#781c6d"/><text class="t" x="460" y="290">2. Guardrails</text>'
    '<text class="s" x="460" y="330">Limits and a human</text></g>'
    '<g><rect x="620" y="220" width="240" height="170" rx="24" fill="#cf4446"/><text class="t" x="740" y="290">3. Monitor</text>'
    '<text class="s" x="740" y="330">Inputs, not just accuracy</text></g>'
    '<g><rect x="900" y="220" width="240" height="170" rx="24" fill="#ed6925"/><text class="t" x="1020" y="290">4. Rollback</text>'
    '<text class="s" x="1020" y="330">One command, written first</text></g>'
    '<g stroke="#1b0c41" stroke-width="6" fill="none" stroke-linecap="round"><path d="M304 305 H336"/><path d="M584 305 H616"/>'
    '<path d="M864 305 H896"/><path d="M1020 400 V520 H180 V400"/></g>'
    '<text class="h" x="600" y="580" style="font-size:24px">Fail any step and it does not ship</text></svg>'
)

CHART_SPEC = json.dumps(
    {
        "title": "Model accuracy after launch (illustrative)",
        "data": {
            "values": [{"week": w, "accuracy": a} for w, a in enumerate((94, 93, 91, 86, 79, 71, 66, 63), start=1)],
        },
        "layer": [
            {
                "mark": {"type": "line", "point": True, "color": "#781c6d"},
                "encoding": {
                    "x": {"field": "week", "type": "ordinal", "title": "Weeks since launch", "axis": {"labelAngle": 0}},
                    "y": {"field": "accuracy", "type": "quantitative", "scale": {"zero": False}, "title": "Accuracy (%)"},
                },
            },
            {
                "data": {"values": [{"week": 2, "label": "A customer notices"}, {"week": 6, "label": "The alert fires"}]},
                "mark": {"type": "rule", "strokeDash": [6, 4], "color": "#cf4446", "size": 2},
                "encoding": {"x": {"field": "week", "type": "ordinal"}},
            },
            {
                "data": {"values": [{"week": 2, "label": "A customer notices"}, {"week": 6, "label": "The alert fires"}]},
                "mark": {"type": "text", "align": "left", "dx": 6, "dy": 4, "color": "#cf4446", "fontWeight": "bold"},
                "encoding": {"x": {"field": "week", "type": "ordinal"}, "y": {"value": 14}, "text": {"field": "label"}},
            },
        ],
    }
)

REFERENCE_WORDS = {
    "quote": ("All models are wrong, but some are useful.", "George Box"),
    "social_post": ("Monitor the inputs, not just the accuracy.", "Demo MLE (@demo.mle)"),
}

# -- Opening image -----------------------------------------------------------------------

SOURCE_URL = "https://example.com/model-monitoring-survey"
OPENING_RESEARCH = (
    "A 2025 model-operations survey ([Example monitoring survey](https://example.com/model-monitoring-survey)) asked 900 teams "
    "how they find out a model has degraded. 38% learn from a customer or user, 29% from a dashboard alert, 21% from a "
    "scheduled review and 12% from the on-call engineer. Median time to detect a drop was 41 days without drift monitoring "
    "and 6 days with it. Teams with a written rollback plan restored service in 2 hours; teams without one took 19 hours. "
    "Share of teams monitoring input drift rose from 22% in 2021 to 35% in 2023 and 51% in 2025."
)
_SOURCE = [{"title": "Example monitoring survey, 2025", "url": SOURCE_URL}]


def _items(*rows: tuple[str, str]) -> list[dict[str, str]]:
    return [{"label": label, "detail": detail} for label, detail in rows]


def _rows(*rows: tuple[str, float, str]) -> list[dict[str, Any]]:
    return [{"label": label, "value": value, "series": series} for label, value, series in rows]


OPENING_CONCEPTS: dict[str, dict[str, str]] = {
    "editorial": {
        "hook": "Every launch is a promise; the ghost is the one who has to keep it.",
        "concept": "A friendly ghost sits at a laptop watching a glowing dashboard, one eye on a dipping line.",
    },
    "data_art": {
        "hook": "Slow drift is oddly beautiful until it is your model.",
        "concept": "Glowing particles stream in a clean band, then slowly peel away from the training distribution.",
    },
    "meme": {"hook": "Every team has shipped on a Friday.", "concept": "A Friday deploy with a calm caption and a pager."},
    "cheat_sheet": {"hook": "Save this before your next launch review.", "concept": "Six checks before a model ships."},
    "data_chart": {"hook": "The numbers say who finds out first.", "concept": "How teams discover a model has degraded."},
    "big_number": {"hook": "One number every launch review should include.", "concept": "How many days a silent drop goes unnoticed."},
    "versus": {"hook": "Two ways to ship the same model.", "concept": "With a rollback plan against without one."},
    "framework": {"hook": "The four steps before anything ships.", "concept": "Eval, guardrails, monitoring and rollback."},
    "receipt": {"hook": "The five lines that catch drift.", "concept": "A code editor showing the drift check."},
}

OPENING_BUILDS: dict[str, dict[str, Any]] = {
    "cheat_grid": {
        "headline": "Six checks before a model ships",
        "subhead": "The launch review, on one card",
        "items": _items(
            ("Eval", "Test on data that looks like tomorrow"),
            ("Owner", "A named person gets the page"),
            ("Drift", "Daily check on the top features"),
            ("Guardrails", "Limits and a human for irreversible calls"),
            ("Rollback", "One command, written first"),
            ("Alert text", "Readable by someone tired"),
        ),
    },
    "versus": {
        "headline": "Same model, two launches",
        "subhead": "What the rollback plan changes",
        "left_label": "No plan",
        "right_label": "Written first",
        "items": _items(
            ("Find out from a customer", "Find out from a dashboard"),
            ("19 hours to restore", "2 hours to restore"),
            ("Everyone improvises", "Everyone follows a page"),
        ),
    },
    "big_number": {
        "headline": "Silent drift is slow",
        "subhead": "median days to notice a drop without drift monitoring",
        "number": "41",
        "items": _items(("With drift monitoring: 6", "")),
        "data": _rows(("Without drift monitoring", 41, ""), ("With drift monitoring", 6, "")),
        "sources": _SOURCE,
    },
    "flow": {
        "headline": "From notebook to promise in four steps",
        "subhead": "",
        "items": _items(
            ("Eval", "Real-life data, not the training set"),
            ("Guardrails", "Limits and a human in the loop"),
            ("Monitor", "Inputs as well as accuracy"),
            ("Rollback", "Written before launch"),
        ),
    },
    "line_annotated": {
        "headline": "More teams now watch for drift",
        "subhead": "Share of teams monitoring input drift",
        "unit": "%",
        "annotation": "More than doubled in four years",
        "data": _rows(("2021", 22, ""), ("2023", 35, ""), ("2025", 51, "")),
        "sources": _SOURCE,
    },
    "ranked_bar": {
        "headline": "Customers find the problem first",
        "subhead": "How teams learn a model has degraded",
        "unit": "%",
        "data": _rows(
            ("Customer or user", 38, ""), ("Dashboard alert", 29, ""), ("Scheduled review", 21, ""), ("On-call engineer", 12, "")
        ),
        "sources": _SOURCE,
    },
    "dumbbell": {
        "headline": "A rollback plan buys your weekend",
        "subhead": "Hours to restore service",
        "unit": "h",
        "data": _rows(("Restore time", 19, "No plan"), ("Restore time", 2, "Written plan")),
        "sources": _SOURCE,
    },
}

# -- Memes ---------------------------------------------------------------------------------

MEME_FORMATS = ("this_is_fine", "two_buttons", "nope_yep", "classic_caption", "terminal", "venn", "comic_strip_3")

MEME_TEXTS: dict[str, dict[str, str]] = {
    "nope_yep": {"nope": "Deploy on a Friday", "yep": "Deploy on a Tuesday, with a rollback plan"},
    "this_is_fine": {"bubble": "This is fine.", "fire": "Accuracy: 63% and falling", "character": "Me, in Friday's standup"},
    "two_buttons": {"left_button": "Write the rollback plan", "right_button": "Ship it, we will see", "character": "ML engineer"},
    "classic_caption": {"top": "When the dashboard finally alerts", "bottom": "six weeks after the customer did"},
    "terminal": {
        "title": "zsh - production",
        "cmd1": "python check_drift.py --feature age",
        "out1": "p = 0.0000001. The data has opinions now.",
        "cmd2": "./rollback.sh --to last-good",
        "out2": "Rolled back in 41 seconds. Friday saved.",
        "cmd3": "git blame deploy.yaml",
        "out3": "fatal: it was me, on a Friday",
    },
    "venn": {"title": "Things that are fine on Friday", "a": "Coffee", "b": "Model deploys", "c": "Weekends", "center": "Coffee"},
    "comic_strip_3": {"p1": "The model passed every test!", "p2": "On last year's data.", "p3": "...Add a drift check."},
}


def meme_caption() -> str:
    return "Friday logic"
