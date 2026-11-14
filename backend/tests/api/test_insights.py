"""The persona Insights page: the Claude digest and the charts measured from samples and posts."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from proseferno import demo


def _persona(client: TestClient) -> int:
    return int(client.post("/api/personas", json={"name": "Me"}).json()["id"])


def _with_profile(client: TestClient) -> int:
    pid = _persona(client)
    client.post(f"/api/personas/{pid}/samples/import-sample-writing")
    job = client.post(f"/api/personas/{pid}/voice-profile").json()
    assert client.get(f"/api/jobs/{job['id']}").json()["status"] == "succeeded"
    return pid


def _insights(client: TestClient, pid: int) -> dict[str, Any]:
    response = client.get(f"/api/personas/{pid}/insights")
    assert response.status_code == 200
    return dict(response.json())


def test_empty_persona_has_empty_insights(client: TestClient) -> None:
    pid = _persona(client)
    data = _insights(client, pid)
    assert data["digest"] is None
    assert data["fingerprint"] is None
    assert data["openers"] == [] and data["phrases"] == []
    assert data["formula"] == {"posts": 0, "nodes": [], "links": []}
    assert data["track_record"]["posts"] == 0
    assert data["overview"]["own_samples"] == 0
    assert client.get("/api/personas/999/insights").status_code == 404


def test_refresh_needs_a_voice_profile(client: TestClient) -> None:
    pid = _persona(client)
    response = client.post(f"/api/personas/{pid}/insights/refresh")
    assert response.status_code == 422
    assert "voice profile" in response.json()["detail"]


def test_charts_work_before_a_voice_profile(client: TestClient) -> None:
    pid = _persona(client)
    client.post(f"/api/personas/{pid}/samples/import-sample-writing")
    data = _insights(client, pid)
    assert data["digest"] is None
    assert data["overview"]["own_samples"] == 3 and data["overview"]["own_words"] > 0
    assert data["fingerprint"]["reference_kind"] == "typical"
    assert {row["key"] for row in data["fingerprint"]["rows"]} >= {"avg_sentence_words", "flesch_reading_ease"}
    assert sum(item["count"] for item in data["openers"]) == 3
    # Every phrase is counted by the posts that really use it.
    assert data["phrases"] and all(1 <= item["count"] <= 3 for item in data["phrases"])


def test_voice_profile_builds_the_digest(client: TestClient) -> None:
    pid = _with_profile(client)
    data = _insights(client, pid)
    digest = data["digest"]
    assert digest["headline"] and digest["version"] == 1 and digest["stale"] is False
    assert len(digest["tone"]) >= 3 and digest["steer_clear"]
    # Code counts Claude's sentence labels: shares add up and match the counts.
    mix = digest["voice_mix"]
    assert mix[0]["name"] == "Chatty"
    assert sum(m["count"] for m in mix) == digest["sentences_labeled"] == digest["sentences_sampled"] > 10
    assert abs(sum(m["share"] for m in mix) - 100) < 0.5
    # Only phrases that really occur in the author's writing survive.
    assert "Not a real phrase" not in digest["signature_phrases"]
    assert "Everyone peeks" in digest["signature_phrases"]
    assert data["overview"]["voice_profile_version"] == 1


def test_posts_feed_the_formula_flow_and_track_record(client: TestClient) -> None:
    pid = _with_profile(client)
    project = client.post("/api/projects", json={"prompt": "Why pie charts are lame"}).json()["project"]
    data = _insights(client, pid)
    flow = data["formula"]
    assert flow["posts"] == 1
    assert {n["stage"] for n in flow["nodes"]} == {"article_type", "opener", "body", "closer"}
    assert len(flow["links"]) == 3 and all(link["value"] == 1 for link in flow["links"])
    track = data["track_record"]
    assert track["posts"] == 1 and track["words"] > 0 and track["images"] >= 1
    assert track["stages"] == [{"id": "draft", "label": "draft", "count": 1}]
    point = track["points"][0]
    assert point["project_id"] == project["id"] and point["voice_match"] is not None and point["critique"] == 8


def test_influences_become_the_fingerprint_reference(client: TestClient, sample_docx: bytes) -> None:
    pid = _persona(client)
    client.post(f"/api/personas/{pid}/samples/import-sample-writing")
    files = {"files": ("influence.docx", sample_docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    assert client.post(f"/api/personas/{pid}/samples", files=files, data={"kind": "influence"}).status_code < 300
    fingerprint = _insights(client, pid)["fingerprint"]
    assert fingerprint["reference_kind"] == "influences"
    assert fingerprint["reference_label"] == "Writers you read"


def test_edited_version_shows_the_older_digest_until_refreshed(client: TestClient) -> None:
    pid = _with_profile(client)
    current = client.get(f"/api/personas/{pid}/voice-profile").json()
    client.put(f"/api/personas/{pid}/voice-profile", json={"markdown": current["markdown"] + "\nOne more rule.", "label": ""})
    digest = _insights(client, pid)["digest"]
    assert digest["version"] == 1 and digest["stale"] is True

    job = client.post(f"/api/personas/{pid}/insights/refresh").json()
    assert job["kind"] == "voice_insights"
    assert client.get(f"/api/jobs/{job['id']}").json()["status"] == "succeeded"
    digest = _insights(client, pid)["digest"]
    assert digest["version"] == 2 and digest["stale"] is False
    # The insights job never shows as the persona's voice profile job.
    assert client.get(f"/api/personas/{pid}").json()["active_job_id"] is None


def test_a_failed_digest_never_fails_the_voice_profile(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(prompt: str) -> dict[str, Any]:
        raise RuntimeError("no digest today")

    monkeypatch.setattr(demo, "_voice_insights_payload", broken)
    pid = _with_profile(client)
    assert client.get(f"/api/personas/{pid}/voice-profile").status_code == 200
    assert _insights(client, pid)["digest"] is None
