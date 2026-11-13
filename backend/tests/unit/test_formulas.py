from __future__ import annotations

from proseferno.db import Persona
from proseferno.prompts import render
from proseferno.writer import Dials, resolve
from proseferno.writer.formulas import (
    ARTICLE_TYPES,
    AUTO,
    BODIES,
    CLOSERS,
    OPENERS,
    ResolvedFormula,
    clean,
    detect_article_type,
    formula_guide,
    formula_label,
    meme_note,
    resolve_formula,
)
from proseferno.writer.pipeline import prompt_settings


def test_catalog_is_consistent() -> None:
    parts = {"openers": OPENERS, "bodies": BODIES, "closers": CLOSERS}
    for options in parts.values():
        ids = [o.id for o in options]
        assert len(ids) == len(set(ids)) and AUTO not in ids
        assert all(o.label and o.summary and o.guide and o.group for o in options)
    assert len({t.id for t in ARTICLE_TYPES}) == len(ARTICLE_TYPES) == 11
    for kind in ARTICLE_TYPES:
        for field, options in parts.items():
            suggested = getattr(kind, field)
            assert suggested, f"{kind.id} suggests no {field}"
            assert set(suggested) <= {o.id for o in options}, f"{kind.id} suggests an unknown {field}"
    # Every style is reachable from at least one article type's suggestions.
    for field, options in parts.items():
        assert {o.id for o in options} == {i for kind in ARTICLE_TYPES for i in getattr(kind, field)}, field
    # Several distinct joke openers to choose between.
    assert sum(o.group == "Joke" for o in OPENERS) >= 3


def test_no_formula_keeps_the_authors_usual_shape() -> None:
    resolved = resolve(Dials(), Persona(name="Me"), "x", default_revisions=1)
    assert (resolved.article_type, resolved.opener, resolved.body, resolved.closer) == (AUTO, AUTO, AUTO, AUTO)
    assert resolved.formula_label == "" and resolved.formula_guide.startswith("Formula: none chosen")


# Shared with frontend/src/lib/formula.test.ts: both sides must read a brief the same way.
BRIEFS = {
    "Snowflake Cortex vs AWS Bedrock for RAG": "comparison",
    "Top 7 pandas tricks I use every week": "listicle",
    "How to size an A/B test": "how_to",
    "Build a RAG chatbot from scratch\n- step-by-step, with code": "tutorial",
    "What is a causal forest?": "explainer",
    "How we migrated 400 dashboards in a quarter": "case_study",
    "I tried three coding agents for a month so you don't have to": "hands_on",
    "5 lessons I learned leading a data science team": "lessons_learned",
    "Unpopular opinion: the dashboard is dead": "opinion",
    "What's new in polars 1.0: a review": "tool_review",
    "The night we lost the feature store: a deep dive": "deep_narrative",
    "Why pie charts are lame and what to use instead": "auto",
    "Uplift modeling\n- explain it simply\n- how to pick a model": "auto",
}


def test_article_type_is_read_from_the_brief() -> None:
    for brief, expected in BRIEFS.items():
        assert detect_article_type(brief) == expected, brief
    assert all(kind.signals for kind in ARTICLE_TYPES)

    persona = Persona(name="Me")
    detected = resolve(Dials(opener="cold_open"), persona, "How to size an A/B test", default_revisions=1)
    assert (detected.article_type, detected.article_type_detected, detected.opener) == ("how_to", True, "cold_open")
    assert detected.formula_label == "How-to · Cold open" and "Article type: How-to." in detected.formula_guide

    # A chosen type (on the post or the persona) is never second-guessed.
    chosen = resolve(Dials(article_type="opinion"), persona, "How to size an A/B test", default_revisions=1)
    assert (chosen.article_type, chosen.article_type_detected) == ("opinion", False)
    persona.default_formula = {"article_type": "tutorial"}
    assert resolve(Dials(), persona, "How to size an A/B test", default_revisions=1).article_type == "tutorial"
    # "Automatic" on the post means "from the brief" again.
    assert resolve(Dials(article_type="auto"), persona, "How to size an A/B test", default_revisions=1).article_type == "how_to"


def test_formula_guide_names_every_chosen_part() -> None:
    dials = Dials(article_type="tutorial", opener="joke_confession", body="progressive_build", closer_note="End on the deploy command.")
    resolved = resolve(dials, Persona(name="Me"), "x", default_revisions=1)

    assert resolved.formula_label == "Tutorial · Joke: the confession · Start simple, build up · Custom closer"
    guide = resolved.formula_guide
    assert "Article type: Tutorial." in guide and "self-deprecating confession" in guide and "smallest version that works" in guide
    assert "Closer (the author's own instructions): End on the deploy command." in guide
    assert "closing meme image always comes after it" in guide

    # The guide reaches the planner, the writer and the editor.
    settings = prompt_settings(resolved)
    extra = {"prompt": "p", "plan": "{}", "placeholders": "", "draft": "d", "fidelity": "{}", "ai_tells": "", "callbacks": ""}
    for template in ("plan", "draft", "critique"):
        assert "Opener: Joke: the confession." in render(template, **settings, **extra)


def test_note_adds_to_a_chosen_style() -> None:
    guide = formula_guide(ResolvedFormula(opener="cold_open", opener_note="Start at 2 a.m. with the pager."))
    assert "Opener: Cold open." in guide and "The author adds: Start at 2 a.m. with the pager." in guide
    assert "Body: the structure the author would naturally give" in guide


def test_persona_default_formula_and_per_post_override() -> None:
    persona = Persona(name="Me", default_formula={"article_type": "opinion", "opener": "contrarian", "closer_note": "No recap."})

    inherited = resolve(Dials(), persona, "x", default_revisions=1)
    assert (inherited.article_type, inherited.opener, inherited.closer_note) == ("opinion", "contrarian", "No recap.")

    # An explicit "auto" (or an empty note) on the post switches the persona's default off for that post.
    post = resolve(Dials(article_type="how_to", opener="auto", closer_note=""), persona, "x", default_revisions=1)
    assert (post.article_type, post.opener, post.closer_note) == ("how_to", AUTO, "")


def test_unknown_ids_fall_back_to_auto() -> None:
    formula = resolve_formula({"article_type": "sonnet", "opener": "retired_style", "body": "countdown"})
    assert (formula.article_type, formula.opener, formula.body) == (AUTO, AUTO, "countdown")
    assert formula_label(formula) == "Countdown"
    assert clean({"opener": "retired_style", "body": "auto", "closer": "kicker", "body_note": "  ", "junk": 1}) == {
        "body": "auto",
        "closer": "kicker",
    }


def test_the_closing_meme_is_told_the_shape_of_the_post() -> None:
    assert meme_note(ResolvedFormula()) == ""  # no formula: the room is told nothing new

    note = meme_note(ResolvedFormula(article_type="comparison", opener="joke_confession", closer="verdict", closer_note="Pick one."))
    assert "Article type: X vs. Y comparison." in note and "Closer: The verdict." in note and "The author adds: Pick one." in note
    assert "never restate the closer's last line" in note and "The post opens on a joke." in note
    assert "Body:" not in note  # parts left to the voice profile are not listed

    # A full-circle closer already echoes the opening, so the meme is told to land somewhere else.
    circle = meme_note(ResolvedFormula(opener="joke_confession", closer="full_circle"))
    assert "should not echo the opening a second time" in circle and "The post opens on a joke." not in circle

    assert "Opener (the author's own instructions): Start at 3 a.m." in meme_note(ResolvedFormula(opener_note="Start at 3 a.m."))
