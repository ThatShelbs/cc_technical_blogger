"""Post stages, outcomes and persona evolution, end to end with a fake Claude."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from proseferno.db import Project
from proseferno.demo import FakeLLM
from proseferno.services import Services
from tests.api.test_flow import ready_post


def edit_heavily(client: TestClient, project: dict) -> dict:
    """Replace the first two paragraphs of prose, like an author reworking a draft."""
    paragraphs = [p for p in project["markdown"].split("\n\n") if len(p.split()) > 8 and not p.startswith(("#", "{{", "*"))]
    markdown = project["markdown"]
    for i, paragraph in enumerate(paragraphs[:2]):
        markdown = markdown.replace(paragraph, f"I rewrote paragraph {i} in my own words, shorter and with a concrete example first.")
    return client.patch(f"/api/projects/{project['id']}", json={"markdown": markdown, "learn": False}).json()


def calls(fake_llm: FakeLLM, task: str) -> list[dict]:
    return [c for c in fake_llm.calls if c["task"] == task]


def test_generation_records_the_baseline(client: TestClient, sample_docx: bytes, services: Services) -> None:
    project = ready_post(client, sample_docx)
    assert project["stage"] == "draft" and project["outcome"] is None
    assert project["has_baseline"] and project["edit_rate"] == 0
    with Session(services.engine) as session:
        row = session.get(Project, project["id"])
        assert row is not None and row.baseline_markdown == row.markdown
    edited = edit_heavily(client, project)
    assert edited["edit_rate"] > 0.02

    diff = client.get(f"/api/projects/{project['id']}/baseline-diff").json()
    ops = {s["op"] for s in diff["segments"]}
    assert ops == {"equal", "insert", "delete"}
    assert "".join(s["text"] for s in diff["segments"] if s["op"] != "delete").strip().startswith("# ")

    # A full regeneration resets the baseline to the new text.
    client.post(f"/api/projects/{project['id']}/generate")
    assert client.get(f"/api/projects/{project['id']}").json()["edit_rate"] == 0


def test_publish_too_early_proposes_and_applies_persona_changes(
    client: TestClient, sample_docx: bytes, fake_llm: FakeLLM, services: Services
) -> None:
    project = ready_post(client, sample_docx)
    persona_id = project["persona_id"]
    before = client.get(f"/api/personas/{persona_id}").json()
    edit_heavily(client, project)

    client.patch(f"/api/projects/{project['id']}", json={"stage": "ready"})
    assert not calls(fake_llm, "persona evolution")
    out = client.patch(f"/api/projects/{project['id']}", json={"stage": "published"}).json()
    assert out["stage"] == "published" and out["outcome"] == "too_early" and out["published_at"]
    [evolution] = out["evolutions"]
    assert evolution["kind"] == "edits" and evolution["state"] == "pending" and evolution["edit_rate"] > 0.02
    assert [i["target"] for i in evolution["items"]] == ["profile", "profile", "playbook"]
    prompt = calls(fake_llm, "persona evolution")[0]["prompt"]
    assert "GENERATED:" in prompt and "PUBLISHED:" in prompt and "I rewrote paragraph 0" in prompt
    assert client.get(f"/api/personas/{persona_id}").json()["pending_evolutions"] == 1

    # Publishing the same text again does not analyze twice.
    client.patch(f"/api/projects/{project['id']}", json={"stage": "ready"})
    client.patch(f"/api/projects/{project['id']}", json={"stage": "published"})
    assert len(calls(fake_llm, "persona evolution")) == 1

    # Apply two of the three: one profile change placed by an edit, one playbook entry.
    response = client.post(f"/api/evolutions/{evolution['id']}/apply", json={"item_ids": ["c1", "c3"]})
    assert response.status_code == 200, response.text
    persona = client.get(f"/api/personas/{persona_id}").json()
    assert persona["voice_profile_version"] == before["voice_profile_version"] + 1
    assert persona["voice_profile_label"].startswith("Evolved: ")
    assert persona["pending_evolutions"] == 0
    assert [e["text"] for e in persona["playbook"]] == ["End a section on a one-line aside when the point is already made."]
    profile = client.get(f"/api/personas/{persona_id}/voice-profile").json()["markdown"]
    assert "Lead with the concrete example, then the rule." in profile
    assert "Cut hedges" not in profile  # not chosen

    history = client.get(f"/api/personas/{persona_id}/evolution").json()
    applied = history["evolutions"][0]
    assert applied["state"] == "applied" and [i["applied"] for i in applied["items"]] == [True, False, True]
    assert len(history["edit_rates"]) == 1
    assert client.post(f"/api/evolutions/{evolution['id']}/apply", json={"item_ids": ["c2"]}).status_code == 422

    # The playbook and the approved change reach the writer and the next voice profile.
    fake_llm.calls.clear()
    client.post(f"/api/projects/{project['id']}/generate")
    system = "\n".join(block.text for block in calls(fake_llm, "post plan")[0]["system"])
    assert "What has landed with this author's readers" in system and "one-line aside" in system
    client.post(f"/api/personas/{persona_id}/voice-profile")
    synthesis = calls(fake_llm, "voice profile synthesis")[0]["prompt"]
    assert "Open each section with the concrete example" in synthesis and "one-line aside" in synthesis

    # Playbook entries can be forgotten.
    assert client.delete(f"/api/personas/{persona_id}/playbook", params={"index": 0}).json()["playbook"] == []


def test_unplaced_profile_change_becomes_a_rule(client: TestClient, sample_docx: bytes) -> None:
    project = ready_post(client, sample_docx)
    edit_heavily(client, project)
    evolution = client.patch(f"/api/projects/{project['id']}", json={"stage": "published"}).json()["evolutions"][0]
    client.post(f"/api/evolutions/{evolution['id']}/apply", json={"item_ids": ["c2"]})
    profile = client.get(f"/api/personas/{project['persona_id']}/voice-profile").json()["markdown"]
    assert "## Do / Don't\n\n- Cut hedges like 'it is worth noting'; say the thing." in profile


def test_barely_edited_post_needs_no_model_call(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM) -> None:
    project = ready_post(client, sample_docx)
    out = client.patch(f"/api/projects/{project['id']}", json={"stage": "published"}).json()
    [evolution] = out["evolutions"]
    assert evolution["state"] == "clean" and evolution["edit_rate"] == 0 and evolution["items"] == []
    assert not calls(fake_llm, "persona evolution")
    assert client.post(f"/api/evolutions/{evolution['id']}/dismiss").json()["state"] == "dismissed"


def test_outcomes_drive_secret_sauce(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM) -> None:
    project = ready_post(client, sample_docx)
    url = f"/api/projects/{project['id']}"
    client.patch(url, json={"stage": "published"})

    client.patch(url, json={"outcome": "small"})
    assert not calls(fake_llm, "secret sauce")

    out = client.patch(url, json={"outcome": "good"}).json()
    sauce = [e for e in out["evolutions"] if e["kind"] == "secret_sauce"]
    assert len(sauce) == 1 and sauce[0]["state"] == "pending" and sauce[0]["outcome"] == "good"
    prompt = calls(fake_llm, "secret sauce")[0]["prompt"]
    assert "good traction" in prompt and "Pie Charts Are Lame" in prompt

    # Going viral before the author applied it re-reads the post; the old proposal is replaced.
    out = client.patch(url, json={"outcome": "viral"}).json()
    sauce = [e for e in out["evolutions"] if e["kind"] == "secret_sauce"]
    assert len(sauce) == 1 and sauce[0]["outcome"] == "viral"
    assert len(calls(fake_llm, "secret sauce")) == 2

    client.post(f"/api/evolutions/{sauce[0]['id']}/apply", json={"item_ids": ["c1", "c2"]})
    persona = client.get(f"/api/personas/{project['persona_id']}").json()
    assert {e["outcome"] for e in persona["playbook"]} == {"viral"}
    assert persona["voice_profile_version"] == 1  # playbook only: no new voice profile version

    # Back to draft clears the outcome.
    out = client.patch(url, json={"stage": "draft"}).json()
    assert out["outcome"] is None and out["published_at"] is None


def test_project_list_shows_stage_and_outcome(client: TestClient, sample_docx: bytes) -> None:
    project = ready_post(client, sample_docx)
    client.patch(f"/api/projects/{project['id']}", json={"outcome": "viral"})
    [summary] = client.get("/api/projects").json()
    assert summary["stage"] == "published" and summary["outcome"] == "viral"
    assert client.patch(f"/api/projects/{project['id']}", json={"stage": "shipped"}).status_code == 422


def test_post_without_baseline_cannot_be_compared(client: TestClient, sample_docx: bytes, services: Services) -> None:
    project = ready_post(client, sample_docx)
    with Session(services.engine) as session:
        row = session.get(Project, project["id"])
        assert row is not None
        row.baseline_markdown = ""
        session.add(row)
        session.commit()
    out = client.patch(f"/api/projects/{project['id']}", json={"stage": "published"}).json()
    assert out["evolutions"] == [] and not out["has_baseline"] and out["edit_rate"] is None
    response = client.post(f"/api/projects/{project['id']}/evolutions", json={"kind": "edits"})
    assert response.status_code == 422 and "no generated text" in response.json()["detail"]
    assert client.get(f"/api/projects/{project['id']}/baseline-diff").status_code == 404
    # A secret-sauce read only needs the post.
    assert client.post(f"/api/projects/{project['id']}/evolutions", json={"kind": "secret_sauce"}).json()["state"] == "pending"
