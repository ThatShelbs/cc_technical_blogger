"""References: generation weaves them in, and each one can be redrawn, reverted or removed."""

from __future__ import annotations

from fastapi.testclient import TestClient

from proseferno.demo import FakeLLM
from proseferno.llm import ResearchResult
from tests.api.test_flow import create_persona, ready_post, upload


def test_generation_weaves_in_five_verified_references(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM) -> None:
    project = ready_post(client, sample_docx)
    refs = project["references"]

    assert project["status"] == "ready"
    assert len(refs) == 5 and all(r["status"] == "ready" and r["in_post"] for r in refs)
    assert {r["kind"] for r in refs} == {"source", "quote", "social_post", "resource", "related_article"}
    for ref in refs:
        assert f"]({ref['url']})" in project["markdown"]
        assert len(ref["history"]) == 1
    # Quotes and posts are blockquotes with the exact words found; resources go in a list before the meme.
    quote = next(r for r in refs if r["kind"] == "quote")
    assert f'> "{quote["quote"]}" — [{quote["speaker"]}]({quote["url"]})' in project["markdown"]
    deeper = project["markdown"].index("## Go deeper")
    assert project["markdown"].index("](https://example.com/resource/") > deeper
    assert deeper < project["markdown"].index("{{image:meme}}")
    # References are researched and woven before the images are drawn, so images see the final text.
    tasks = fake_llm.tasks()
    assert tasks.index("reference plan") < tasks.index("research") < tasks.index("reference weave") < tasks.index("hero image design")
    # Image placeholders all survive.
    assert project["markdown"].count("{{image:") == len(project["images"])


def test_reference_count_zero_skips_the_pass(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM) -> None:
    pid = create_persona(client)["id"]
    upload(client, pid, sample_docx)
    client.post(f"/api/personas/{pid}/voice-profile")
    created = client.post("/api/projects", json={"prompt": "Pie charts", "dials": {"revision_passes": 0, "reference_count": 0}}).json()
    project = client.get(f"/api/projects/{created['project']['id']}").json()

    assert project["references"] == [] and project["resolved_dials"]["reference_count"] == 0
    assert "reference plan" not in fake_llm.tasks()

    # "Find references" adds them to the existing post as a job, and the change can be undone.
    job = client.post(f"/api/projects/{project['id']}/references", json={"count": 2, "kinds": ["source"]})
    assert job.status_code == 202 and job.json()["status"] == "succeeded", job.text
    out = client.get(f"/api/projects/{project['id']}").json()
    assert [r["kind"] for r in out["references"]] == ["source", "source"]
    assert out["revisions"][0]["kind"] == "reference"
    assert all(f"]({r['url']})" in out["markdown"] for r in out["references"])


def test_redraw_revert_and_remove_one_reference(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM) -> None:
    project = ready_post(client, sample_docx)
    url = f"/api/projects/{project['id']}"
    source = next(r for r in project["references"] if r["kind"] == "source")
    others = {r["id"]: r["url"] for r in project["references"] if r["id"] != source["id"]}

    # Redraw finds a different link for the same spot; the rest of the post keeps its references.
    job = client.post(f"/api/references/{source['id']}/redraw")
    assert job.status_code == 202 and job.json()["status"] == "succeeded", job.text
    out = client.get(url).json()
    redrawn = next(r for r in out["references"] if r["id"] == source["id"])
    assert redrawn["url"] != source["url"] and redrawn["in_post"]
    assert source["url"] not in out["markdown"] and redrawn["url"] in out["markdown"]
    assert len(redrawn["history"]) == 2
    assert {r["id"]: r["url"] for r in out["references"] if r["id"] != source["id"]} == others
    assert out["revisions"][0]["kind"] == "reference"
    # The old link is not offered to the researcher again.
    assert source["url"] in [c for c in fake_llm.calls if c["kind"] == "research"][-1]["prompt"]

    # Switching kind: a quote instead of the source, in the same sentence.
    job = client.post(f"/api/references/{source['id']}/redraw", json={"kind": "quote"})
    assert job.json()["status"] == "succeeded", job.json()
    out = client.get(url).json()
    assert next(r for r in out["references"] if r["id"] == source["id"])["kind"] == "quote"

    # Versions: swap the first one back.
    out = client.post(f"/api/references/{source['id']}/revert", json={"index": 0}).json()
    back = next(r for r in out["references"] if r["id"] == source["id"])
    assert back["url"] == source["url"] and source["url"] in out["markdown"]
    assert client.post(f"/api/references/{source['id']}/revert", json={"index": 9}).status_code == 404

    # Remove puts the sentence back the way it read before.
    out = client.delete(f"/api/references/{source['id']}").json()
    assert source["id"] not in [r["id"] for r in out["references"]]
    assert source["url"] not in out["markdown"]
    assert "Pie charts have a fan club." in out["markdown"]

    # Removing every "Go deeper" item also removes its heading.
    for ref in [r for r in out["references"] if r["placement"] == "go_deeper"]:
        out = client.delete(f"/api/references/{ref['id']}").json()
    assert "## Go deeper" not in out["markdown"]
    assert client.delete("/api/references/9999").status_code == 404


