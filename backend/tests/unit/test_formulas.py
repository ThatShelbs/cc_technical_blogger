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
    formula_guide,
    formula_label,
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
