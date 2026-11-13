from __future__ import annotations

from fastapi.testclient import TestClient

from proseferno.demo import FakeLLM
from tests.api.test_flow import create_persona, upload


def test_catalog_lists_every_style(client: TestClient) -> None:
    catalog = client.get("/api/formulas/catalog").json()
    assert len(catalog["article_types"]) == 11
    tutorial = next(t for t in catalog["article_types"] if t["id"] == "tutorial")
    assert tutorial["bodies"][0] == "progressive_build"
    assert {o["group"] for o in catalog["openers"]} == {"Joke", "Story", "Bold", "Serious"}
    assert all(o["summary"] for part in ("openers", "bodies", "closers") for o in catalog[part])


def test_saved_formulas_crud(client: TestClient) -> None:
    assert client.get("/api/formulas").json() == []
    body = {
        "name": "War story",
        "article_type": "case_study",
        "opener": "cold_open",
        "closer": "full_circle",
        "body_note": "Keep the dead ends.",
    }
    saved = client.post("/api/formulas", json=body)
    assert saved.status_code == 201, saved.text
    formula = saved.json()
    assert formula["body"] == "auto" and formula["body_note"] == "Keep the dead ends."
    assert formula["label"] == "Case study / build walkthrough · Cold open · Custom body · Full circle"

    # Names are unique, and a formula has to say something.
    assert client.post("/api/formulas", json={**body, "name": "war story"}).status_code == 409
    assert client.post("/api/formulas", json={"name": "Empty", "opener": "no_such_style"}).status_code == 422

    updated = client.put(f"/api/formulas/{formula['id']}", json={**body, "name": "War story v2", "body": "chronological"}).json()
    assert updated["name"] == "War story v2" and updated["body"] == "chronological"
    assert [f["name"] for f in client.get("/api/formulas").json()] == ["War story v2"]

    assert client.delete(f"/api/formulas/{formula['id']}").status_code == 204
    assert client.put(f"/api/formulas/{formula['id']}", json=body).status_code == 404
    assert client.get("/api/formulas").json() == []


def test_formula_drives_the_post(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM) -> None:
    pid = create_persona(client)["id"]
    upload(client, pid, sample_docx)
    client.post(f"/api/personas/{pid}/voice-profile")

    # The persona's default formula applies to a post that sets nothing; unknown styles are dropped.
    default = {"article_type": "listicle", "closer": "kicker", "opener": "gone"}
    out = client.patch(f"/api/personas/{pid}", json={"default_formula": default}).json()
    assert out["default_formula"]["article_type"] == "listicle" and out["default_formula"]["opener"] is None

    dials = {
        "revision_passes": 1,
        "opener": "joke_misdirection",
        "body": "countdown",
        "closer": "auto",
        "opener_note": "Mention the 3 a.m. dashboard.",
    }
    created = client.post("/api/projects", json={"prompt": "Pie charts", "dials": dials}).json()
    project = client.get(f"/api/projects/{created['project']['id']}").json()
    resolved = project["resolved_dials"]
    assert (resolved["article_type"], resolved["opener"], resolved["body"], resolved["closer"]) == (
        "listicle",
        "joke_misdirection",
        "countdown",
        "auto",
    )
    assert resolved["formula_label"] == "Top N countdown · Joke: the misdirection · Countdown"

    prompts = {c["task"]: c["prompt"] for c in fake_llm.calls if c.get("task") in ("post plan", "draft", "critique")}
    assert set(prompts) == {"post plan", "draft", "critique"}
    for prompt in prompts.values():
        assert "Article type: Top N countdown." in prompt and "Opener: Joke: the misdirection." in prompt
        assert "The author adds: Mention the 3 a.m. dashboard." in prompt
        assert "Closer: the author's usual way of ending" in prompt

    # Clearing the persona default.
    assert client.patch(f"/api/personas/{pid}", json={"default_formula": {}}).json()["default_formula"]["article_type"] is None
