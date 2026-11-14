"""The opening-image catalog: every way a post can open, and which ones suit which posts.

This is the only place an opening style is defined. The frontend reads it from ``GET /api/opening-styles``.
To add a style, add an entry here and teach ``room.py`` how to build it (see ``docs/opening-images.md``).
Stored ids that no longer exist resolve to ``auto``, so removing a style never breaks an old post.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

AUTO = "auto"

# How a style is made: Claude draws SVG, the meme room makes it, or code lays out a template from Claude's words and data.
Builder = Literal["svg", "meme", "template"]


class OpeningStyle(BaseModel):
    id: str
    label: str
    # Shown in the picker.
    summary: str
    # What the pitching room and the panel are told about it.
    when_to_use: str
    builder: Builder
    # Article types (``writer.formulas`` ids) and opener ids this style suits best; empty = suits everything.
    suits: list[str] = []
    # Templates the style can use (code-drawn styles only), best first.
    templates: list[str] = []
    # Lowest humor dial at which the style is offered.
    min_humor: int = 0
    # Needs real, sourced numbers: researched before it is built, and dropped when nothing can be verified.
    needs_data: bool = False
    # How a platform thumbnail is cut from it: "cover" crops the centre, "contain" pads to keep the whole image.
    thumbnail_fit: Literal["cover", "contain"] = "cover"
    # Always in the running on Auto, whatever the article type.
    always: bool = False


STYLES: list[OpeningStyle] = [
    OpeningStyle(
        id="editorial",
        label="Visual metaphor",
        summary="An imaginative illustration of the post's core idea as a physical scene.",
        when_to_use=(
            "The post's central mechanism, acted out by a physical system that behaves the same way: marketing spend as coins "
            "dropping through a plinko board into channel buckets; a single source of truth as several specialists each lighting "
            "one part of an elephant. Specific to this post, labelled with its own terms only when a label is essential, never a "
            "generic tech scene."
        ),
        builder="svg",
        always=True,
    ),
    OpeningStyle(
        id="data_art",
        label="Data art",
        summary="Beautiful abstract data: networks, streams sorting by colour, flowing particles, chart motifs.",
        when_to_use=(
            "Analytics, data science, ML and finance topics that want the premium 'data in motion' look: a network graph, "
            "streams of coloured particles sorting into lanes, candlestick or line motifs, scatter clouds. It must encode the "
            "post's idea (streams sorting into the post's own categories, a network with the one node the post is about), and it "
            "never shows numbers, axis values or claims, so it states nothing that could be wrong."
        ),
        builder="svg",
        always=True,
    ),
    OpeningStyle(
        id="meme",
        label="Opening meme",
        summary="Open with a joke that sets up the post's tension; pairs with the closing meme as a meme sandwich.",
        when_to_use=(
            "Posts with a relatable pain, a hot take or a joke opener, for readers who share memes. It sets up the problem the "
            "post solves; the closing meme pays it off."
        ),
        builder="meme",
        suits=[
            "opinion",
            "lessons_learned",
            "listicle",
            "deep_narrative",
            "joke_confession",
            "joke_absurd_analogy",
            "joke_misdirection",
            "joke_exaggeration",
            "joke_mock_serious",
        ],
        min_humor=3,
        thumbnail_fit="contain",
    ),
    OpeningStyle(
        id="cheat_sheet",
        label="Cheat sheet",
        summary="The post's steps, rules or commands as a crisp one-glance reference card people save.",
        when_to_use="How-tos, tutorials and lists: when the post boils down to 4-9 items a reader would pin to their wall.",
        builder="template",
        suits=["how_to", "tutorial", "listicle"],
        templates=["cheat_grid"],
    ),
    OpeningStyle(
        id="data_chart",
        label="Data story chart",
        summary="One factual chart that makes a big point: line, slope, dumbbell, waterfall, tornado, ranked bars, heatmap or spider.",
        when_to_use=(
            "When a real, sourced number tells the post's story at a glance: a trend that bends, a before/after gap, where the "
            "money goes, which factor matters most. Every value must come from research or the post itself, with sources printed."
        ),
        builder="template",
        suits=["case_study", "comparison", "explainer", "news_peg", "surprising_number", "result_first"],
        templates=["line_annotated", "slope", "dumbbell", "waterfall", "tornado", "ranked_bar", "heatmap", "spider"],
        needs_data=True,
    ),
    OpeningStyle(
        id="big_number",
        label="Big number",
        summary="One huge verified number, what it means and its source.",
        when_to_use="When a single surprising, sourced figure is the hook: a cost, a share, a speed-up, a failure rate.",
        builder="template",
        suits=["case_study", "opinion", "lessons_learned", "surprising_number", "news_peg", "result_first"],
        templates=["big_number"],
        needs_data=True,
    ),
    OpeningStyle(
        id="versus",
        label="Versus split",
        summary="Two columns: before and after, myth and reality, the old way and the new.",
        when_to_use="Comparisons, tool reviews, myth-busting and contrarian posts: the contrast is the hook.",
        builder="template",
        suits=["comparison", "tool_review", "myth_buster", "contrarian", "opinion"],
        templates=["versus"],
    ),
    OpeningStyle(
        id="framework",
        label="Framework diagram",
        summary="The whole idea in one picture: a flow, 2x2 matrix, layered stack, cycle, funnel or timeline.",
        when_to_use="Explainers, how-tos and tutorials whose idea is a process, a model or a set of layers.",
        builder="template",
        suits=["explainer", "how_to", "tutorial", "case_study"],
        templates=["flow", "matrix_2x2", "stack", "cycle", "funnel", "timeline"],
    ),
    OpeningStyle(
        id="receipt",
        label="The receipt",
        summary="A crisp, oversized mock of the key code, terminal output or prompt the post is about.",
        when_to_use="Hands-on posts, tutorials and tool reviews where the proof is on screen: the command, the diff, the output.",
        builder="svg",
        suits=["hands_on", "tutorial", "tool_review"],
    ),
]

BY_ID = {s.id: s for s in STYLES}
FALLBACK = "editorial"


def get_style(style_id: str | None) -> OpeningStyle | None:
    return BY_ID.get(style_id or "")


def clean_style(style_id: str | None) -> str:
    """A catalog id, or ``auto`` for anything else (unknown, removed or empty)."""
    return style_id if style_id in BY_ID else AUTO


def suggested(article_type: str, opener: str, humor: int) -> list[str]:
    """The styles worth pitching for this post, best fit first. The open styles are always included."""
    allowed = [s for s in STYLES if humor >= s.min_humor]
    fits = [s.id for s in allowed if not s.always and (article_type in s.suits or opener in s.suits)]
    return [*fits, *(s.id for s in allowed if s.always)]


def eligible(article_type: str, opener: str, humor: int) -> list[str]:
    """Every style the room may pitch on Auto: the suggested ones first, then any other the humor level allows."""
    first = suggested(article_type, opener, humor)
    return [*first, *(s.id for s in STYLES if s.id not in first and humor >= s.min_humor)]


def suggested_by_type(article_types: list[str], humor: int = 5) -> dict[str, list[str]]:
    """What the picker shows as "suits this post" for each article type (opener and humor aside)."""
    return {t: suggested(t, AUTO, humor) for t in [AUTO, *article_types]}


def label(style_id: str) -> str:
    style = get_style(style_id)
    return style.label if style else "Auto (the panel picks)"
