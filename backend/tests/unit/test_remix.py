"""The redraw's twist catalog, data art staying abstract, and image slots that build on earlier ones."""

from __future__ import annotations

import random

from inferno_ghostwriter.images import remix
from inferno_ghostwriter.images.memes import ArtDirection
from inferno_ghostwriter.images.opening.room import OpeningRoom, literal_objects
from inferno_ghostwriter.images.opening.specs import OpeningConcept
from inferno_ghostwriter.writer.pipeline import normalize_slots
from inferno_ghostwriter.writer.schemas import ImageSlot


def test_every_tweak_belongs_to_a_dimension_and_palettes_carry_colors() -> None:
    assert {t.dimension for t in remix.TWEAKS} == set(remix.DIMENSIONS)
    assert len({(t.dimension, t.id) for t in remix.TWEAKS}) == len(remix.TWEAKS)
    assert all(len(t.colors) >= 3 for t in remix.TWEAKS if t.dimension == remix.PALETTE)
    assert {"ghost", "robots", "dogs", "people"} <= {t.id for t in remix.TWEAKS if t.dimension == remix.CAST}


def test_a_twist_picks_dimensions_that_suit_the_image_and_skips_recent_ones() -> None:
    chart = remix.choose_tweaks(remix.dimensions_for("chart"), rng=random.Random(1))
    assert [t.dimension for t in chart] == [remix.PALETTE]
    # Templates drawn by code only take colors; data art takes no characters.
    assert remix.dimensions_for("hero", "cheat_sheet") == (remix.PALETTE,)
    assert remix.CAST not in remix.dimensions_for("hero", "data_art")
    assert remix.CAST in remix.dimensions_for("hero", "editorial")

    recent = [f"palette:{t.id}" for t in remix.TWEAKS if t.dimension == remix.PALETTE][: remix.MEMORY]
    for seed in range(20):
        (picked,) = remix.choose_tweaks((remix.PALETTE,), recent=recent, rng=random.Random(seed))
        assert picked.id in {"blueprint", "sepia"}  # the palettes the last redraws did not try


def test_the_authors_pins_win_and_a_brand_palette_is_not_replaced_at_random() -> None:
    chosen = remix.choose_tweaks(
        remix.dimensions_for("hero", "editorial"),
        pinned=remix.pins_from({"cast": "dogs", "palette": "nope", "staging": "auto"}),
        rng=random.Random(3),
        keep_palette=True,
    )
    assert any(t.id == "dogs" for t in chosen)
    assert not any(t.dimension == remix.PALETTE for t in chosen)
    pinned = remix.choose_tweaks((remix.PALETTE,), pinned={"palette": "viridis"}, keep_palette=True)
    assert [t.id for t in pinned] == ["viridis"]


def test_the_art_direction_carries_the_critique_and_the_twist() -> None:
    plan = remix.ImprovementPlan(weakness="Cluttered.", improvements=["Cut the legend"], keep=["The curve"], fresh_angle="Zoom in")
    tweaks = [remix.get_tweak("palette", "ocean"), remix.get_tweak("cast", "dogs")]
    art = remix.apply_to_art(ArtDirection(visual_style="flat"), plan, [t for t in tweaks if t])
    assert art.palette[0] == "#0b1d3a" and "0b1d3a" in art.brand and "dogs" in art.cast.lower()
    both = remix.variation_for(art)
    assert "Cluttered." in both and "Cut the legend" in both and "Dogs" not in both and "dogs" in both
    # A chart takes the palette in code, and no cast: only the critique is worded for it.
    assert "dogs" not in remix.variation_for(art, (remix.PALETTE,), kind="chart")
    assert remix.variation_for(ArtDirection(visual_style="flat")) == ""
    stored = remix.to_remix(plan, [t for t in tweaks if t], {"recent": ["staging:wide"]})
    assert stored["recent"][0] == "palette:ocean" and "staging:wide" in stored["recent"] and stored["brainstormed"]


def test_data_art_is_abstract_so_literal_objects_send_the_pitch_back() -> None:
    assert literal_objects("Streams of particles sort into lanes; one node glows warm.") == []
    assert literal_objects("Coins flip and land in buckets") == ["coins", "flip", "buckets"]
    concepts = [
        OpeningConcept(style="editorial", template="", hook="h", concept="A plinko board", content="", data_claim=""),
        OpeningConcept(style="editorial", template="", hook="h", concept="Another scene", content="", data_claim=""),
        OpeningConcept(style="data_art", template="", hook="h", concept="Coin flips streaming into piles", content="", data_claim=""),
    ]
    problems = OpeningRoom._mix_problems(concepts, False, 3)
    assert len(problems) == 1 and "Concept 2" in problems[0] and "abstract" in problems[0]
    concepts[2] = concepts[2].model_copy(update={"concept": "Streams of particles splitting into two lanes"})
    assert OpeningRoom._mix_problems(concepts, False, 3) == []


def test_slots_only_build_on_earlier_images_and_keep_the_link_through_renaming() -> None:
    def slot(slot_id: str, kind: str = "chart", builds_on: str = "") -> ImageSlot:
        return ImageSlot(slot_id=slot_id, kind=kind, section_index=0, purpose="p", brief="b", builds_on=builds_on)  # type: ignore[arg-type]

    slots = [
        slot("hero", "hero"),
        slot("a"),
        slot("b", builds_on="a"),
        slot("c", builds_on="b"),
        slot("d", builds_on="e"),
        slot("meme", "meme"),
    ]
    result = normalize_slots(slots, 6, 3)
    links = {s.slot_id: s.builds_on for s in result}
    assert links == {"hero": "", "img2": "", "img3": "img2", "img4": "img3", "img5": "", "meme": ""}
    # A link to a later slot or to one dropped for the image count is not kept.
    trimmed = normalize_slots(slots, 3, 3)
    assert {s.slot_id: s.builds_on for s in trimmed} == {"hero": "", "img2": "", "meme": ""}
    assert ImageSlot.model_validate({"slot_id": "x", "kind": "chart", "section_index": 0, "purpose": "p", "brief": "b"}).builds_on == ""
