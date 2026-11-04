from __future__ import annotations

import httpx
import pytest

from proseferno.db import ProjectReference
from proseferno.llm import Citation, ResearchResult
from proseferno.writer.dials import auto_reference_count
from proseferno.writer.links import HttpLinkChecker
from proseferno.writer.references import (
    PlannedReference,
    add_go_deeper,
    check_edit,
    in_post,
    norm_url,
    plan_references,
    remove_go_deeper,
)
from proseferno.writer.schemas import ReferenceEdit, ReferencePlan, ReferenceSlot

POST = """# Title

*Subtitle line.*

{{image:hero}}

First paragraph says something. It has two sentences.

## Section

Second paragraph makes a claim.

```python
code = "Do not anchor here."
```

Third paragraph wraps up.

{{image:meme}}
"""


def slot(kind: str, anchor: str = "", placement: str = "inline") -> ReferenceSlot:
    return ReferenceSlot(kind=kind, placement=placement, anchor=anchor, purpose="p", query="q")  # type: ignore[arg-type]


def edit(replace: str, *, url: str = "", quote: str = "") -> ReferenceEdit:
    return ReferenceEdit(slot="r1", find="", replace=replace, url=url, title="", speaker="", quote=quote)


@pytest.mark.parametrize(("words", "count"), [(800, 5), (2000, 5), (2500, 6), (3000, 7), (6000, 12)])
def test_reference_count_grows_with_length(words: int, count: int) -> None:
    assert auto_reference_count(words) == count


def test_plan_keeps_placeable_slots_only() -> None:
    plan = ReferencePlan(
        slots=[
            slot("source", "First paragraph says something."),
            slot("quote", "First paragraph says something.", "blockquote"),  # same paragraph: dropped
            slot("quote", "Second paragraph makes a claim.", "blockquote"),
            slot("source", 'code = "Do not anchor here."'),  # in code: dropped
            slot("source", "# Title"),  # the title: dropped
            slot("resource", "not in the post"),  # falls back to the list
            slot("social_post", "Third paragraph wraps up.", "go_deeper"),  # posts never go in the list
            slot("related_article", placement="go_deeper"),
        ]
    )
    planned = plan_references(plan, POST, count=10, kinds=["source", "quote", "social_post", "resource", "related_article"])
    assert [(p.slot_id, p.kind, p.placement) for p in planned] == [
        ("r1", "source", "inline"),
        ("r2", "quote", "blockquote"),
        ("r3", "resource", "go_deeper"),
        ("r4", "social_post", "blockquote"),
        ("r5", "related_article", "go_deeper"),
    ]
    # A blockquote anchor runs to the end of its paragraph so the quote goes after it.
    assert planned[3].anchor == "Third paragraph wraps up."
    assert plan_references(plan, POST, count=2, kinds=["quote"], start_index=4)[0].slot_id == "r4"
    assert plan_references(plan, POST, count=0, kinds=["source"]) == []


def test_check_edit_rejects_invented_urls_and_quotes() -> None:
    research = ResearchResult(
        text='Box wrote "All models are wrong, but some are useful."',
        citations=[Citation(url="https://www.example.com/box/", title="Box 1976")],
    )
    planned = PlannedReference("r1", "quote", "blockquote", "A claim.", "", "")
    good = "A claim.\n\n> “All models are wrong, but some are useful.” — [George Box](https://example.com/box)"
    error, fields = check_edit(planned, edit(good, quote="All models are wrong, but some are useful."), research)
    assert error is None and fields["url"] == "https://example.com/box" and fields["title"] == "Box 1976"

    assert check_edit(planned, edit(good.replace("example.com/box", "invented.org/x")), research)[0]
    made_up = good.replace("but some are useful", "and none are useful")
    assert "verify" in (check_edit(planned, edit(made_up, quote="All models are wrong, and none are useful."), research)[0] or "")
    assert "didn't link" in (check_edit(planned, edit("A claim, as Box said."), research)[0] or "")
    assert "Couldn't find" in (check_edit(planned, edit(""), research)[0] or "")

    listed = PlannedReference("r2", "resource", "go_deeper", "", "", "")
    error, fields = check_edit(listed, edit("* [Box](https://example.com/box)\n  is worth it"), research)
    assert error is None and fields["replace"] == "- [Box](https://example.com/box) is worth it"


def test_go_deeper_list_is_created_extended_and_removed() -> None:
    one = add_go_deeper(POST, "Go deeper", "- [A](https://a.example)")
    assert one.index("## Go deeper") < one.index("- [A](https://a.example)") < one.index("{{image:meme}}")
    two = add_go_deeper(one, "Go deeper", "- [B](https://b.example)")
    assert "- [A](https://a.example)\n- [B](https://b.example)\n" in two
    back = remove_go_deeper(remove_go_deeper(two, "Go deeper", "- [A](https://a.example)"), "Go deeper", "- [B](https://b.example)")
    assert "Go deeper" not in back and back.strip() == POST.strip()


def test_in_post() -> None:
    row = ProjectReference(project_id=1, slot_id="r1", kind="source", inserted="Second paragraph [x](https://x.example).")
    assert not in_post(row, POST)
    assert in_post(row, POST.replace("Second paragraph makes a claim.", row.inserted))
    listed = ProjectReference(project_id=1, slot_id="r2", kind="resource", placement="go_deeper", inserted="- [A](https://a.example)")
    assert in_post(listed, add_go_deeper(POST, "Go deeper", listed.inserted))
    assert not in_post(listed, "intro - [A](https://a.example) inline")


def test_norm_url() -> None:
    assert norm_url("HTTPS://WWW.Example.com/a/#frag") == norm_url("https://example.com/a")


async def test_link_checker_only_trusts_clear_evidence() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "gone.example":
            raise httpx.ConnectError("[Errno 11001] getaddrinfo failed", request=request)
        if request.url.host == "flaky.example":
            raise httpx.ConnectError("connection reset", request=request)
        return httpx.Response({"/404": 404, "/410": 410, "/403": 403, "/429": 429}.get(request.url.path, 200))

    checker = HttpLinkChecker(transport=httpx.MockTransport(handler))
    urls = [f"https://site.example/{code}" for code in ("404", "410", "403", "429", "ok")]
    dead = await checker.dead([*urls, "https://gone.example/", "https://flaky.example/", "mailto:x@y.z"])
    assert dead == {"https://site.example/404", "https://site.example/410", "https://gone.example/"}


async def test_demo_research_never_offers_a_tried_url() -> None:
    from proseferno.demo import FakeLLM

    # The demo app's fake restarts its counter with the app, so it must skip what the prompt says was tried.
    prompt = "Reference kind: source\nDo not use these URLs, they were already tried: https://example.com/source/1, https://example.com/source/2\n"
    result = await FakeLLM().research(system=[], prompt=prompt, effort="low")
    assert [c.url for c in result.citations] == ["https://example.com/source/3"]
