"""The optional interview before writing, and the detector models' settings."""

from __future__ import annotations

from fastapi.testclient import TestClient

from inferno_ghostwriter.demo import DEMO_INTERVIEW, FakeLLM
from tests.api.test_flow import create_persona, upload


def ready_persona(client: TestClient, sample_docx: bytes) -> int:
    persona = create_persona(client)
    upload(client, persona["id"], sample_docx)
    assert client.post(f"/api/personas/{persona['id']}/voice-profile").json()["status"] == "succeeded"
    return int(persona["id"])


def test_without_the_interview_nothing_changes(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM) -> None:
    ready_persona(client, sample_docx)
    created = client.post("/api/projects", json={"prompt": "Why pie charts are lame"}).json()
    project = client.get(f"/api/projects/{created['project']['id']}").json()
    assert project["status"] == "ready" and project["interview"] == []
    assert "interview" not in fake_llm.tasks()
    plan_call = next(c for c in fake_llm.calls if c["task"] == "post plan")
    assert "<author_material>" not in plan_call["prompt"]


def test_interview_asks_then_writes_with_the_answers(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM) -> None:
    pid = ready_persona(client, sample_docx)
    assert client.get(f"/api/personas/{pid}").json()["default_interview"] is False
    assert client.patch(f"/api/personas/{pid}", json={"default_interview": True}).json()["default_interview"] is True

    created = client.post("/api/projects", json={"prompt": "Why pie charts are lame", "interview": True}).json()
    project_id = created["project"]["id"]
    assert client.get(f"/api/jobs/{created['job_id']}").json()["kind"] == "interview"
    project = client.get(f"/api/projects/{project_id}").json()
    # Questions are ready and nothing has been written yet.
    assert [q["question"] for q in project["interview"]] == DEMO_INTERVIEW and project["markdown"] == ""
    assert "post plan" not in fake_llm.tasks()

    answers = [{"question": q["question"], "answer": ""} for q in project["interview"]]
    answers[0]["answer"] = "A 3D exploding pie in a board deck, 2019."
    saved = client.put(f"/api/projects/{project_id}/interview", json={"answers": answers}).json()
    assert saved["interview"][0]["answer"].startswith("A 3D exploding pie")

    job = client.post(f"/api/projects/{project_id}/generate", json={"interview": answers}).json()
    assert job["status"] == "succeeded", job
    project = client.get(f"/api/projects/{project_id}").json()
    assert project["status"] == "ready" and project["markdown"]
    for task in ("post plan", "draft"):
        call = next(c for c in fake_llm.calls if c["task"] == task)
        assert "A 3D exploding pie in a board deck" in call["prompt"]
        # A skipped question is not sent.
        assert DEMO_INTERVIEW[1] not in call["prompt"]
    critique = next(c for c in fake_llm.calls if c["task"] == "critique")
    assert "close to their wording" in critique["prompt"]

    # Ask again: new questions replace the old ones.
    again = client.post(f"/api/projects/{project_id}/interview").json()
    assert again["status"] == "succeeded"
    assert all(q["answer"] == "" for q in client.get(f"/api/projects/{project_id}").json()["interview"])


def test_humanize_a_passage(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM) -> None:
    ready_persona(client, sample_docx)
    created = client.post("/api/projects", json={"prompt": "Why pie charts are lame"}).json()
    project = client.get(f"/api/projects/{created['project']['id']}").json()
    passage = next(line for line in project["markdown"].splitlines() if line and not line.startswith(("#", "*", "{{")))
    response = client.post(
        f"/api/projects/{project['id']}/rewrite",
        json={"selection": passage, "instruction": "Stock closing line", "action": "humanize"},
    )
    # Either the rewrite was kept, or it read less like the author and nothing changed (a clear 422).
    assert response.status_code in (200, 422), response.text
    rewrite = next(c for c in fake_llm.calls if c["task"] == "passage humanize")
    assert "Make this passage read like the author wrote it" in rewrite["prompt"]


def test_detector_settings(client: TestClient) -> None:
    state = client.get("/api/detector").json()
    # The light check is built in, so detection works with no download.
    assert state["enabled"] and state["ready"] and state["selected"] == ["light"] and state["detail"]
    assert [m["id"] for m in state["models"]] == ["light", "curvature", "classifier"]
    assert [m["heavy"] for m in state["models"]] == [False, True, True]
    settings = client.get("/api/settings").json()
    assert settings["detector_models"] == ["light"] and settings["humanize_rounds"] == 1
    # Any mix can be selected; a trained model that is not set up yet is selected but cannot run.
    mixed = client.put("/api/settings", json={"detector_models": ["classifier", "light"]}).json()
    assert mixed["detector_models"] == ["light", "classifier"]
    assert client.get("/api/detector").json()["ready"] is False
    assert client.put("/api/settings", json={"detector_models": []}).json()["detector_models"] == []
    assert not client.get("/api/detector").json()["enabled"]
    assert client.put("/api/settings", json={"detector_models": ["nope"]}).status_code == 422
    client.put("/api/settings", json={"detector_models": ["light"]})
    assert client.put("/api/settings", json={"humanize_rounds": 2}).json()["humanize_rounds"] == 2
    assert client.put("/api/settings", json={"humanize_rounds": 5}).status_code == 422
