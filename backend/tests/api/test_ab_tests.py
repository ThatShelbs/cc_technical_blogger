"""A/B Test Mode end to end with a fake Claude: two hidden posts, a blind choice, blending and adopting."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from proseferno.abtest.service import fail_interrupted
from proseferno.db import ABTest, Persona, PersonaEvolution, Project, ProjectImage, Sample
from proseferno.demo import FakeLLM
from proseferno.services import Services
from tests.api.test_flow import create_persona, ready_post, upload


def start(client: TestClient, sample_docx: bytes) -> tuple[dict, dict]:
    """A persona with a voice profile, and a new post written in A/B mode: (project, test)."""
    pid = create_persona(client)["id"]
    upload(client, pid, sample_docx)
    client.post(f"/api/personas/{pid}/voice-profile")
    created = client.post("/api/projects", json={"prompt": "Pie charts", "dials": {"revision_passes": 0}, "mode": "ab"})
    assert created.status_code == 201, created.text
    project = client.get(f"/api/projects/{created.json()['project']['id']}").json()
    return project, client.get(f"/api/ab-tests/{project['ab_test']['id']}").json()


def row(services: Services, test_id: int) -> ABTest:
    with Session(services.engine) as session:
        test = session.get(ABTest, test_id)
        assert test is not None
        return test


def side_of(services: Services, test_id: int, role: str) -> str:
    return "left" if row(services, test_id).left_role == role else "right"


def decide(client: TestClient, test_id: int, **body: object) -> dict:
    response = client.post(f"/api/ab-tests/{test_id}/decide", json=body)
    assert response.status_code == 202, response.text
    assert response.json()["status"] == "succeeded", response.json()
    return response.json()


def test_ab_mode_writes_two_hidden_posts_and_says_nothing_about_them(
    client: TestClient, sample_docx: bytes, fake_llm: FakeLLM, services: Services
) -> None:
    project, test = start(client, sample_docx)

    # The host has no post of its own yet, and the two variants are not in the list.
    assert project["markdown"] == "" and project["ab_test"]["status"] == "voting"
    listed = client.get("/api/projects").json()
    assert [p["id"] for p in listed] == [project["id"]] and listed[0]["ab_status"] == "voting"
    with Session(services.engine) as session:
        variants = {p.variant: p for p in session.exec(select(Project).where(Project.ab_test_id == test["id"]))}
        assert set(variants) == {"control", "challenger"}
        control, challenger = variants["control"].dials, variants["challenger"].dials
        assert control == {"revision_passes": 0}
        assert challenger["humor"] != 5 and challenger["revision_passes"] == 0 and "target_words" not in challenger

    # Blind: positions only, both posts complete with their images.
    assert test["status"] == "voting" and test["winner"] is None and test["tweaks"] == [] and test["adopted"] is None
    for side in ("left", "right"):
        post = test[side]
        assert post["side"] == side and post["markdown"].startswith("# ") and post["status"] == "ready"
        assert {i["status"] for i in post["images"]} == {"ready"} and post["images"][0]["slot_id"] == "hero"
        assert not {"dials", "role", "variant", "authenticity"} & set(post)

    # Only the challenger was written with the emphasis block and the moved dials.
    drafts = [c for c in fake_llm.calls if c["task"] == "draft"]
    assert len(drafts) == 2
    emphasized = [c for c in drafts if "# Emphasis for this post" in str(c["system"])]
    assert len(emphasized) == 1
    plain = next(c for c in drafts if c is not emphasized[0])
    assert "Humor level 5/10" in plain["prompt"] and "Humor level 5/10" not in emphasized[0]["prompt"]
    assert "About 1500 words" in plain["prompt"] and "About 1500 words" in emphasized[0]["prompt"]

    # No refining while the test is open.
    for path, body in (("generate", None), ("tweak", {"feedback": "Shorter"}), ("rewrite", {"selection": "x"})):
        assert client.post(f"/api/projects/{project['id']}/{path}", json=body).status_code == 409
    assert client.post(f"/api/projects/{project['id']}/ab-tests").status_code == 409


def test_control_wins_and_nothing_changes(client: TestClient, sample_docx: bytes, services: Services) -> None:
    project, test = start(client, sample_docx)
    side = side_of(services, test["id"], "control")
    winner_text = test[side]["markdown"]
    winner_images = [i["id"] for i in test[side]["images"]]
    decide(client, test["id"], winner=side)

    after = client.get(f"/api/projects/{project['id']}").json()
    assert after["markdown"] == winner_text and after["status"] == "ready" and after["edit_rate"] == 0
    assert [i["id"] for i in after["images"]] == winner_images
    assert all(client.get(i["url"]).status_code == 200 for i in after["images"])
    assert after["ab_test"] is None  # nothing to adopt: the settings held up
    assert after["dials"] == {"revision_passes": 0}

    out = client.get(f"/api/ab-tests/{test['id']}").json()
    assert out["status"] == "decided" and out["winner"] == "control" and out["winner_side"] == side
    assert out["left"] is None and out["adopted"] == [] and len(out["tweaks"]) > 10
    assert not any(t["suggested"] for t in out["tweaks"])

    # Both variants are gone, rows and files.
    with Session(services.engine) as session:
        assert session.exec(select(Project).where(Project.ab_test_id == test["id"])).all() == []
        assert {i.project_id for i in session.exec(select(ProjectImage))} == {project["id"]}
    assert sorted(p.name for p in (services.storage.root / "projects").iterdir()) == [str(project["id"])]
    # The post is a normal post again.
    assert client.post(f"/api/projects/{project['id']}/tweak", json={"feedback": "Add a joke"}).status_code == 202


def test_challenger_wins_and_the_persona_adopts_it(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM, services: Services) -> None:
    project, test = start(client, sample_docx)
    side = side_of(services, test["id"], "challenger")
    decide(client, test["id"], winner=side)

    after = client.get(f"/api/projects/{project['id']}").json()
    assert after["ab_test"] == {"id": test["id"], "status": "decided", "error": None}
    assert after["dials"]["humor"] != 5  # the post keeps the settings it was written with
    out = client.get(f"/api/ab-tests/{test['id']}").json()
    assert out["winner"] == "challenger" and all(t["suggested"] for t in out["tweaks"])
    by_label = {t["label"]: t for t in out["tweaks"] if t["group"] == "Settings"}
    assert by_label["Humor"]["before"] == "5/10" and by_label["Humor"]["after"] != "5/10"

    stored = {t["id"]: t for t in row(services, test["id"]).tweaks}
    humor = next(t for t in stored.values() if t.get("field") == "default_humor")
    opener = next((t for t in stored.values() if t.get("field") == "opener"), None)
    lean = next(t for t in stored.values() if t["label"] == "Lean most on")
    title = next(t for t in stored.values() if t["group"] == "Title")
    style = next(t for t in stored.values() if t.get("field") == "visual_style")
    chosen = [t["id"] for t in (humor, opener, lean, title, style) if t]

    adopted = client.post(f"/api/ab-tests/{test['id']}/adopt", json={"tweak_ids": chosen})
    assert adopted.status_code == 200, adopted.text
    body = adopted.json()
    assert body["ab_test"]["adopted"] == chosen and body["job"]["kind"] == "apply_evolution" and body["job"]["status"] == "succeeded"

    with Session(services.engine) as session:
        persona = session.get(Persona, project["persona_id"])
        assert persona is not None
        assert persona.default_humor == humor["value"] and persona.visual_style == style["value"]
        assert persona.default_storytelling == 5  # not chosen, not adopted
        if opener:
            assert persona.default_formula == {"opener": opener["value"]}
        sample = session.get(Sample, lean["sample_id"])
        assert sample is not None and sample.weight == 1.5
        evolution = session.exec(select(PersonaEvolution).where(PersonaEvolution.kind == "ab_test")).one()
        assert evolution.state == "applied" and evolution.project_id == project["id"]
        assert [i["id"] for i in evolution.items] == [title["id"]] and evolution.items[0]["applied"]
    profile = client.get(f"/api/personas/{project['persona_id']}/voice-profile").json()
    assert profile["version"] == 2 and title["change"] in profile["markdown"]

    assert client.get(f"/api/projects/{project['id']}").json()["ab_test"] is None
    assert client.post(f"/api/ab-tests/{test['id']}/adopt", json={"tweak_ids": []}).status_code == 409
    # The next post starts from the adopted settings.
    fake_llm.calls.clear()
    client.post("/api/projects", json={"prompt": "Bar charts", "dials": {"revision_passes": 0}})
    draft = next(c for c in fake_llm.calls if c["task"] == "draft")
    assert f"Humor level {humor['value']}/10" in draft["prompt"]


def test_keeping_my_settings_closes_the_question(client: TestClient, sample_docx: bytes, services: Services) -> None:
    project, test = start(client, sample_docx)
    decide(client, test["id"], winner=side_of(services, test["id"], "challenger"))
    out = client.post(f"/api/ab-tests/{test['id']}/adopt", json={"tweak_ids": []}).json()
    assert out["job"] is None and out["ab_test"]["adopted"] == []
    with Session(services.engine) as session:
        persona = session.get(Persona, project["persona_id"])
        assert persona is not None and persona.default_humor == 5 and persona.default_formula == {}
    assert client.get(f"/api/projects/{project['id']}").json()["ab_test"] is None


def test_blend_takes_parts_of_the_other_post_and_a_note(
    client: TestClient, sample_docx: bytes, fake_llm: FakeLLM, services: Services
) -> None:
    project, test = start(client, sample_docx)
    side = side_of(services, test["id"], "control")
    loser = "right" if side == "left" else "left"
    their = {i["slot_id"]: i for i in test[loser]["images"]}
    mine = {i["slot_id"]: i for i in test[side]["images"]}
    fake_llm.calls.clear()

    result = decide(
        client,
        test["id"],
        winner=side,
        take=["title", "opener", "closer", "hero", "meme", "image_style"],
        notes="Take the other version's joke about circles.",
    )
    assert result["result"]["notes_error"] is None

    after = client.get(f"/api/projects/{project['id']}").json()
    images = {i["slot_id"]: i for i in after["images"]}
    # The hero and the meme are the other post's own images; the opener's image came along under a new slot.
    assert images["hero"]["id"] == their["hero"]["id"] and images["meme"]["id"] == their["meme"]["id"]
    moved = [i for i in after["images"] if i["id"] in {v["id"] for v in their.values()} and i["slot_id"] not in ("hero", "meme")]
    assert moved and all(f"{{{{image:{i['slot_id']}}}}}" in after["markdown"] for i in after["images"])
    assert all(client.get(i["url"]).status_code == 200 for i in after["images"])
    assert after["images"][0]["slot_id"] == "hero" and after["images"][-1]["slot_id"] == "meme"
    assert {s["slot_id"] for s in after["plan"]["image_slots"]} == set(images)
    # The winner's remaining images were redrawn in the other post's style.
    kept = [i for i in after["images"] if i["id"] in {v["id"] for v in mine.values()}]
    assert kept and all(len(i["history"]) == 2 for i in kept)
    assert after["brand_kit"]["style"] and after["edit_rate"] == 0 and after["revisions"] == []

    # The note ran as a tweak that could see the other post, and taught the persona nothing.
    tweak = next(c for c in fake_llm.calls if c["task"] == "post tweak")
    assert "<other_version>" in tweak["prompt"] and "joke about circles" in tweak["prompt"]
    with Session(services.engine) as session:
        persona = session.get(Persona, project["persona_id"])
        assert persona is not None and persona.edit_lessons == []

    # Control won, but parts of the challenger were kept: only the matching tweaks are suggested.
    out = client.get(f"/api/ab-tests/{test['id']}").json()
    assert out["taken"] == ["title", "opener", "closer", "hero", "meme", "image_style"]
    suggested = {t["group"] for t in out["tweaks"] if t["suggested"]}
    assert {"Title", "Images"} <= suggested <= {"Title", "Images", "Formula"}
    assert after["ab_test"]["status"] == "decided"


def test_discard_keeps_the_existing_post(client: TestClient, sample_docx: bytes, services: Services) -> None:
    project = ready_post(client, sample_docx)
    started = client.post(f"/api/projects/{project['id']}/ab-tests", json={"dials": {"revision_passes": 0, "humor": 8}})
    assert started.status_code == 202 and started.json()["kind"] == "ab_generate"
    during = client.get(f"/api/projects/{project['id']}").json()
    assert during["markdown"] == project["markdown"] and during["ab_test"]["status"] == "voting"
    test_id = during["ab_test"]["id"]

    assert client.delete(f"/api/ab-tests/{test_id}").status_code == 204
    after = client.get(f"/api/projects/{project['id']}").json()
    assert after["ab_test"] is None and after["markdown"] == project["markdown"]
    assert [i["id"] for i in after["images"]] == [i["id"] for i in project["images"]]
    assert client.get(f"/api/ab-tests/{test_id}").json()["status"] == "discarded"
    with Session(services.engine) as session:
        assert len(session.exec(select(Project)).all()) == 1
    assert client.delete(f"/api/ab-tests/{test_id}").status_code == 409
    assert client.post(f"/api/ab-tests/{test_id}/decide", json={"winner": "left"}).status_code == 409


def test_a_failed_post_can_be_retried(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM, services: Services) -> None:
    project = ready_post(client, sample_docx)
    original = fake_llm.text
    seen = {"drafts": 0}

    async def flaky(**kwargs):  # type: ignore[no-untyped-def]
        if kwargs.get("task") == "draft":
            seen["drafts"] += 1
            if seen["drafts"] == 2:
                raise RuntimeError("The model was overloaded.")
        return await original(**kwargs)

    fake_llm.text = flaky  # type: ignore[method-assign]
    job = client.post(f"/api/projects/{project['id']}/ab-tests").json()
    assert job["status"] == "failed"
    during = client.get(f"/api/projects/{project['id']}").json()
    assert during["ab_test"]["status"] == "error" and "overloaded" in during["ab_test"]["error"]
    test_id = during["ab_test"]["id"]
    assert client.post(f"/api/ab-tests/{test_id}/decide", json={"winner": "left"}).status_code == 409

    retried = client.post(f"/api/ab-tests/{test_id}/retry").json()
    assert retried["status"] == "succeeded" and seen["drafts"] == 3  # only the failed post was written again
    test = client.get(f"/api/ab-tests/{test_id}").json()
    assert test["status"] == "voting" and test["left"]["status"] == test["right"]["status"] == "ready"
    assert client.post(f"/api/ab-tests/{test_id}/retry").status_code == 409


def test_restart_and_deletion_leave_nothing_behind(client: TestClient, sample_docx: bytes, services: Services) -> None:
    project, test = start(client, sample_docx)
    with Session(services.engine) as session:
        stuck = session.get(ABTest, test["id"])
        assert stuck is not None
        stuck.status = "generating"
        session.add(stuck)
        session.commit()
    assert fail_interrupted(services.engine) == 1
    assert client.get(f"/api/ab-tests/{test['id']}").json()["status"] == "error"

    # Insights and the post list never count the hidden posts.
    insights = client.get(f"/api/personas/{project['persona_id']}/insights")
    assert insights.status_code == 200

    assert client.delete(f"/api/projects/{project['id']}").status_code == 204
    with Session(services.engine) as session:
        assert session.exec(select(Project)).all() == [] and session.exec(select(ABTest)).all() == []
        assert session.exec(select(ProjectImage)).all() == []
    assert list((services.storage.root / "projects").iterdir()) == []

    _, second = start_again(client)
    assert client.delete(f"/api/personas/{project['persona_id']}").status_code == 204
    with Session(services.engine) as session:
        assert session.exec(select(Project)).all() == [] and session.exec(select(ABTest)).all() == []
    assert second["status"] == "voting"


def start_again(client: TestClient) -> tuple[dict, dict]:
    created = client.post("/api/projects", json={"prompt": "Bar charts", "dials": {"revision_passes": 0}, "mode": "ab"}).json()
    project = client.get(f"/api/projects/{created['project']['id']}").json()
    return project, client.get(f"/api/ab-tests/{project['ab_test']['id']}").json()
