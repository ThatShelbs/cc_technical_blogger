"""Text follows images: a redraw fixes the sentences about the old picture, and a highlight can ask for a new image."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from proseferno.demo import DEMO_IMAGE_SYNC, DEMO_PLACEMENT_EDIT, FakeLLM
from tests.api.test_flow import ready_post


def _image(client: TestClient, project_id: int, kind: str) -> dict:
    return next(i for i in client.get(f"/api/projects/{project_id}").json()["images"] if i["kind"] == kind)


def test_changing_the_meme_format_fixes_the_text_around_it(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM) -> None:
    project = ready_post(client, sample_docx)
    url = f"/api/projects/{project['id']}"
    meme = _image(client, project["id"], "meme")
    other = "nutrition_label" if meme["meme"]["format"] != "nutrition_label" else "venn"
    fake_llm.calls.clear()

    job = client.post(f"/api/images/{meme['id']}/redraw", json={"meme_format": other}).json()
    assert job["status"] == "succeeded", job
    assert job["result"]["text_edits"] == 1 and job["result"]["text_summary"]
    call = next(c for c in fake_llm.calls if c["task"] == "image text sync")
    assert "Format:" in call["prompt"] and "{{image:meme}}" in call["prompt"]

    after = client.get(url).json()
    assert DEMO_IMAGE_SYNC in after["markdown"] and "{{image:meme}}" in after["markdown"]
    assert after["revisions"][0]["kind"] == "image"
    # The change is one undo away.
    restored = client.post(f"{url}/revisions/0/restore").json()
    assert DEMO_IMAGE_SYNC not in restored["markdown"]


def test_a_plain_redraw_leaves_the_text_alone(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM) -> None:
    project = ready_post(client, sample_docx)
    diagram = next(i for i in project["images"] if i["kind"] == "diagram")
    markdown, revisions = project["markdown"], len(project["revisions"])
    fake_llm.calls.clear()

    job = client.post(f"/api/images/{diagram['id']}/redraw", json={}).json()
    assert job["status"] == "succeeded", job
    assert job["result"]["text_edits"] == 0
    after = client.get(f"/api/projects/{project['id']}").json()
    assert after["markdown"] == markdown and len(after["revisions"]) == revisions


def test_a_failed_text_check_never_fails_the_redraw(client: TestClient, sample_docx: bytes, monkeypatch: pytest.MonkeyPatch) -> None:
    project = ready_post(client, sample_docx)
    meme = _image(client, project["id"], "meme")

    async def boom(**_: object) -> dict:
        raise RuntimeError("model fell over")

    monkeypatch.setattr("proseferno.api.projects.sync_text_to_images", boom)
    job = client.post(f"/api/images/{meme['id']}/redraw", json={"rethink": True}).json()
    assert job["status"] == "succeeded", job
    assert job["result"]["text_edits"] == 0 and "could not be checked" in job["result"]["text_error"]
    assert _image(client, project["id"], "meme")["status"] == "ready"


def test_highlight_to_add_an_image_after_its_paragraph(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM) -> None:
    project = ready_post(client, sample_docx)
    url = f"/api/projects/{project['id']}"
    paragraph = next(
        p.strip()
        for p in project["markdown"].split("\n\n")
        if p.strip() and not p.lstrip().startswith(("#", "{{", "```", "-", ">", "|", "*"))
    )
    selection = paragraph.split(". ")[0]
    before_ids = {i["slot_id"] for i in project["images"]}

    job = client.post(f"{url}/images", json={"selection": selection, "instruction": "keep it simple"}).json()
    assert job["status"] == "succeeded", job
    result = job["result"]
    assert result["kind"] == "diagram" and result["slot_id"] not in before_ids and result["text_edits"] == 1
    assert "keep it simple" in next(c for c in fake_llm.calls if c["task"] == "image placement")["prompt"]

    after = client.get(url).json()
    tag = "{{image:" + result["slot_id"] + "}}"
    assert after["markdown"].count(tag) == 1
    # Right after the paragraph it belongs to, with the sentence that points at it, and ahead of the closing meme.
    assert paragraph + DEMO_PLACEMENT_EDIT + "\n\n" + tag in after["markdown"]
    assert after["markdown"].index(tag) < after["markdown"].index("{{image:meme}}")
    assert after["revisions"][0]["kind"] == "image"

    # The image is drawn, in reading order, and recorded in the plan so later edits keep it.
    order = re.findall(r"\{\{image:([^}]+)\}\}", after["markdown"])
    assert [i["slot_id"] for i in after["images"]] == order
    added = next(i for i in after["images"] if i["slot_id"] == result["slot_id"])
    assert added["status"] == "ready" and added["url"] and len(added["history"]) == 1
    assert result["slot_id"] in {s["slot_id"] for s in after["plan"]["image_slots"]}
    tweak = client.post(f"{url}/tweak", json={"feedback": "Add a joke to the opening"}).json()
    assert tweak["status"] == "succeeded" and tag in client.get(url).json()["markdown"]

    # One undo takes the image's placeholder out of the text again.
    index = next(r["index"] for r in client.get(url).json()["revisions"] if r["kind"] == "image")
    undone = client.post(f"{url}/revisions/{index}/restore").json()
    assert tag not in undone["markdown"] and result["slot_id"] not in {i["slot_id"] for i in undone["images"]}
    assert result["slot_id"] not in {s["slot_id"] for s in undone["plan"]["image_slots"]}


def test_adding_an_image_needs_a_findable_highlight_and_an_idle_post(client: TestClient, sample_docx: bytes) -> None:
    project = ready_post(client, sample_docx)
    url = f"/api/projects/{project['id']}"
    assert client.post(f"{url}/images", json={"selection": "words that are nowhere in this post"}).status_code == 422
    assert client.post(f"{url}/images", json={"selection": ""}).status_code == 422
    assert client.post("/api/projects/9999/images", json={"selection": "x"}).status_code == 404
