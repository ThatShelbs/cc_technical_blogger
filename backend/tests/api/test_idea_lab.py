"""Idea Lab end to end against the fake Claude and the stand-in feed collector (nothing goes online)."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from inferno_ghostwriter.demo import FakeLLM


def _persona(client: TestClient, name: str = "Me") -> int:
    pid = int(client.post("/api/personas", json={"name": name}).json()["id"])
    client.post(f"/api/personas/{pid}/samples/import-sample-writing")
    job = client.post(f"/api/personas/{pid}/voice-profile").json()
    assert client.get(f"/api/jobs/{job['id']}").json()["status"] == "succeeded"
    return pid


def _brainstorm(client: TestClient, **body: Any) -> dict[str, Any]:
    response = client.post("/api/idea-lab/sessions", json=body)
    assert response.status_code == 201, response.text
    created = response.json()
    job = client.get(f"/api/jobs/{created['job_id']}").json()
    assert job["status"] == "succeeded", job["error"]
    return dict(client.get(f"/api/idea-lab/sessions/{created['session']['id']}").json())


def test_empty_lab(client: TestClient) -> None:
    lab = client.get("/api/idea-lab").json()
    assert lab["signals"] == 0 and lab["trends"] == [] and not lab["fresh"] and lab["last_refresh"] is None
    assert client.get("/api/idea-lab/sessions").json() == []
    assert client.post("/api/idea-lab/sessions", json={}).status_code == 422  # no persona yet


def test_research_builds_the_base_and_drops_unverifiable_trends(client: TestClient) -> None:
    job = client.post("/api/idea-lab/research", json={}).json()
    assert client.get(f"/api/jobs/{job['id']}").json()["status"] == "succeeded"
    lab = client.get("/api/idea-lab").json()
    assert lab["fresh"] and lab["signals"] >= 10
    labels = [t["label"] for t in lab["trends"]]
    assert "Agent frameworks add built-in evaluation" in labels
    assert "An unverifiable rumour" not in labels
    assert {t["kind"] for t in lab["trends"]} >= {"launch", "claim", "creator_wave", "industry_pattern", "question"}
    assert all(t["evidence"] and all(e["url"].startswith("https://") for e in t["evidence"]) for t in lab["trends"])
    # Every source reports how it answered.
    sources = client.get("/api/idea-lab/sources").json()["sources"]
    assert all(s["ok"] for s in sources if s["enabled"])


def test_another_search_adds_to_the_base(client: TestClient) -> None:
    client.post("/api/idea-lab/research", json={})
    before = len(client.get("/api/idea-lab").json()["trends"])
    job = client.post("/api/idea-lab/research", json={"query": "  feature   stores "}).json()
    assert client.get(f"/api/jobs/{job['id']}").json()["result"]["query"] == "feature stores"
    lab = client.get("/api/idea-lab").json()
    assert len(lab["trends"]) == before + 1
    assert any("feature stores" in t["label"] for t in lab["trends"])
    assert lab["searches"][0]["query"] == "feature stores"


@pytest.mark.parametrize(("mode", "count"), [("light", 10), ("medium", 25), ("heavy", 50)])
def test_each_mode_gives_its_number_of_ideas(client: TestClient, mode: str, count: int) -> None:
    pid = _persona(client)
    session = _brainstorm(client, persona_id=pid, mode=mode)
    assert session["status"] == "ready" and len(session["items"]) == count
    assert sum(session["mix"].values()) == count
    ideas = session["items"]
    assert [i["rank"] for i in ideas] == list(range(1, count + 1))
    assert ideas == sorted(ideas, key=lambda i: -i["score"])
    assert len({i["title"] for i in ideas}) == count
    by_approach: dict[str, int] = {}
    for idea in ideas:
        by_approach[idea["approach"]] = by_approach.get(idea["approach"], 0) + 1
        assert idea["title"] and idea["brief"] and len(idea["outline"]) >= 4 and idea["theme"]
        assert set(idea["scores"]) >= {"timeliness", "demand", "fit", "differentiation", "effort"}
    assert by_approach == session["mix"]
    # Ideas that rest on the research carry its links.
    assert all(i["evidence"] for i in ideas if i["approach"] in ("emerging", "reader_questions", "counter_take"))
    # The research ran as part of the first brainstorm.
    assert client.get("/api/idea-lab").json()["fresh"]


def test_core_only_mix_and_reuse_of_fresh_research(client: TestClient, fake_llm: FakeLLM) -> None:
    pid = _persona(client)
    first = _brainstorm(client, persona_id=pid, mode="light", extras=[])
    assert first["mix"] == {"emerging": 5, "builder": 3, "expander": 2}
    builders = [i for i in first["items"] if i["approach"] == "builder"]
    assert all(i["builds_on"] for i in builders)
    searches = sum(1 for call in fake_llm.calls if call["kind"] == "research")
    _brainstorm(client, persona_id=pid, mode="light", extras=[])
    assert sum(1 for call in fake_llm.calls if call["kind"] == "research") == searches  # the base was fresh
    _brainstorm(client, persona_id=pid, mode="light", extras=[], refresh_research=True)
    assert sum(1 for call in fake_llm.calls if call["kind"] == "research") > searches


def test_sparks_and_no_research(client: TestClient) -> None:
    pid = _persona(client)
    session = _brainstorm(client, persona_id=pid, mode="light", extras=[], sparks="a note about dashboards", refresh_research=False)
    # Nothing on file and research switched off: portfolio ideas only, and the author is told why.
    assert "emerging" not in session["mix"] and session["mix"]["sparks"] == 1
    assert any("research" in note for note in session["notes"])
    assert len(session["items"]) == 10


def test_dismissed_and_used_ideas_do_not_come_back(client: TestClient) -> None:
    pid = _persona(client)
    first = _brainstorm(client, persona_id=pid, mode="light")
    dismissed, saved = first["items"][0], first["items"][1]
    assert client.patch(f"/api/ideas/{dismissed['id']}", json={"state": "dismissed"}).json()["state"] == "dismissed"
    assert client.patch(f"/api/ideas/{saved['id']}", json={"state": "saved"}).json()["state"] == "saved"
    second = _brainstorm(client, persona_id=pid, mode="light")
    titles = {i["title"] for i in second["items"]}
    assert dismissed["title"] not in titles and saved["title"] not in titles


def test_edit_an_idea(client: TestClient) -> None:
    pid = _persona(client)
    idea = _brainstorm(client, persona_id=pid, mode="light")["items"][0]
    updated = client.patch(f"/api/ideas/{idea['id']}", json={"title": "  My   own title ", "outline": ["one", " ", "two"]}).json()
    assert updated["title"] == "My own title" and updated["outline"] == ["one", "two"]
    assert updated["prompt"].splitlines()[0] == "My own title" and "- one" in updated["prompt"]
    assert client.patch("/api/ideas/9999", json={"state": "saved"}).status_code == 404


def test_write_a_post_from_an_idea(client: TestClient) -> None:
    pid = _persona(client)
    other = _persona(client, "Other voice")
    ideas = _brainstorm(client, persona_id=pid, mode="light")["items"]
    idea = next(i for i in ideas if i["evidence"] and i["article_type"] != "auto")

    created = client.post(f"/api/ideas/{idea['id']}/write", json={"persona_id": other}).json()
    project = created["project"]
    assert project["persona_id"] == other and project["status"] == "ready"
    assert project["prompt"].startswith(idea["title"]) and "Outline:" in project["prompt"]
    assert idea["evidence"][0]["url"] in project["prompt"]
    assert project["dials"]["article_type"] == idea["article_type"]
    after = client.get(f"/api/ideas/{idea['id']}").json()
    assert after["state"] == "used" and after["project_id"] == project["id"]
    assert client.post(f"/api/ideas/{idea['id']}/write", json={}).status_code == 409
    assert client.patch(f"/api/ideas/{idea['id']}", json={"state": "dismissed"}).status_code == 409

    # The persona that wrote it sees where the post came from, and whether that paid off.
    client.patch(f"/api/projects/{project['id']}", json={"stage": "published", "outcome": "good"})
    sources = client.get(f"/api/personas/{other}/insights").json()["track_record"]["idea_sources"]
    assert sources == [{"id": idea["approach"], "label": idea["approach_label"], "count": 1, "wins": 1}]

    # Deleting the post puts the idea back on the saved list.
    client.delete(f"/api/projects/{project['id']}")
    after = client.get(f"/api/ideas/{idea['id']}").json()
    assert after["state"] == "saved" and after["project_id"] is None


def test_ab_test_from_an_idea(client: TestClient) -> None:
    pid = _persona(client)
    idea = _brainstorm(client, persona_id=pid, mode="light")["items"][0]
    created = client.post(f"/api/ideas/{idea['id']}/write", json={"mode": "ab"}).json()
    assert created["project"]["ab_test"]["status"] == "voting"
    assert client.get(f"/api/ideas/{idea['id']}").json()["state"] == "used"


def test_customize_first_marks_the_idea_used(client: TestClient) -> None:
    pid = _persona(client)
    idea = _brainstorm(client, persona_id=pid, mode="light")["items"][0]
    # Not generated yet, so the title is still the idea's (writing the post replaces it with the written title).
    body = {"prompt": idea["prompt"] + "\n- my extra point", "persona_id": pid, "idea_id": idea["id"], "generate": False}
    created = client.post("/api/projects", json=body)
    assert created.status_code == 201 and created.json()["project"]["title"] == idea["title"][:80]
    assert client.get(f"/api/ideas/{idea['id']}").json()["state"] == "used"
    assert client.post("/api/projects", json={"prompt": "x y z", "persona_id": pid, "idea_id": 9999}).status_code == 404


def test_sources_can_be_changed_and_reset(client: TestClient) -> None:
    start = client.get("/api/idea-lab/sources").json()
    assert start["voices"] and start["industries"] and start["search_only"]
    body = {
        "disabled": ["hn_ai"],
        "custom": [{"name": "My feed", "url": "https://blog.example.com/rss"}],
        "voices": ["Ada Lovelace"],
        "industries": ["Energy"],
    }
    changed = client.put("/api/idea-lab/sources", json=body).json()
    by_id = {s["id"]: s for s in changed["sources"]}
    assert not by_id["hn_ai"]["enabled"] and by_id["arxiv_ml"]["enabled"]  # left out of "disabled" = switched on
    assert not by_id["custom_blog_example_com_rss"]["builtin"]
    assert changed["voices"] == ["Ada Lovelace"] and "news_energy" in by_id
    assert client.put("/api/idea-lab/sources", json={"custom": [{"name": "Bad", "url": "ftp://nope.example"}]}).status_code == 422
    reset = client.put("/api/idea-lab/sources", json={"reset": True}).json()
    assert [s["id"] for s in reset["sources"]] == [s["id"] for s in start["sources"]]
    assert next(s for s in reset["sources"] if s["id"] == "hn_ai")["enabled"]


def test_deleting_a_brainstorm_keeps_what_the_author_decided(client: TestClient) -> None:
    pid = _persona(client)
    session = _brainstorm(client, persona_id=pid, mode="light")
    dismissed, saved = session["items"][0], session["items"][1]
    client.patch(f"/api/ideas/{dismissed['id']}", json={"state": "dismissed"})
    client.patch(f"/api/ideas/{saved['id']}", json={"state": "saved"})
    assert client.delete(f"/api/idea-lab/sessions/{session['id']}").status_code == 204
    assert client.get("/api/idea-lab/sessions").json() == []
    assert client.get(f"/api/ideas/{dismissed['id']}").status_code == 200
    # Saved ideas outlive their brainstorm in the bank.
    assert [i["id"] for i in client.get("/api/ideas").json()] == [saved["id"]]
    # Unsaved ones stay on file, out of sight, so they are not proposed again.
    hidden = {i["title"].lower() for i in session["items"][2:]}
    assert client.get(f"/api/ideas/{session['items'][2]['id']}").json()["stage"] == "prospective"
    again = _brainstorm(client, persona_id=pid, mode="light")
    assert not hidden & {i["title"].lower() for i in again["items"]}


def test_new_brainstorms_do_not_repeat_earlier_ideas(client: TestClient) -> None:
    pid = _persona(client)
    first = {i["title"].lower() for i in _brainstorm(client, persona_id=pid, mode="light")["items"]}
    second = _brainstorm(client, persona_id=pid, mode="light")
    # Nothing was saved or dismissed, and still no idea from the first brainstorm comes back.
    assert second["items"] and not first & {i["title"].lower() for i in second["items"]}


def test_the_lifecycle_follows_the_post(client: TestClient) -> None:
    pid = _persona(client)
    idea = _brainstorm(client, persona_id=pid, mode="light")["items"][0]
    assert (idea["stage"], idea["stage_label"]) == ("prospective", "Prospective")
    assert client.patch(f"/api/ideas/{idea['id']}", json={"state": "saved"}).json()["stage"] == "serious"
    project = client.post(f"/api/ideas/{idea['id']}/write", json={}).json()["project"]
    assert project["idea_id"] == idea["id"]
    after = client.get(f"/api/ideas/{idea['id']}").json()
    assert after["stage"] == "generated" and after["project_title"] == project["title"]
    steps = [
        ({"stage": "ready"}, "ready"),
        # Publishing starts the outcome at "too early to tell".
        ({"stage": "published"}, "too_early"),
        ({"outcome": "small"}, "small_hit"),
        ({"outcome": "good"}, "medium_hit"),
        ({"outcome": "viral"}, "big_hit"),
    ]
    for body, stage in steps:
        client.patch(f"/api/projects/{project['id']}", json=body)
        assert client.get(f"/api/ideas/{idea['id']}").json()["stage"] == stage
    bank = client.get("/api/ideas", params={"persona_id": pid}).json()
    assert [(i["id"], i["stage_label"]) for i in bank] == [(idea["id"], "Big hit")]
    summary = next(p for p in client.get("/api/projects").json() if p["id"] == project["id"])
    assert summary["idea_id"] == idea["id"]


def test_dismiss_restore_and_note(client: TestClient) -> None:
    pid = _persona(client)
    idea = _brainstorm(client, persona_id=pid, mode="light")["items"][0]
    assert client.patch(f"/api/ideas/{idea['id']}", json={"state": "dismissed"}).json()["stage"] == "dismissed"
    assert [i["id"] for i in client.get("/api/ideas", params={"state": "dismissed"}).json()] == [idea["id"]]
    restored = client.patch(f"/api/ideas/{idea['id']}", json={"state": "new", "note": "  ask the platform team  "}).json()
    assert restored["stage"] == "prospective" and restored["note"] == "ask the platform team"


def test_add_your_own_idea_to_the_bank(client: TestClient) -> None:
    assert client.post("/api/ideas", json={"title": "No persona yet"}).status_code == 422
    pid = _persona(client)
    created = client.post("/api/ideas", json={"title": "  Why our  dashboards died ", "outline": ["a", "", "b"], "note": "mine"})
    assert created.status_code == 201
    idea = created.json()
    assert idea["title"] == "Why our dashboards died" and idea["outline"] == ["a", "b"]
    assert idea["stage"] == "serious" and idea["approach_label"] == "Your own idea" and idea["persona_id"] == pid
    # It lives in the bank, not in the brainstorm list, and a brainstorm will not propose it again.
    assert client.get("/api/idea-lab/sessions").json() == []
    assert [i["id"] for i in client.get("/api/ideas").json()] == [idea["id"]]
    second = client.post("/api/ideas", json={"title": "Another one of mine", "persona_id": pid}).json()
    assert second["session_id"] == idea["session_id"]
    written = client.post(f"/api/ideas/{idea['id']}/write", json={}).json()["project"]
    assert written["prompt"].startswith("Why our dashboards died")


def test_deleting_a_persona_removes_its_brainstorms(client: TestClient) -> None:
    pid = _persona(client)
    session = _brainstorm(client, persona_id=pid, mode="light")
    assert client.delete(f"/api/personas/{pid}").status_code == 204
    assert client.get(f"/api/idea-lab/sessions/{session['id']}").status_code == 404
    assert client.get("/api/idea-lab").json()["trends"]  # the research is shared, so it stays


def test_idea_jobs_are_not_the_personas_voice_job(client: TestClient) -> None:
    pid = _persona(client)
    _brainstorm(client, persona_id=pid, mode="light")
    assert client.get(f"/api/personas/{pid}").json()["active_job_id"] is None
