"""Building a voice with no writing of your own: archetypes, a surprise, named writers, an interview."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from inferno_ghostwriter.voice import sources


def _persona(client: TestClient) -> int:
    return int(client.post("/api/personas", json={"name": "Fresh Start"}).json()["id"])


def _generate(client: TestClient, persona_id: int) -> dict:  # type: ignore[type-arg]
    job = client.post(f"/api/personas/{persona_id}/voice-profile")
    assert job.status_code == 202, job.text
    done = client.get(f"/api/jobs/{job.json()['id']}").json()
    assert done["status"] == "succeeded", done
    return client.get(f"/api/personas/{persona_id}/voice-profile").json()  # type: ignore[no-any-return]


def test_catalogs_are_served(client: TestClient) -> None:
    archetypes = client.get("/api/archetypes").json()
    assert len(archetypes) >= 10
    assert all({"id", "name", "tagline", "preview", "dials"} <= a.keys() for a in archetypes)
    assert len({a["id"] for a in archetypes}) == len(archetypes)
    questions = client.get("/api/voice-interview").json()
    assert 5 <= len(questions) <= 8


def test_every_archetype_has_valid_dials() -> None:
    for archetype in sources.archetypes():
        assert set(archetype["dials"]) == set(sources.DIAL_KEYS)
        assert all(0 <= v <= 10 for v in archetype["dials"].values())


def test_surprise_is_reproducible_and_varied() -> None:
    assert sources.random_spec(7) == sources.random_spec(7)
    assert {sources.random_spec(i)["archetype"] for i in range(20)} != {sources.random_spec(0)["archetype"]}
    spec = sources.random_spec(3)
    assert spec["archetype"] != spec["secondary"]


def test_no_voice_and_no_samples_still_explains_what_to_do(client: TestClient) -> None:
    resp = client.post(f"/api/personas/{_persona(client)}/voice-profile")
    assert resp.status_code == 422
    assert "pick a voice" in resp.json()["detail"]


def test_archetype_persona_writes_without_any_samples(client: TestClient) -> None:
    pid = _persona(client)
    persona = client.put(
        f"/api/personas/{pid}/voice-source", json={"source": "archetype", "spec": {"archetype": "dry_wit_engineer"}}
    ).json()
    assert persona["source"] == "archetype" and persona["own_samples"] == 0
    assert persona["default_humor"] == 8  # the archetype's dials become the persona's defaults

    profile = _generate(client, pid)
    assert profile["baseline_stylometrics"] == {}
    assert client.get(f"/api/personas/{pid}").json()["voice_profile_version"] == 1
    versions = client.get(f"/api/personas/{pid}").json()["voice_profile_versions"]
    assert versions[0]["label"].startswith("Archetype: ")

    created = client.post("/api/projects", json={"prompt": "Why pie charts are lame"})
    assert created.status_code in (200, 201, 202), created.text
    assert client.get(f"/api/projects/{created.json()['project']['id']}").json()["status"] == "ready"


def test_synthesis_gets_the_brief_and_the_no_posts_note(client: TestClient, services) -> None:  # type: ignore[no-untyped-def]
    pid = _persona(client)
    client.put(f"/api/personas/{pid}/voice-source", json={"source": "archetype", "spec": {"archetype": "friendly_explainer"}})
    _generate(client, pid)
    prompt = next(c["prompt"] for c in services.llm.calls if c.get("task") == "voice profile synthesis")
    assert "The Friendly Explainer" in prompt
    assert "has no posts of their own yet" in prompt


def test_blend_researches_once_and_keeps_the_sources(client: TestClient, services) -> None:  # type: ignore[no-untyped-def]
    pid = _persona(client)
    spec = {"writers": [{"name": "Writer One", "weight": 8}, {"name": "Writer Two", "weight": 3}], "topics": "data science"}
    persona = client.put(f"/api/personas/{pid}/voice-source", json={"source": "blend", "spec": spec}).json()
    assert persona["source_spec"]["writers"][0]["name"] == "Writer One"

    profile = _generate(client, pid)
    assert "Writers studied" in (profile["best_practices"] or "")
    assert "researched" not in client.get(f"/api/personas/{pid}").json()["source_spec"]

    _generate(client, pid)
    style_calls = [c for c in services.llm.calls if c["kind"] == "research" and c["prompt"].startswith("Style research:")]
    assert len(style_calls) == 1  # the second profile reused the stored research
    assert "Writer One [8]" in style_calls[0]["prompt"]


def test_interview_answers_become_the_brief(client: TestClient, services) -> None:  # type: ignore[no-untyped-def]
    pid = _persona(client)
    questions = client.get("/api/voice-interview").json()
    answers = [{"id": questions[0]["id"], "answer": "Analysts who are drowning in dashboards."}, {"id": "bogus", "answer": "x"}]
    client.put(f"/api/personas/{pid}/voice-source", json={"source": "interview", "spec": {"answers": answers}})
    _generate(client, pid)
    prompt = next(c["prompt"] for c in services.llm.calls if c.get("task") == "voice profile synthesis")
    assert "drowning in dashboards" in prompt


def test_surprise_source_round_trips(client: TestClient) -> None:
    pid = _persona(client)
    surprise = client.get("/api/voice-surprise", params={"seed": 5}).json()
    assert surprise["archetype"]["id"] != surprise["secondary"]["id"]
    persona = client.put(f"/api/personas/{pid}/voice-source", json={"source": "random", "spec": surprise["spec"]}).json()
    assert persona["source"] == "random"
    _generate(client, pid)


@pytest.mark.parametrize(
    ("source", "spec"),
    [
        ("archetype", {"archetype": "nope"}),
        ("blend", {"writers": []}),
        ("interview", {"answers": [{"id": "audience", "answer": "   "}]}),
    ],
)
def test_bad_choices_are_rejected(client: TestClient, source: str, spec: dict) -> None:  # type: ignore[type-arg]
    resp = client.put(f"/api/personas/{_persona(client)}/voice-source", json={"source": source, "spec": spec})
    assert resp.status_code == 422


def test_writers_are_cleaned() -> None:
    cleaned = sources.clean_writers(
        [
            {"name": " A ", "weight": 99},
            {"name": "a"},
            {"name": ""},
            {"name": "B", "weight": 0},
            {"name": "C"},
            {"name": "D"},
            {"name": "E"},
        ]
    )
    assert [w["name"] for w in cleaned] == ["A", "B", "C", "D"]
    assert [w["weight"] for w in cleaned[:2]] == [10, 1]


def test_clearing_the_source_goes_back_to_samples(client: TestClient) -> None:
    pid = _persona(client)
    client.put(f"/api/personas/{pid}/voice-source", json={"source": "archetype", "spec": {"archetype": "deep_diver"}})
    assert client.delete(f"/api/personas/{pid}/voice-source").json()["source"] == "samples"
    assert client.post(f"/api/personas/{pid}/voice-profile").status_code == 422


def test_pasted_text_becomes_a_sample(client: TestClient) -> None:
    pid = _persona(client)
    text = "I like to explain things plainly. " * 20
    added = client.post(f"/api/personas/{pid}/samples/text", json={"text": text, "title": "My note"})
    assert added.status_code == 201 and added.json()["kind"] == "own"
    too_short = client.post(f"/api/personas/{pid}/samples/text", json={"text": "hi"})
    assert too_short.status_code == 422


def test_own_posts_and_a_chosen_voice_combine(client: TestClient) -> None:
    pid = _persona(client)
    client.post(f"/api/personas/{pid}/samples/import-sample-writing")
    client.put(f"/api/personas/{pid}/voice-source", json={"source": "archetype", "spec": {"archetype": "deep_diver"}})
    profile = _generate(client, pid)
    assert profile["baseline_stylometrics"]  # measured from the posts as before