def test_edited_out_reference_is_flagged(client: TestClient, sample_docx: bytes) -> None:
    project = ready_post(client, sample_docx)
    url = f"/api/projects/{project['id']}"
    ref = next(r for r in project["references"] if r["kind"] == "source")
    markdown = project["markdown"].replace(f"]({ref['url']})", "](https://example.org/mine)")
    out = client.patch(url, json={"markdown": markdown, "learn": False}).json()
    assert next(r for r in out["references"] if r["id"] == ref["id"])["in_post"] is False
    assert client.post(f"/api/references/{ref['id']}/revert", json={"index": 0}).status_code == 409


def test_a_failed_search_fails_one_reference_not_the_post(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    original = fake_llm.research

    async def flaky(**kwargs):  # type: ignore[no-untyped-def]
        if "Reference kind: quote" in kwargs["prompt"]:
            return ResearchResult(text="Nothing verifiable.", citations=[])
        return await original(**kwargs)

    monkeypatch.setattr(fake_llm, "research", flaky)
    project = ready_post(client, sample_docx)

    assert project["status"] == "ready"
    statuses = {r["kind"]: r["status"] for r in project["references"]}
    assert statuses["quote"] == "error" and statuses["source"] == "ready"
    quote = next(r for r in project["references"] if r["kind"] == "quote")
    assert "Redraw" in (quote["error"] or "") and not quote["in_post"]

    # Redraw tries again; this time the search finds something.
    monkeypatch.setattr(fake_llm, "research", original)
    job = client.post(f"/api/references/{quote['id']}/redraw").json()
    assert job["status"] == "succeeded", job
    out = client.get(f"/api/projects/{project['id']}").json()
    fixed = next(r for r in out["references"] if r["id"] == quote["id"])
    assert fixed["status"] == "ready" and fixed["in_post"] and fixed["url"] in out["markdown"]


def test_invented_links_and_quotes_are_rejected(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    original = fake_llm.structured

    async def liar(**kwargs):  # type: ignore[no-untyped-def]
        result = await original(**kwargs)
        if kwargs["task"] == "reference weave":
            for edit in result.edits:
                if "/source/" in edit.url:
                    edit.replace = edit.replace.replace(edit.url, "https://made-up.example/paper")
                if edit.quote:
                    edit.replace = edit.replace.replace(edit.quote, "Words nobody ever said, I promise you.")
                    edit.quote = "Words nobody ever said, I promise you."
        return result

    monkeypatch.setattr(fake_llm, "structured", liar)
    project = ready_post(client, sample_docx)
    statuses = {r["kind"]: r["status"] for r in project["references"]}
    assert statuses == {"source": "error", "quote": "error", "social_post": "error", "resource": "ready", "related_article": "ready"}
    assert "made-up.example" not in project["markdown"] and "nobody ever said" not in project["markdown"]


def test_regeneration_replaces_references_and_deletes_clean_up(client: TestClient, sample_docx: bytes, services) -> None:  # type: ignore[no-untyped-def]
    from sqlmodel import Session, select

    from proseferno.db import ProjectReference

    project = ready_post(client, sample_docx)
    old_urls = {r["url"] for r in project["references"]}
    client.post(f"/api/projects/{project['id']}/generate")
    out = client.get(f"/api/projects/{project['id']}").json()
    assert len(out["references"]) == 5 and not old_urls & {r["url"] for r in out["references"]}
    assert all(f"]({r['url']})" in out["markdown"] for r in out["references"])

    client.delete(f"/api/projects/{project['id']}")
    with Session(services.engine) as session:
        assert session.exec(select(ProjectReference)).all() == []


def test_section_add_source_is_tracked_as_a_reference(client: TestClient, sample_docx: bytes) -> None:
    project = ready_post(client, sample_docx)
    selection = "So the next time you reach for a pie, reach for a bar instead."
    assert selection in project["markdown"]
    out = client.post(f"/api/projects/{project['id']}/rewrite", json={"selection": selection, "action": "add_source"}).json()
    added = out["references"][-1]
    assert added["url"] == "https://example.com/guide" and added["in_post"] and added["slot_id"] == "r6"


def test_reference_settings_and_persona_default(client: TestClient) -> None:
    out = client.put("/api/settings", json={"reference_max_searches": 2, "check_reference_links": False}).json()
    assert out["reference_max_searches"] == 2 and out["check_reference_links"] is False
    persona = create_persona(client)
    assert persona["default_reference_count"] is None
    url = f"/api/personas/{persona['id']}"
    assert client.patch(url, json={"default_reference_count": 0}).json()["default_reference_count"] == 0
    assert client.patch(url, json={"default_reference_count": None}).json()["default_reference_count"] is None
