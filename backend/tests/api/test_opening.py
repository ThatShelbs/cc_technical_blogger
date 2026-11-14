"""The opening image through the API: styles, the panel's pitches, retyped words and the meme sandwich."""

from __future__ import annotations

import io
import zipfile

from fastapi.testclient import TestClient
from PIL import Image

from proseferno.demo import FakeLLM
from tests.api.test_flow import create_persona, upload


def post_with(client: TestClient, sample_docx: bytes, **dials: object) -> dict:
    pid = create_persona(client)["id"]
    upload(client, pid, sample_docx)
    client.post(f"/api/personas/{pid}/voice-profile")
    created = client.post("/api/projects", json={"prompt": "Pie charts", "dials": {"revision_passes": 0, **dials}}).json()
    return client.get(f"/api/projects/{created['project']['id']}").json()


def image(client: TestClient, project: dict, kind: str) -> dict:
    return next(i for i in client.get(f"/api/projects/{project['id']}").json()["images"] if i["kind"] == kind)


def test_the_catalog_lists_every_style_and_what_suits_each_article_type(client: TestClient) -> None:
    catalog = client.get("/api/opening-styles").json()
    ids = [s["id"] for s in catalog["styles"]]
    assert ids[:2] == ["editorial", "data_art"] and {
        "meme",
        "cheat_sheet",
        "data_chart",
        "big_number",
        "versus",
        "framework",
        "receipt",
    } <= set(ids)
    assert catalog["suggested_by_type"]["how_to"][0] == "cheat_sheet"
    assert catalog["suggested_by_type"]["auto"] == ["editorial", "data_art"]


def test_a_chosen_style_its_pitches_and_words_need_no_new_judging(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM) -> None:
    project = post_with(client, sample_docx, opening_style="cheat_sheet")
    assert project["resolved_dials"]["opening_style"] == "cheat_sheet"
    hero = image(client, project, "hero")
    opening = hero["opening"]
    assert opening["style"] == "cheat_sheet" and opening["mode"] == "cheat_sheet" and len(opening["pitches"]) == 4
    assert opening["pitches"][0]["current"] and set(opening["pitches"][0]["scores"]) == {
        "scroller",
        "art_director",
        "fact_checker",
        "author",
    }
    assert opening["thumbnail_fit"] == "cover" and opening["review"]["verdict"] == "passed"
    assert {s["name"] for s in opening["slots"]} >= {"headline", "items.0.label", "items.0.detail"}
    url = f"/api/images/{hero['id']}"

    fake_llm.calls.clear()
    retyped = client.put(f"{url}/opening-words", json={"words": {"headline": "Six rules, zero pies"}})
    assert retyped.status_code == 200, retyped.text
    assert {s["name"]: s["text"] for s in retyped.json()["opening"]["slots"]}["headline"] == "Six rules, zero pies"
    assert fake_llm.calls == [] and len(retyped.json()["history"]) == len(hero["history"]) + 1

    assert client.post(f"{url}/redraw", json={"opening_concept": 2}).json()["status"] == "succeeded"
    assert image(client, project, "hero")["opening"]["pitches"][2]["current"]
    assert "opening ideas" not in fake_llm.tasks() and "opening panel" not in fake_llm.tasks()

    assert client.post(f"{url}/redraw", json={"opening_style": "versus"}).json()["status"] == "succeeded"
    assert image(client, project, "hero")["opening"]["style"] == "versus"
    assert client.post(f"{url}/redraw", json={"opening_style": "hologram"}).status_code == 422
    assert client.post(f"{url}/redraw", json={"opening_concept": 40}).status_code == 422

    meme = image(client, project, "meme")
    assert client.post(f"/api/images/{meme['id']}/redraw", json={"opening_style": "versus"}).status_code == 422
    assert client.put(f"/api/images/{meme['id']}/opening-words", json={"words": {"headline": "x"}}).status_code == 422

    job = client.post(f"{url}/edit", json={"instruction": "Make the headline shorter"}).json()
    assert job["status"] == "succeeded", job
    edit = next(c for c in reversed(fake_llm.calls) if c["task"].startswith("opening "))
    assert "Make the headline shorter" in edit["prompt"]


def test_a_data_opener_prints_its_sources(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM) -> None:
    project = post_with(client, sample_docx, opening_style="data_chart")
    opening = image(client, project, "hero")["opening"]
    assert opening["style"] == "data_chart" and opening["sources"][0]["url"].startswith("https://example.com/")
    assert "Source" in image(client, project, "hero")["caption"]
    research = next(c for c in fake_llm.calls if c["task"] == "research" and "opening chart" in c["prompt"])
    assert "Pie chart accuracy" in research["prompt"]


def test_a_meme_sandwich(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM) -> None:
    project = post_with(client, sample_docx, opening_style="meme", humor=6)
    hero = image(client, project, "hero")
    assert hero["opening"]["style"] == "meme" and hero["opening"]["thumbnail_fit"] == "contain"
    assert hero["meme"] and hero["meme"]["pitches"] and hero["provider"] == "claude-meme"
    ideas = [c for c in fake_llm.calls if c["task"] == "meme ideas"]
    # The opener is pitched first; the closer is told about it, so the two memes differ and can bookend.
    assert "Pitch the opening meme" in ideas[0]["prompt"] and "meme sandwich" in ideas[1]["prompt"]

    url = f"/api/images/{hero['id']}"
    slot = hero["meme"]["slots"][0]["name"]
    fake_llm.calls.clear()
    retyped = client.put(f"{url}/meme-words", json={"words": {slot: "Me, opening with a meme"}})
    assert retyped.status_code == 200, retyped.text
    assert retyped.json()["opening"]["style"] == "meme" and fake_llm.calls == []
    assert client.post(f"{url}/redraw", json={"meme_concept": 1}).json()["status"] == "succeeded"
    assert image(client, project, "hero")["meme"]["pitches"][1]["current"]

    bundle = client.get(f"/api/projects/{project['id']}/export/x")
    with zipfile.ZipFile(io.BytesIO(bundle.content)) as zf, Image.open(io.BytesIO(zf.read("thumbnail.png"))) as thumb:
        assert thumb.size == (1500, 600)


def test_low_humor_never_opens_with_a_meme_and_the_persona_default_applies(client: TestClient, sample_docx: bytes) -> None:
    project = post_with(client, sample_docx, humor=1)
    styles = {p["style"] for p in image(client, project, "hero")["opening"]["pitches"]}
    assert "meme" not in styles and {"editorial", "data_art"} <= styles

    pid = project["persona_id"]
    assert client.get(f"/api/personas/{pid}").json()["default_opening_style"] == "auto"
    assert client.patch(f"/api/personas/{pid}", json={"default_opening_style": "versus"}).json()["default_opening_style"] == "versus"
    created = client.post("/api/projects", json={"prompt": "Pie charts", "dials": {"revision_passes": 0}}).json()
    later = client.get(f"/api/projects/{created['project']['id']}").json()
    assert later["resolved_dials"]["opening_style"] == "versus" and image(client, later, "hero")["opening"]["style"] == "versus"
    assert client.patch(f"/api/personas/{pid}", json={"default_opening_style": "hologram"}).json()["default_opening_style"] == "auto"
