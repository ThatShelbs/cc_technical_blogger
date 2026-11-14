"""The A/B challenger (random, seeded tweaks) and blending parts of two posts."""

from __future__ import annotations

import random

from proseferno.abtest.blend import closer_span, opener_span, take_closer, take_opener, take_title
from proseferno.abtest.perturb import PRINCIPLES, build_challenger, bullets, research_principles, voice_habits
from proseferno.db import Persona, Sample, VoiceProfile
from proseferno.voice import select_exemplars
from proseferno.writer import Dials, resolve
from proseferno.writer.dials import STYLE_DIALS
from proseferno.writer.formulas import ARTICLE_TYPES, OPENERS, shuffle_part

PROFILE = """# Voice Profile: Me

## Signature Moves
- **The confession opener**: start by admitting a mistake. Example: "I shipped it on a Friday."
- Asks the reader a direct question before every big claim
- Ends sections on a one-line punch
- Uses a running gag about spreadsheets

## Lexicon
Never use: delve
"""

RESEARCH = """## Titles
- Promise one specific outcome in the title, and keep the promise.
- Use [numbers](https://example.com) when the post is a list.

## Sources
- [A guide](https://example.com/guide)
"""


def sample(i: int, text: str, weight: float = 1.0) -> Sample:
    return Sample(
        id=i,
        persona_id=1,
        kind="own",
        source_name=f"s{i}.md",
        source_type="md",
        title=f"Post {i}",
        markdown=text,
        word_count=50,
        weight=weight,
    )


SAMPLES = [
    sample(1, "pie charts and bar charts for dashboards"),
    sample(2, "bar charts beat pie charts in every dashboard"),
    sample(3, "charts and dashboards nobody opens"),
    sample(4, "causal inference with uplift models"),
    sample(5, "pie charts in the quarterly deck"),
]


def challenger(seed: int, *, humor: int = 5, samples: list[Sample] | None = None, best_practices: str | None = RESEARCH, **dials: object):
    persona = Persona(id=1, name="Me", default_humor=humor)
    profile = VoiceProfile(persona_id=1, version=1, markdown=PROFILE, best_practices=best_practices)
    raw = Dials(target_words=1800, article_type="how_to", **dials)  # type: ignore[arg-type]
    control = resolve(raw, persona, "Pie charts", default_revisions=0)
    built = build_challenger(
        seed=seed,
        control=control,
        dials=raw,
        persona=persona,
        voice_profile=profile,
        samples=SAMPLES if samples is None else samples,
        prompt="Pie charts and dashboards",
    )
    return control, built, resolve(built.dials, persona, "Pie charts", default_revisions=0)


def test_same_seed_same_challenger() -> None:
    _, first, _ = challenger(7)
    _, second, _ = challenger(7)
    assert first == second
    assert challenger(8)[1].tweaks != first.tweaks


def test_every_dial_moves_a_little_and_the_length_never_does() -> None:
    for seed in range(40):
        for humor in (0, 5, 10):
            control, _, after = challenger(seed, humor=humor)
            for key in ("humor", *STYLE_DIALS):
                before, now = getattr(control, key), getattr(after, key)
                assert 1 <= abs(now - before) <= 2 and 0 <= now <= 10, (key, before, now)
            assert after.target_words == control.target_words == 1800
            assert (after.platform, after.topic, after.article_type) == (control.platform, control.topic, control.article_type)
            assert abs(after.image_count - control.image_count) == 1 and after.image_count >= 2
            assert 1 <= abs(after.reference_count - control.reference_count) <= 2


def test_references_stay_off_when_the_author_turned_them_off() -> None:
    _, built, after = challenger(3, reference_count=0)
    assert after.reference_count == 0
    assert not [t for t in built.tweaks if t["label"] == "References"]


def test_formula_parts_suit_the_article_type() -> None:
    how_to = next(t for t in ARTICLE_TYPES if t.id == "how_to")
    for seed in range(30):
        control, built, after = challenger(seed)
        moved = [t for t in built.tweaks if t["group"] == "Formula"]
        assert len(moved) == 2
        for tweak in moved:
            part = tweak["field"]
            assert getattr(after, part) == tweak["value"] != getattr(control, part)
            assert tweak["value"] in {"opener": how_to.openers, "body": how_to.bodies, "closer": how_to.closers}[part]


def test_shuffle_part_follows_the_frontend_rules() -> None:
    jokes = {o.id for o in OPENERS if o.group == "Joke"}
    rng = random.Random(1)
    assert all(shuffle_part("opener", "auto", humor=2, rng=rng) not in jokes for _ in range(50))
    assert shuffle_part("body", "auto", rng=rng) is None  # a body only makes sense for an article type
    assert shuffle_part("closer", "kicker", "listicle", rng=rng) != "kicker"


def test_emphasis_names_habits_principles_title_and_example() -> None:
    _, built, _ = challenger(11)
    groups = {t["group"] for t in built.tweaks}
    assert groups == {"Settings", "Formula", "Examples", "Voice", "Principles", "Title", "Images"}
    assert built.emphasis.startswith("# Emphasis for this post")
    voice = [t for t in built.tweaks if t["group"] == "Voice"]
    assert [t["label"] for t in voice] == ["Lean into", "Lean into", "Ease off"]
    for tweak in [t for t in built.tweaks if t["target"] == "profile"]:
        assert tweak["change"] and (tweak["after"] in built.emphasis or tweak["group"] == "Title")
    # Research bullets come first; the built-in principles fill the rest.
    principles = [t for t in built.tweaks if t["group"] == "Principles"]
    assert len(principles) == 3 and [t["label"] for t in principles][:2] == ["From your research"] * 2
    assert principles[2]["label"] in PRINCIPLES
    assert built.brand_kit["style"].count(",") >= 1 and built.tweaks[-1]["field"] == "visual_style"


