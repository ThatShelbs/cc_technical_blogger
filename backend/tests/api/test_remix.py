"""Redraw that thinks (critique + twist), the opener's full meme bank and images that build on each other."""

from __future__ import annotations

from fastapi.testclient import TestClient

from inferno_ghostwriter.demo import FakeLLM
from tests.api.test_flow import create_persona, upload


def make_post(client: TestClient, sample_docx: bytes, **dials: object) -> dict:
    pid = create_persona(client)["id"]
    upload(client, pid, sample_docx)
    client.post(f"/api/personas/{pid}/voice-profile")
    created = client.post("/api/projects", json={"prompt": "Pie charts", "dials": {"revision_passes": 0, **dials}}).json()
    return client.get(f"/api/projects/{created['project']['id']}").json()


def images(client: TestClient, project: dict) -> dict[str, dict]:
    return {i["slot_id"]: i for i in client.get(f"/api/projects/{project['id']}").json()["images"]}


def test_every_redraw_critiques_the_image_and_tries_a_twist(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM) -> None:
    project = make_post(client, sample_docx)
    chart = images(client, project)["img3"]
    assert chart["remix"] is None

    fake_llm.calls.clear()
    assert client.post(f"/api/images/{chart['id']}/redraw", json={}).json()["status"] == "succeeded"
    assert "image improvement plan" in fake_llm.tasks()
    remix = images(client, project)["img3"]["remix"]
    assert remix["brainstormed"] and remix["weakness"] and remix["improvements"]
    # A chart has colors to vary and nothing else.
    assert [t["dimension"] for t in remix["tweaks"]] == ["palette"]
    draw = next(c for c in fake_llm.calls if c["task"] == "chart image design")
    assert "Biggest weakness to fix" in draw["prompt"]

    diagram = images(client, project)["img2"]
    assert (
        client.post(f"/api/images/{diagram['id']}/redraw", json={"tweaks": {"palette": "viridis", "staging": "isometric"}}).json()["status"]
        == "succeeded"
    )
    ids = {(t["dimension"], t["id"]) for t in images(client, project)["img2"]["remix"]["tweaks"]}
    assert ids == {("palette", "viridis"), ("staging", "isometric")}

    assert client.post(f"/api/images/{diagram['id']}/redraw", json={"tweaks": {"palette": "nope"}}).status_code == 422
    options = client.get("/api/remix-options").json()
    assert [d["id"] for d in options] == ["palette", "cast", "staging", "medium"]
    assert any(o["id"] == "dogs" for d in options if d["id"] == "cast" for o in d["options"])


def test_pitched_ideas_and_redraw_all_skip_the_brainstorm(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM) -> None:
    project = make_post(client, sample_docx, opening_style="cheat_sheet")
    hero = images(client, project)["hero"]
    fake_llm.calls.clear()
    assert client.post(f"/api/images/{hero['id']}/redraw", json={"opening_concept": 1}).json()["status"] == "succeeded"
    assert "image improvement plan" not in fake_llm.tasks()
    fake_llm.calls.clear()
    assert client.post(f"/api/projects/{project['id']}/images/redraw").json()["status"] == "succeeded"
    assert "image improvement plan" not in fake_llm.tasks()
    assert images(client, project)["img3"]["remix"] is None


def test_the_opening_image_can_open_with_any_meme_format(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM) -> None:
    project = make_post(client, sample_docx, humor=1)
    hero = images(client, project)["hero"]
    assert hero["meme"] is None and hero["opening"]["style"] != "meme"

    assert client.post(f"/api/images/{hero['id']}/redraw", json={"meme_format": "nope"}).status_code == 422
    fake_llm.calls.clear()
    done = client.post(f"/api/images/{hero['id']}/redraw", json={"meme_format": "venn"})
    assert done.json()["status"] == "succeeded", done.text
    opened = images(client, project)["hero"]
    assert opened["opening"]["style"] == "meme" and opened["meme"]["format"] == "venn"
    ideas = next(c for c in fake_llm.calls if c["task"] == "meme ideas")
    assert "Pitch the opening meme" in ideas["prompt"]
    # The earlier opening pitches stay on the board next to the new meme.
    assert len(opened["opening"]["pitches"]) > 1
    # Now it is a meme, so the closing bank's tools work on it too.
    assert client.post(f"/api/images/{hero['id']}/redraw", json={"meme_format": "nutrition_label"}).json()["status"] == "succeeded"
    assert images(client, project)["hero"]["meme"]["format"] == "nutrition_label"


