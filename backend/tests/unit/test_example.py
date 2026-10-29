from __future__ import annotations

from fastapi.testclient import TestClient

from proseferno.services import Services


def test_example_is_a_finished_persona_you_can_look_at(client: TestClient) -> None:
    created = client.post("/api/example")
    assert created.status_code == 201
    persona = created.json()
    assert persona["is_example"] and not persona["is_active"]
    assert persona["own_samples"] == 3 and persona["voice_profile_version"] == 1

    profile = client.get(f"/api/personas/{persona['id']}/voice-profile").json()
    assert "Sample Author" in profile["markdown"] and "Voice Anchors" in profile["markdown"]

    project = client.get("/api/projects").json()[0]
    detail = client.get(f"/api/projects/{project['id']}").json()
    assert detail["status"] == "ready"
    assert len(detail["images"]) >= 3 and all(i["status"] == "ready" for i in detail["images"])
    assert all("Sample Author" in i["credit"] for i in detail["images"])


def test_example_is_created_once_and_removed_cleanly(client: TestClient, services: Services) -> None:
    first = client.post("/api/example").json()
    assert client.post("/api/example").json()["id"] == first["id"]
    assert len(client.get("/api/personas").json()) == 1

    assert client.delete("/api/example").status_code == 204
    assert client.get("/api/personas").json() == []
    assert client.get("/api/projects").json() == []
    assert not any(services.storage.root.glob("projects/*/images/*"))


def test_a_real_persona_takes_over_from_the_example(client: TestClient) -> None:
    client.post("/api/example")
    mine = client.post("/api/personas", json={"name": "Me"}).json()
    assert mine["is_active"]
    personas = {p["name"]: p for p in client.get("/api/personas").json()}
    assert personas["Sample Author"]["is_active"] is False

    # Removing the example leaves the real persona on.
    client.delete("/api/example")
    assert [p["is_active"] for p in client.get("/api/personas").json()] == [True]