def test_principles_fall_back_to_the_built_in_list() -> None:
    _, built, _ = challenger(5, best_practices=None)
    assert {t["label"] for t in built.tweaks if t["group"] == "Principles"} <= set(PRINCIPLES)
    assert len([t for t in built.tweaks if t["group"] == "Principles"]) == 3


def test_examples_swap_one_post_and_lean_on_one() -> None:
    usual = [s.id for s in select_exemplars("Pie charts and dashboards", SAMPLES)]
    for seed in range(20):
        _, built, _ = challenger(seed)
        assert len(built.exemplar_ids) == len(usual) == 3
        assert len(set(built.exemplar_ids) - set(usual)) == 1
        examples = [t for t in built.tweaks if t["group"] == "Examples"]
        assert [t["label"] for t in examples] == ["Example post shown to the writer", "Lean most on"]
        assert examples[1]["sample_id"] in built.exemplar_ids

    # Too few posts to swap: the same examples, one still leaned on. No samples at all: no example tweaks.
    _, few, _ = challenger(1, samples=SAMPLES[:2])
    assert sorted(few.exemplar_ids) == [1, 2] and [t["label"] for t in few.tweaks if t["group"] == "Examples"] == ["Lean most on"]
    _, none, _ = challenger(1, samples=[])
    assert none.exemplar_ids == [] and not [t for t in none.tweaks if t["group"] == "Examples"]


def test_sample_weight_favors_a_post_as_an_example() -> None:
    plain = [s.id for s in select_exemplars("causal uplift pie", SAMPLES, max_posts=1)]
    favored = [sample(s.id or 0, s.markdown, 5.0 if s.id == 5 else 1.0) for s in SAMPLES]
    assert plain != [5]
    assert [s.id for s in select_exemplars("causal uplift pie", favored, max_posts=1)] == [5]


def test_bullets_and_profile_parsing() -> None:
    habits = voice_habits(PROFILE)
    assert habits[0] == "The confession opener: start by admitting a mistake."
    assert len(habits) == 4
    assert research_principles(RESEARCH) == [
        "Promise one specific outcome in the title, and keep the promise.",
        "Use numbers when the post is a list.",
    ]
    assert bullets("1. " + "word " * 80)[0].endswith("...")


BASE = """# Base Title

*Base subtitle.*

{{image:hero}}

Base opener paragraph.

{{image:img2}}

## First

Base first section.

{{image:img3}}

## Last

Base closing words.

## Go deeper

- [A link](https://example.com)

{{image:meme}}
"""

OTHER = """# Other Title

*Other subtitle.*

{{image:hero}}

Other opener, line one.

{{image:img2}}

Other opener, line two.

## One

Other first section.

## Finale

Other closing words.

{{image:img3}}

{{image:meme}}
"""


def test_spans() -> None:
    lines = BASE.splitlines()
    start, end = opener_span(BASE)
    assert lines[start:end][1] == "Base opener paragraph." and lines[end] == "## First"
    closer = closer_span(BASE)
    assert closer is not None and lines[closer[0]] == "## Last" and lines[closer[1]] == "## Go deeper"
    assert closer_span("# T\n\nNo sections.\n") is None


def test_take_title_keeps_the_hero_and_the_body() -> None:
    out = take_title(BASE, OTHER)
    assert out.startswith("# Other Title\n\n*Other subtitle.*\n\n{{image:hero}}\n\nBase opener paragraph.")
    assert out.count("{{image:hero}}") == 1 and "Base closing words." in out


def test_take_opener_brings_its_image_under_a_free_slot() -> None:
    result = take_opener(BASE, OTHER)
    assert result.dropped == ["img2"] and result.moved == {"img2": "img4"}
    assert "Other opener, line one.\n\n{{image:img4}}\n\nOther opener, line two.\n\n## First" in result.markdown
    assert "Base opener paragraph." not in result.markdown and result.markdown.startswith("# Base Title")
    assert result.markdown.count("{{image:hero}}") == 1 and "\n\n\n" not in result.markdown


def test_take_closer_stops_before_go_deeper_and_the_meme() -> None:
    result = take_closer(BASE, OTHER)
    assert result.dropped == [] and result.moved == {"img3": "img4"}
    assert "## Finale\n\nOther closing words.\n\n{{image:img4}}\n\n## Go deeper" in result.markdown
    assert "## Last" not in result.markdown and result.markdown.rstrip().endswith("{{image:meme}}")
    assert result.markdown.count("{{image:img3}}") == 1  # the base's own img3 is untouched

    # Both parts: slots from the two splices never collide.
    both = take_closer(take_opener(BASE, OTHER).markdown, OTHER)
    assert both.moved == {"img3": "img5"}
    assert take_closer("# T\n\nNo sections.\n", OTHER).markdown == "# T\n\nNo sections.\n"