def test_an_image_can_build_on_an_earlier_one_and_follows_it(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM) -> None:
    project = make_post(client, sample_docx)
    rows = images(client, project)
    base, later = rows["img2"], rows["img3"]
    assert later["builds_on"] == ""

    # Only an earlier, drawn, non-meme image can be built on.
    assert client.post(f"/api/images/{base['id']}/build-on", json={"slot_id": "img3"}).status_code == 422
    assert client.post(f"/api/images/{later['id']}/build-on", json={"slot_id": "meme"}).status_code == 422
    assert client.post(f"/api/images/{later['id']}/build-on", json={"slot_id": "nope"}).status_code == 422

    fake_llm.calls.clear()
    assert client.post(f"/api/images/{later['id']}/build-on", json={"slot_id": "img2"}).json()["status"] == "succeeded"
    assert images(client, project)["img3"]["builds_on"] == "img2"
    prompt = next(c for c in fake_llm.calls if c["task"] == "chart image design")["prompt"]
    assert "BUILDS ON the earlier image `img2`" in prompt and "<base>" in prompt

    # Redrawing the base reports who builds on it, and the dependents can be matched to it.
    job = client.post(f"/api/images/{base['id']}/redraw", json={}).json()
    assert job["result"]["dependents"] == ["img3"]
    fake_llm.calls.clear()
    assert client.post(f"/api/images/{base['id']}/redraw-dependents").json()["status"] == "succeeded"
    assert [c["task"] for c in fake_llm.calls if "image design" in c["task"]] == ["chart image design"]
    assert "image improvement plan" not in fake_llm.tasks()
    assert client.post(f"/api/images/{later['id']}/redraw-dependents").status_code == 409

    cleared = client.delete(f"/api/images/{later['id']}/build-on")
    assert cleared.status_code == 200 and cleared.json()["builds_on"] == ""


def test_redraw_and_remix_build_on_an_edited_image(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM) -> None:
    project = make_post(client, sample_docx)
    diagram = images(client, project)["img2"]

    # Never edited: the redraw prompt carries no edit block.
    fake_llm.calls.clear()
    client.post(f"/api/images/{diagram['id']}/redraw", json={})
    plain = next(c for c in fake_llm.calls if c["task"] == "diagram image design")
    assert "<edits>" not in plain["prompt"]

    assert client.post(f"/api/images/{diagram['id']}/edit", json={"instruction": "Make the arrows orange"}).json()["status"] == "succeeded"
    fake_llm.calls.clear()
    assert client.post(f"/api/images/{diagram['id']}/redraw", json={"tweaks": {"palette": "viridis"}}).json()["status"] == "succeeded"
    draw = next(c for c in fake_llm.calls if c["task"] == "diagram image design")
    assert "Make the arrows orange" in draw["prompt"] and "<current_design>" in draw["prompt"]
    assert "viridis" in draw["prompt"].lower()
    # Later redraws keep building on it ...
    fake_llm.calls.clear()
    client.post(f"/api/images/{diagram['id']}/redraw", json={})
    assert "Make the arrows orange" in next(c for c in fake_llm.calls if c["task"] == "diagram image design")["prompt"]
    # ... until the author asks for a new idea.
    fake_llm.calls.clear()
    client.post(f"/api/images/{diagram['id']}/redraw", json={"rethink": True})
    assert "<edits>" not in next(c for c in fake_llm.calls if c["task"] == "diagram image design")["prompt"]
    fake_llm.calls.clear()
    client.post(f"/api/images/{diagram['id']}/redraw", json={})
    assert "<edits>" not in next(c for c in fake_llm.calls if c["task"] == "diagram image design")["prompt"]
