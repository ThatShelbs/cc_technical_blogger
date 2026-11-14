from __future__ import annotations

from proseferno.voice.insights import count_mix, prose_sentences, sample_sentences, verbatim_only
from proseferno.voice.schemas import MixCategory, SentenceLabel, VoiceInsights


def _insights(labels: list[tuple[int, str]]) -> VoiceInsights:
    return VoiceInsights(
        headline="h",
        tone=[],
        signature_phrases=[],
        steer_clear=[],
        mix_categories=[MixCategory(name="Chatty", description="talks"), MixCategory(name="Data", description="numbers")],
        sentence_categories=[SentenceLabel(index=i, category=c) for i, c in labels],
        image_habits=[],
        caption_example="",
    )


def test_count_mix_ignores_bad_labels() -> None:
    labels = [(1, "Chatty"), (2, "data"), (3, "Chatty"), (3, "Data"), (9, "Chatty"), (4, "Jokes"), (0, "Data")]
    mix, total = count_mix(_insights(labels), sentence_count=4)
    assert total == 3
    assert [(m["name"], m["count"], m["share"]) for m in mix] == [("Chatty", 2, 66.7), ("Data", 1, 33.3)]


def test_count_mix_with_no_valid_labels_is_empty() -> None:
    mix, total = count_mix(_insights([(5, "Chatty")]), sentence_count=2)
    assert mix == [] and total == 0


def test_prose_sentences_skip_headings_code_and_images() -> None:
    markdown = """# Title

Here is a confession. I peeked at the test early.

```python
print("not prose. at all.")
```

![chart](x.png)
- **Fix the sample size** up front, then wait.
Ok.
"""
    assert prose_sentences(markdown) == [
        "Here is a confession.",
        "I peeked at the test early.",
        "Fix the sample size up front, then wait.",
    ]


def test_sample_sentences_take_turns_between_posts() -> None:
    a = " ".join(f"Post A says thing {i}." for i in range(50))
    b = " ".join(f"Post B says thing {i}." for i in range(50))
    picked = sample_sentences([a, b], limit=6)
    # Three from each post, spread through it rather than its opening, alternating posts.
    assert picked == [f"Post {p} says thing {i}." for i in (0, 16, 33) for p in "AB"]


def test_verbatim_only_keeps_real_phrases() -> None:
    texts = ["Here is a confession. Everyone peeks, honestly."]
    assert verbatim_only(["“Everyone peeks”", "here is a CONFESSION", "made up line", "peeks, honestly"], texts) == [
        "Everyone peeks",
        "here is a CONFESSION",
        "peeks, honestly",
    ]
