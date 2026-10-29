"""What a brand-new user with no files and no data sees: every empty case must be clean and explain itself."""

from __future__ import annotations

from fastapi.testclient import TestClient

from proseferno.config import Settings
from proseferno.main import create_app
from proseferno.services import Services


def test_every_list_is_empty(client: TestClient) -> None:
    for path in ("/api/personas", "/api/projects"):
        assert client.get(path).json() == []
    seed = client.get("/api/seed-samples").json()
    assert seed["available"] is False
    assert seed["files"] == []


def test_actions_without_data_explain_what_to_do(client: TestClient) -> None:
    no_persona = client.post("/api/projects", json={"prompt": "Anything at all"})
    assert no_persona.status_code == 422
    assert "persona" in no_persona.json()["detail"].lower()

    persona = client.post("/api/personas", json={"name": "Me"}).json()
    no_samples = client.post(f"/api/personas/{persona['id']}/voice-profile")
    assert no_samples.status_code == 422
    assert "sample" in no_samples.json()["detail"].lower()

    no_profile = client.post("/api/projects", json={"prompt": "Anything at all"})
    assert no_profile.status_code == 422
    assert "voice profile" in no_profile.json()["detail"]

    assert client.get(f"/api/personas/{persona['id']}/voice-profile").status_code == 404


def test_first_persona_is_on(client: TestClient) -> None:
    assert client.post("/api/personas", json={"name": "Me"}).json()["is_active"] is True


def test_sample_posts_get_a_new_user_to_a_post_without_any_files(client: TestClient) -> None:
    listing = client.get("/api/sample-writing").json()
    assert len(listing["files"]) == 3

    persona = client.post("/api/personas", json={"name": "Me"}).json()
    added = client.post(f"/api/personas/{persona['id']}/samples/import-sample-writing").json()
    assert len(added["added"]) == 3 and added["errors"] == []
    # Importing twice adds nothing new.
    assert client.post(f"/api/personas/{persona['id']}/samples/import-sample-writing").json()["added"] == []

    job = client.post(f"/api/personas/{persona['id']}/voice-profile").json()
    assert client.get(f"/api/jobs/{job['id']}").json()["status"] == "succeeded"
    created = client.post("/api/projects", json={"prompt": "Why pie charts are lame"}).json()
    assert client.get(f"/api/projects/{created['project']['id']}").json()["status"] == "ready"


def test_demo_starts_on_the_example(tmp_path_factory, settings: Settings, services: Services) -> None:  # type: ignore[no-untyped-def]
    settings.demo = True
    with TestClient(create_app(settings, services)) as demo_client:
        personas = demo_client.get("/api/personas").json()
        assert [p["name"] for p in personas] == ["Sample Author"]
        assert personas[0]["is_example"] and personas[0]["is_active"]
        project = demo_client.get("/api/projects").json()[0]
        assert project["status"] == "ready"


def test_demo_seed_can_be_turned_off(settings: Settings, services: Services) -> None:
    settings.demo = True
    settings.demo_seed = False
    with TestClient(create_app(settings, services)) as demo_client:
        assert demo_client.get("/api/personas").json() == []
