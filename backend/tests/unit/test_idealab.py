"""Idea Lab building blocks: feed parsing, the source catalog, the link check, the mix and duplicate removal."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from inferno_ghostwriter.idealab.collect import HttpSignalCollector, NoSignalCollector, parse, parse_date
from inferno_ghostwriter.idealab.ideate import CORE_MIX, MODES, Candidate, dedupe, plan_mix, select, title_tokens, too_similar
from inferno_ghostwriter.idealab.research import checked_trends, standing_beats
from inferno_ghostwriter.idealab.schemas import IdeaDraft, Trend, TrendDigest
from inferno_ghostwriter.idealab.sources import CustomSource, Source, SourceChanges, build_config
from inferno_ghostwriter.writer.references import norm_url

RSS = """<?xml version="1.0"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/"><channel><title>Feed</title>
<item><title>First &amp; best</title><link>https://example.com/a</link><dc:creator>Ann</dc:creator>
<pubDate>Mon, 09 Nov 2026 10:00:00 GMT</pubDate><description>&lt;p&gt;Some &lt;b&gt;bold&lt;/b&gt; text.&lt;/p&gt;</description></item>
<item><title>No link</title></item>
</channel></rss>"""

ATOM = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Atom post</title><link rel="alternate" href="https://example.com/atom"/><updated>2026-11-10T08:00:00Z</updated>
<author><name>Bo</name></author><summary>Short.</summary></entry>
</feed>"""


def _source(kind: str = "rss", url: str = "https://feeds.example.com/x") -> Source:
    return Source(id="s1", name="Source One", group="creator", kind=kind, url=url)  # type: ignore[arg-type]


def test_rss_and_atom_are_parsed_to_signals() -> None:
    rss = parse(_source(), RSS)
    assert [(s.title, s.url, s.author, s.summary) for s in rss] == [("First & best", "https://example.com/a", "Ann", "Some bold text.")]
    assert rss[0].published_at == datetime(2026, 11, 9, 10, tzinfo=UTC)
    atom = parse(_source(), ATOM)
    assert (atom[0].title, atom[0].url, atom[0].author) == ("Atom post", "https://example.com/atom", "Bo")


def test_a_feed_with_a_doctype_is_refused() -> None:
    with pytest.raises(ValueError, match="document type"):
        parse(_source(), '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><rss/>')


def test_json_sources_are_parsed() -> None:
    hn = parse(
        _source("hn"), {"hits": [{"objectID": "42", "title": "Show: a thing", "points": 99, "num_comments": 7, "created_at_i": 1794000000}]}
    )
    assert hn[0].url == "https://news.ycombinator.com/item?id=42" and hn[0].engagement == 99
    gh = parse(
        _source("github"),
        {"items": [{"html_url": "https://github.com/a/b", "full_name": "a/b", "description": "x", "stargazers_count": 5}]},
    )
    assert gh[0].title == "a/b: x" and gh[0].engagement == 5
    papers = parse(
        _source("hf_papers"), [{"paper": {"id": "1234.5", "title": "A paper", "upvotes": 3}, "publishedAt": "2026-11-01T00:00:00.000Z"}]
    )
    assert papers[0].url.endswith("/papers/1234.5")
    assert parse_date("not a date") is None


async def test_one_failing_source_does_not_fail_the_rest() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "bad" in request.url.host:
            return httpx.Response(500)
        # No personal data and a generic client name in every request.
        assert "Inferno Ghostwriter feed reader" in request.headers["user-agent"]
        return httpx.Response(200, text=ATOM)

    good = Source(id="good", name="Good", group="creator", kind="rss", url="https://good.example.com/feed")
    bad = Source(id="bad", name="Bad", group="creator", kind="rss", url="https://bad.example.com/feed")
    collector = HttpSignalCollector(transport=httpx.MockTransport(handler))
    signals, health = await collector.collect([good, bad], since=datetime(2026, 1, 1, tzinfo=UTC))
    assert [s.source_id for s in signals] == ["good"]
    assert {h.source_id: h.ok for h in health} == {"good": True, "bad": False}
    assert "500" in next(h.error for h in health if not h.ok)


async def test_old_items_are_left_out_and_placeholders_filled() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, text=ATOM)

    source = Source(id="s", name="S", group="code", kind="rss", url="https://x.example.com/?since={since_date}&ts={since_ts}")
    since = datetime.now(UTC) - timedelta(days=1)
    signals, _ = await HttpSignalCollector(transport=httpx.MockTransport(handler)).collect([source], since=since)
    assert signals == []  # the Atom entry is from 2026-11-10, before "yesterday"
    assert since.date().isoformat() in seen[0] and "{since" not in seen[0]


async def test_the_stand_in_collector_never_needs_a_network() -> None:
    signals, health = await NoSignalCollector().collect([_source()], since=datetime.now(UTC))
    assert signals and all(s.url.startswith("https://example.com/") for s in signals)
    assert await NoSignalCollector([]).collect([], since=datetime.now(UTC)) == ([], [])
    assert health[0].ok


def test_catalog_and_author_changes() -> None:
    config = build_config(SourceChanges())
    ids = [s.id for s in config.sources]
    assert len(ids) == len(set(ids))
    assert config.voices and config.industries
    assert "news_healthcare" in ids and "when%3A7d" in next(s.url for s in config.sources if s.id == "news_healthcare")
    arxiv = next(s for s in config.sources if s.id == "arxiv_ml")
    assert not arxiv.enabled and arxiv not in config.active()

    changed = build_config(
        SourceChanges(
            disabled=["hn_ai"],
            enabled=["arxiv_ml"],
            custom=[CustomSource(name="My feed", url="https://blog.example.com/rss")],
            voices=["  Ada   Lovelace ", "ada lovelace", ""],
            industries=["Energy"],
        )
    )
    by_id = {s.id: s for s in changed.sources}
    assert not by_id["hn_ai"].enabled and by_id["arxiv_ml"].enabled
    assert not by_id["custom_blog_example_com_rss"].builtin
    assert changed.voices == ["Ada Lovelace"] and changed.industries == ["Energy"]
    assert "news_energy" in by_id and "news_healthcare" not in by_id
    with pytest.raises(ValueError):
        CustomSource(name="x", url="ftp://nope")


def test_scouts_take_their_names_from_the_catalog() -> None:
    config = build_config(SourceChanges(voices=["Ada Lovelace"], industries=["Energy", "Mining"]))
    beats = standing_beats(config)
    assert [b.id for b in beats] == ["launches", "voices", "creators", "community", "industry_energy", "industry_mining"]
    assert "Ada Lovelace" in beats[1].instructions
    assert beats[-1].source_ids == ("news_mining",)


def _trend(label: str, urls: list[str]) -> Trend:
    return Trend(kind="launch", label=label, summary="s", heat=5, evidence_urls=urls)


def test_trends_without_a_real_link_are_dropped() -> None:
    allowed = {norm_url("https://example.com/a"): "Page A", norm_url("https://www.example.com/b/"): "Page B"}
    digest = TrendDigest(
        trends=[
            _trend("Real  thing", ["https://example.com/a/", "https://example.com/made-up"]),
            _trend("Invented", ["https://example.com/made-up"]),
            _trend("real thing", ["https://example.com/b"]),  # same label again
        ]
    )
    kept = checked_trends(digest, allowed)
    assert [(t.label, [e["title"] for e in ev]) for t, ev in kept] == [("Real thing", ["Page A"])]


@pytest.mark.parametrize("mode", list(MODES))
def test_the_mix_adds_up_to_the_mode(mode: str) -> None:
    everything = {"emerging": True, "builder": True, "expander": True, "reader_questions": True, "counter_take": True, "sparks": True}
    core, notes = plan_mix(mode, [], everything)
    assert tuple(core.values()) == CORE_MIX[mode] and sum(core.values()) == MODES[mode] and not notes
    full, _ = plan_mix(mode, ["reader_questions", "counter_take", "sparks"], everything)
    assert sum(full.values()) == MODES[mode] and set(full) == set(everything)
    assert full["emerging"] >= full["builder"] >= full["reader_questions"] >= 1


def test_an_approach_with_nothing_to_work_from_hands_over_its_share() -> None:
    mix, notes = plan_mix("light", ["counter_take"], {"emerging": True, "builder": False, "expander": True, "counter_take": False})
    assert mix == {"emerging": 8, "expander": 2} and len(notes) == 2
    no_research, notes = plan_mix("light", [], {"emerging": False, "builder": True, "expander": True})
    assert no_research == {"builder": 3, "expander": 7} and "research" in notes[0]


def _candidate(title: str, approach: str = "emerging", score: float = 0.0) -> Candidate:
    draft = IdeaDraft(title=title, brief="b", angle="a", outline=["one", "two"], why_now="w", shelf_life="evergreen", article_type="auto")
    return Candidate(approach=approach, draft=draft, score=score)


def test_duplicates_and_near_copies_of_existing_posts_are_removed() -> None:
    assert too_similar(title_tokens("Why pie charts are lame"), title_tokens("Pie charts are lame: a roast"))
    assert not too_similar(title_tokens("Sizing an A/B test"), title_tokens("Gradient boosting on tabular data"))
    kept = dedupe(
        [
            _candidate("Why your A/B tests are underpowered"),
            _candidate("Your A/B tests are underpowered, and why"),
            _candidate("Pie Charts Are Lame, again"),
            _candidate("Prompt caching, measured"),
        ],
        against=["Pie Charts Are Lame"],
    )
    assert [c.draft.title for c in kept] == ["Why your A/B tests are underpowered", "Prompt caching, measured"]


def test_selection_holds_the_mix_then_tops_up() -> None:
    candidates = [_candidate(f"E{i}", "emerging", 9 - i) for i in range(4)] + [_candidate(f"B{i}", "builder", 5 - i) for i in range(2)]
    chosen = select(candidates, {"emerging": 2, "builder": 3})
    # Builder is one short, so the next best emerging idea fills the gap; best first overall.
    assert [c.draft.title for c in chosen] == ["E0", "E1", "E2", "B0", "B1"]


@pytest.mark.parametrize(
    ("state", "project", "stage"),
    [
        ("new", None, "prospective"),
        ("saved", None, "serious"),
        ("dismissed", None, "dismissed"),
        ("used", None, "serious"),  # the post is gone
        ("used", {}, "generated"),
        ("used", {"stage": "ready"}, "ready"),
        ("used", {"stage": "published"}, "published"),
        ("used", {"stage": "published", "outcome": "too_early"}, "too_early"),
        ("used", {"stage": "published", "outcome": "small"}, "small_hit"),
        ("used", {"stage": "published", "outcome": "good"}, "medium_hit"),
        ("used", {"stage": "published", "outcome": "viral"}, "big_hit"),
    ],
)
def test_an_ideas_stage_follows_its_post(state: str, project: dict[str, str] | None, stage: str) -> None:
    from inferno_ghostwriter.db import Idea, Project
    from inferno_ghostwriter.idealab.lifecycle import STAGES, stage_label, stage_of

    idea = Idea(session_id=1, persona_id=1, approach="emerging", title="T", state=state)
    post = Project(persona_id=1, prompt="p", **project) if project is not None else None
    assert stage_of(idea, post) == stage
    assert stage_label(stage) == STAGES[stage]
