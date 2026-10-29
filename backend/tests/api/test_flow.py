"""End-to-end API flow with a fake Claude."""

from __future__ import annotations

import io
import zipfile

from fastapi.testclient import TestClient

from proseferno.config import Settings
from proseferno.demo import FakeLLM, png_bytes


def create_persona(client: TestClient, name: str = "Shelby") -> dict:
    response = client.post("/api/personas", json={"name": name, "display_name": f"{name} Temple"})
    assert response.status_code == 201, response.text
    return response.json()


def upload(client: TestClient, persona_id: int, data: bytes, kind: str = "own", name: str = "pie.docx") -> dict:
    response = client.post(
        f"/api/personas/{persona_id}/samples",
        files=[("files", (name, data, "application/octet-stream"))],
        data={"kind": kind},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_health_and_spa_fallback(client: TestClient) -> None:
    assert client.get("/api/health").json()["status"] == "ok"
    page = client.get("/projects/1")
    assert page.status_code == 200 and "Proseferno" in page.text
    assert client.get("/api/does-not-exist").status_code == 404


def test_exactly_one_persona_is_active(client: TestClient) -> None:
    first = create_persona(client, "One")
    second = create_persona(client, "Two")
    assert first["is_active"] and not second["is_active"]

    personas = client.post(f"/api/personas/{second['id']}/activate").json()
    assert [p["is_active"] for p in personas] == [False, True]

    client.delete(f"/api/personas/{second['id']}")
    remaining = client.get("/api/personas").json()
    assert len(remaining) == 1 and remaining[0]["is_active"]


def test_full_post_flow(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM) -> None:
    persona = create_persona(client)
    pid = persona["id"]

    # Writing samples: one of mine, one influence; bad files are reported, not fatal.
    result = upload(client, pid, sample_docx)
    assert len(result["added"]) == 1 and result["added"][0]["title"] == "Pie Charts Are Lame"
    upload(client, pid, sample_docx, kind="influence", name="other.docx")
    bad = upload(client, pid, b"not a docx", name="broken.docx")
    assert bad["added"] == [] and bad["errors"]

    # Projects need a voice profile first.
    assert client.post("/api/projects", json={"prompt": "Pie charts"}).status_code == 422

    # Voice profile (with research).
    client.patch(f"/api/personas/{pid}", json={"research_enabled": True})
    job = client.post(f"/api/personas/{pid}/voice-profile").json()
    assert job["status"] == "succeeded", job
    voice_profile = client.get(f"/api/personas/{pid}/voice-profile").json()
    assert voice_profile["version"] == 1 and voice_profile["markdown"].startswith("# Voice Profile")
    assert "Sources" in voice_profile["best_practices"]
    assert client.get(f"/api/personas/{pid}").json()["visual_style"].startswith("warm flat")
    assert fake_llm.tasks().count("sample analysis") == 2

    # Regenerating reuses cached analyses and keeps history.
    client.post(f"/api/personas/{pid}/voice-profile")
    assert fake_llm.tasks().count("sample analysis") == 2
    edited = client.put(f"/api/personas/{pid}/voice-profile", json={"markdown": "# Voice Profile: edited by hand, with care"}).json()
    assert edited["version"] == 3 and edited["edited_by_user"]
    assert len(client.get(f"/api/personas/{pid}/voice-profile/versions").json()) == 3

    # Generate a post with only a prompt (smart defaults).
    created = client.post("/api/projects", json={"prompt": "Why pie charts are lame and what to use instead"})
    assert created.status_code == 201, created.text
    job_id = created.json()["job_id"]
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "succeeded"
    project_id = created.json()["project"]["id"]
    project = client.get(f"/api/projects/{project_id}").json()

    assert project["status"] == "ready"
    assert project["title"] == "Pie Charts Are Lame"
    assert project["resolved_dials"]["topic"] == "Data Visualization"
    assert project["critique"]["overall"] == 8
    assert project["fidelity"]["score"] is not None
    kinds = [img["kind"] for img in project["images"]]
    assert kinds == ["hero", "diagram", "chart", "meme"]
    assert all(img["status"] == "ready" and img["url"] for img in project["images"])
    assert all(img["credit"].startswith("Author: Shelby Temple") for img in project["images"])
    assert project["images"][0]["credit"] == "Author: Shelby Temple; Made with Claude Opus 5.5 (SVG)"
    assert project["images"][2]["credit"].endswith("Claude Opus 5.5 + Vega-Lite")
    assert [img["provider"] for img in project["images"][:3]] == ["claude-svg", "claude-svg", "vega-lite"]
    # The meme came from the writers' room: a catalog format, its joke, and four more ideas for "New idea".
    meme = project["images"][3]
    assert meme["provider"] in ("claude-meme", "vega-lite")
    assert meme["meme"]["format"] and meme["meme"]["premise"] and meme["meme"]["ideas_left"] == 4
    assert "(illustrative data)" in project["images"][2]["caption"]
    # AI-generation detection ran (scan + judge) and the editor saw the scan's findings.
    report = project["authenticity"]
    assert 0 <= report["score"] <= 100 and report["judge_score"] == 82 and report["label"]
    assert any(f["source"] == "judge" for f in report["flagged"])
    critique_call = next(c for c in fake_llm.calls if c.get("task") == "critique")
    assert "AI-writing tells found by an automated scan" in critique_call["prompt"]
    assert "draft" in fake_llm.tasks() and "revision" in fake_llm.tasks()
    # The writer saw the voice profile and the user's own example post.
    draft_call = next(c for c in fake_llm.calls if c.get("task") == "draft")
    system_text = "\n".join(block.text for block in draft_call["system"])
    assert "edited by hand" in system_text and "Pie Charts Are Lame" in system_text

    # Images: file, redraw (Claude designs a new version), upload, revert.
    hero = project["images"][0]
    assert client.get(hero["url"]).headers["content-type"] == "image/png"
    designs_before = fake_llm.tasks().count("hero image design")
    redraw = client.post(f"/api/images/{hero['id']}/redraw", json={}).json()
    assert redraw["status"] == "succeeded", redraw
    assert fake_llm.tasks().count("hero image design") == designs_before + 1
    assert "This is a redraw" in fake_llm.calls[-1]["prompt"]
    uploaded = client.post(f"/api/images/{hero['id']}/upload", files={"file": ("shot.png", png_bytes(), "image/png")}).json()
    assert uploaded["provider"] == "upload" and len(uploaded["history"]) == 3
    reverted = client.post(f"/api/images/{hero['id']}/revert", json={"index": 0}).json()
    assert reverted["provider"] == "claude-svg"
    assert client.get(reverted["history"][1]["url"]).status_code == 200

    # Editing: title, caption, passage rewrite.
    patched = client.patch(f"/api/projects/{project_id}", json={"title": "Stop Baking Pies"}).json()
    assert patched["markdown"].startswith("# Stop Baking Pies")
    client.patch(f"/api/images/{hero['id']}", json={"caption": "A very sad pie"})
    rewritten = client.post(
        f"/api/projects/{project_id}/rewrite", json={"selection": "Bar charts. Seriously, bar charts.", "instruction": "punchier"}
    )
    assert rewritten.status_code == 200, rewritten.text
    assert "Every. Single. Time." in rewritten.json()["markdown"]

    # Exports for every platform.
    for platform, expected in {
        "medium": {"post.html", "post.md", "thumbnail.png", "README.txt"},
        "substack": {"post.html", "post.md", "thumbnail.png"},
        "linkedin": {"post.html", "post.md", "thumbnail.png", "feed-post.txt", "carousel.pdf", "carousel.pptx"},
        "gumroad": {"post.pdf", "post.html"},
        "markdown": {"post.md", "post.docx"},
    }.items():
        response = client.get(f"/api/projects/{project_id}/export/{platform}")
        assert response.status_code == 200, (platform, response.text)
        names = set(zipfile.ZipFile(io.BytesIO(response.content)).namelist())
        assert expected <= names, (platform, names)
        assert sum(n.startswith("images/") for n in names) == 4

    medium = client.get(f"/api/projects/{project_id}/copy/medium").json()["html"]
    assert "<h1>Stop Baking Pies</h1>" in medium and "<h3>" in medium and "data:image/png;base64," in medium
    assert "<figcaption>A very sad pie; Author: Shelby Temple" in medium
    substack = client.get(f"/api/projects/{project_id}/copy/substack").json()["html"]
    assert "<h1>" not in substack and "<h2>" in substack
    linkedin = client.get(f"/api/projects/{project_id}/copy/linkedin").json()["html"]
    assert "<h1>" not in linkedin and "<h2>" in linkedin

    # LinkedIn feed post: a template until Claude writes one in the persona's voice.
    template = client.get(f"/api/projects/{project_id}/linkedin-post").json()
    assert template["written_by"] == "template" and template["characters"] <= 3000 and "#" in template["text"]
    written = client.post(f"/api/projects/{project_id}/linkedin-post").json()
    assert written["written_by"] == "claude" and written["text"].startswith("I stopped making pie charts")
    assert "#DataViz" in written["text"] and "**" not in written["text"]
    assert client.get(f"/api/projects/{project_id}/linkedin-post").json()["text"] == written["text"]
    bundle = zipfile.ZipFile(io.BytesIO(client.get(f"/api/projects/{project_id}/export/linkedin").content))
    assert bundle.read("feed-post.txt").decode().startswith("I stopped making pie charts")
    assert bundle.read("carousel.pdf").startswith(b"%PDF")

    # Re-running the AI check after edits.
    rechecked = client.post(f"/api/projects/{project_id}/authenticity").json()
    assert rechecked["authenticity"]["checked_at"] != report["checked_at"]
    assert client.get(f"/api/projects/{project_id}/export/myspace").status_code == 404

    summaries = client.get("/api/projects").json()
    assert summaries[0]["thumbnail_url"] and summaries[0]["persona_name"] == "Shelby"

    # Deleting the persona removes its projects too.
    assert client.delete(f"/api/personas/{pid}").status_code == 204
    assert client.get("/api/projects").json() == []


def test_persona_versions_rename_and_duplicate(client: TestClient, sample_docx: bytes) -> None:
    pid = create_persona(client)["id"]
    upload(client, pid, sample_docx)
    client.post(f"/api/personas/{pid}/voice-profile", json={"label": "First take"})
    client.post(f"/api/personas/{pid}/voice-profile")
    persona = client.get(f"/api/personas/{pid}").json()
    assert persona["voice_profile_version"] == 2 and persona["latest_voice_profile_version"] == 2
    assert [v["label"] for v in persona["voice_profile_versions"]] == ["", "First take"]

    # Pin an older version: new posts use it, and the persona reports it.
    pinned = client.patch(f"/api/personas/{pid}", json={"pinned_voice_profile_version": 1}).json()
    assert pinned["voice_profile_version"] == 1 and pinned["voice_profile_label"] == "First take"
    assert client.get(f"/api/personas/{pid}/voice-profile").json()["version"] == 1
    assert client.get(f"/api/personas/{pid}/voice-profile?version=2").json()["in_use"] is False
    assert client.patch(f"/api/personas/{pid}", json={"pinned_voice_profile_version": 9}).status_code == 404
    created = client.post("/api/projects", json={"prompt": "Pie charts", "dials": {"image_count": 2, "revision_passes": 0}}).json()
    assert (
        created["project"]["voice_profile_version"] == 1
        or client.get(f"/api/projects/{created['project']['id']}").json()["voice_profile_version"] == 1
    )

    # Naming a version; a new version is used automatically (unpins).
    assert client.patch(f"/api/personas/{pid}/voice-profile/2", json={"label": "Punchier"}).json()["label"] == "Punchier"
    client.put(f"/api/personas/{pid}/voice-profile", json={"markdown": "# Voice Profile: hand edited version here", "label": "Edited"})
    persona = client.get(f"/api/personas/{pid}").json()
    assert persona["voice_profile_version"] == 3 and persona["pinned_voice_profile_version"] is None

    # Rename, then branch a separately named persona from version 2.
    assert client.patch(f"/api/personas/{pid}", json={"name": "  Shelby (work)  "}).json()["name"] == "Shelby (work)"
    copy = client.post(f"/api/personas/{pid}/duplicate", json={"name": "Shelby (playful)", "voice_profile_version": 2})
    assert copy.status_code == 201, copy.text
    copy = copy.json()
    assert copy["name"] == "Shelby (playful)" and not copy["is_active"] and copy["own_samples"] == 1
    assert copy["voice_profile_version"] == 1 and copy["voice_profile_label"] == "Punchier"
    assert len(client.get("/api/personas").json()) == 2


def test_persona_default_dials(client: TestClient, sample_docx: bytes) -> None:
    pid = create_persona(client)["id"]
    upload(client, pid, sample_docx)
    client.post(f"/api/personas/{pid}/voice-profile")
    out = client.patch(
        f"/api/personas/{pid}",
        json={"default_target_words": 900, "default_image_count": 3, "default_opinion": 9, "default_platform": "linkedin"},
    ).json()
    assert out["default_target_words"] == 900 and out["default_opinion"] == 9 and out["default_platform"] == "linkedin"
    assert client.patch(f"/api/personas/{pid}", json={"default_storytelling": 11}).status_code == 422

    created = client.post("/api/projects", json={"prompt": "Pie charts", "dials": {"revision_passes": 0, "formality": 1}}).json()
    project = client.get(f"/api/projects/{created['project']['id']}").json()
    dials = project["resolved_dials"]
    assert (dials["target_words"], dials["image_count"], dials["platform"]) == (900, 3, "linkedin")
    assert dials["opinion"] == 9 and dials["formality"] == 1 and dials["storytelling"] == 5
    assert "Bold hot take" in dials["style_guide"] and "Very casual" in dials["style_guide"]
    assert len(project["images"]) == 3

    # 0 = automatic image count again.
    assert client.patch(f"/api/personas/{pid}", json={"default_image_count": 0}).json()["default_image_count"] is None


def test_seed_import(client: TestClient, settings: Settings, sample_docx: bytes) -> None:
    (settings.seed_samples_dir / "pie.docx").write_bytes(sample_docx)
    (settings.seed_samples_dir / "ignore.xyz").write_text("x")
    assert client.get("/api/seed-samples").json()["files"] == ["pie.docx"]

    pid = create_persona(client)["id"]
    first = client.post(f"/api/personas/{pid}/samples/import-seed").json()
    again = client.post(f"/api/personas/{pid}/samples/import-seed").json()
    assert len(first["added"]) == 1 and again["added"] == []


def test_settings_and_auth(client: TestClient) -> None:
    status = client.get("/api/auth/status").json()
    assert status["signed_in"] is False

    status = client.put("/api/auth/api-key", json={"api_key": "sk-ant-test-123456"}).json()
    assert status["signed_in"] and status["source"] == "app_api_key"
    assert client.delete("/api/auth/api-key").json()["signed_in"] is False

    assert client.post("/api/auth/login").status_code == 409  # no ant CLI in tests

    out = client.put("/api/settings", json={"ai_detection": False, "revision_passes": 2, "model": "claude-sonnet-5-5"}).json()
    assert out["ai_detection"] is False and out["revision_passes"] == 2 and out["model"] == "claude-sonnet-5-5"
    assert out["image_tool_label"].startswith("Claude Sonnet 5.5")
    assert client.get("/api/settings").json()["revision_passes"] == 2


def test_claude_subscription_connection(client: TestClient) -> None:
    assert client.get("/api/settings").json()["claude_connection"] == "api"
    out = client.put("/api/settings", json={"claude_connection": "subscription"}).json()
    assert out["claude_connection"] == "subscription"

    status = client.get("/api/auth/status").json()
    assert status["connection"] == "subscription" and status["source"] == "claude_subscription"
    assert status["claude_code_installed"] is False  # discovery is off in tests
    assert "not installed" in status["detail"]
    assert client.post("/api/auth/claude-code/login").status_code == 409
    assert client.post("/api/auth/test").json()["ok"] is False

    assert client.put("/api/settings", json={"claude_connection": "nope"}).status_code == 422
    assert client.put("/api/settings", json={"claude_connection": "api"}).json()["claude_connection"] == "api"
    assert client.get("/api/auth/status").json()["connection"] == "api"


def ready_post(client: TestClient, sample_docx: bytes) -> dict:
    pid = create_persona(client)["id"]
    upload(client, pid, sample_docx)
    client.post(f"/api/personas/{pid}/voice-profile")
    created = client.post("/api/projects", json={"prompt": "Pie charts", "dials": {"revision_passes": 0}}).json()
    return client.get(f"/api/projects/{created['project']['id']}").json()


def test_title_options_pin_regenerate_and_edit(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM) -> None:
    project = ready_post(client, sample_docx)
    url = f"/api/projects/{project['id']}"
    assert project["pinned_titles"] == []
    selected, pinned = project["title"], "Bars > Pies"

    out = client.patch(url, json={"pinned_titles": [pinned, pinned.upper()]}).json()
    assert out["pinned_titles"] == [pinned]

    out = client.post(f"{url}/titles").json()
    options = out["plan"]["title_options"]
    assert options[:2] == [selected, pinned] and len(options) == 5
    assert "Stop Baking Pies" not in options  # an unpinned option was replaced
    assert out["title"] == selected
    call = next(c for c in fake_llm.calls if c["task"] == "title options")
    assert "Write 3 new title options" in call["prompt"] and "Stop Baking Pies" in call["prompt"]

    # Editing the title rewrites the heading; pins survive regenerating the whole post.
    out = client.patch(url, json={"title": "Pie Charts Are Mostly Lame"}).json()
    assert out["markdown"].startswith("# Pie Charts Are Mostly Lame")
    client.post(f"{url}/generate")
    out = client.get(url).json()
    assert out["pinned_titles"] == [pinned] and out["plan"]["title_options"][0] == pinned


def test_a_broken_image_does_not_fail_the_post(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    original = fake_llm.structured

    async def flaky(**kwargs):  # type: ignore[no-untyped-def]
        if kwargs["task"] == "diagram image design":
            raise ValueError("Streaming is required for operations that may take longer than 10 minutes.")
        return await original(**kwargs)

    monkeypatch.setattr(fake_llm, "structured", flaky)
    project = ready_post(client, sample_docx)

    assert project["status"] == "ready"
    statuses = {img["kind"]: img["status"] for img in project["images"]}
    assert statuses == {"hero": "ready", "diagram": "error", "chart": "ready", "meme": "ready"}
    diagram = next(img for img in project["images"] if img["kind"] == "diagram")
    assert "Redraw" in diagram["error"]


def test_orphaned_pending_images_are_failed(client: TestClient, sample_docx: bytes, services) -> None:  # type: ignore[no-untyped-def]
    from sqlmodel import Session

    from proseferno.db import ProjectImage

    project = ready_post(client, sample_docx)
    image_id = project["images"][0]["id"]
    with Session(services.engine) as session:
        row = session.get(ProjectImage, image_id)
        row.status = "pending"
        session.add(row)
        session.commit()

    assert services.images.fail_pending() == 1
    image = client.get(f"/api/projects/{project['id']}").json()["images"][0]
    assert image["status"] == "error" and "Redraw" in image["error"]


def test_regenerate_with_settings_tweak_and_undo(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM) -> None:
    project = ready_post(client, sample_docx)
    url = f"/api/projects/{project['id']}"
    images_before = {i["slot_id"]: (i["id"], i["url"]) for i in project["images"]}

    # Tweak: one structured call, surgical edit, images untouched, revision recorded.
    fake_llm.calls.clear()
    assert client.post(f"{url}/tweak", json={"feedback": "Add a joke to the opening"}).status_code == 202
    out = client.get(url).json()
    assert "nobody stopped them" in out["markdown"] and out["markdown"] != project["markdown"]
    assert "post tweak" in fake_llm.tasks() and "draft" not in fake_llm.tasks() and "post plan" not in fake_llm.tasks()
    assert {i["slot_id"]: (i["id"], i["url"]) for i in out["images"]} == images_before
    assert out["revisions"][0]["kind"] == "tweak" and out["revisions"][0]["label"] == "Add a joke to the opening"

    # A tweak about an image redraws only that image.
    client.post(f"{url}/tweak", json={"feedback": "The diagram should show the hidden slices"})
    out = client.get(url).json()
    changed = {i["slot_id"] for i in out["images"] if (i["id"], i["url"]) != images_before[i["slot_id"]]}
    assert changed == {"img2"}

    # Undo restores the earlier text, and the restore itself is undoable.
    restored = client.post(f"{url}/revisions/0/restore").json()
    assert restored["markdown"] == project["markdown"] or "nobody stopped them" in restored["markdown"]
    assert restored["revisions"][0]["kind"] == "restore"
    assert client.post(f"{url}/revisions/99/restore").status_code == 404

    # Regenerate with new settings and another persona; history starts fresh.
    other = create_persona(client, "Other")
    assert client.post(f"{url}/generate", json={"persona_id": other["id"]}).status_code == 422
    upload(client, other["id"], sample_docx)
    client.post(f"/api/personas/{other['id']}/voice-profile")
    response = client.post(
        f"{url}/generate",
        json={
            "persona_id": other["id"],
            "prompt": "Pie charts, refined",
            "dials": {"platform": "x", "audience": "analysts", "revision_passes": 0},
        },
    )
    assert response.status_code == 202, response.text
    out = client.get(url).json()
    assert out["persona_id"] == other["id"] and out["prompt"] == "Pie charts, refined"
    assert out["resolved_dials"]["platform"] == "x" and out["resolved_dials"]["audience"] == "analysts"
    assert out["revisions"] == [] and out["active_job_kind"] is None

    names = set(zipfile.ZipFile(io.BytesIO(client.get(f"{url}/export/x").content)).namelist())
    assert {"post.html", "post.md", "thumbnail.png", "teaser-post.txt", "README.txt"} <= names


def test_tweak_needs_a_post(client: TestClient, sample_docx: bytes) -> None:
    persona = create_persona(client)
    upload(client, persona["id"], sample_docx)
    client.post(f"/api/personas/{persona['id']}/voice-profile")
    created = client.post("/api/projects", json={"prompt": "Pie charts", "generate": False}).json()
    assert client.post(f"/api/projects/{created['project']['id']}/tweak", json={"feedback": "shorter"}).status_code == 409


def test_voice_profile_settings(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM) -> None:
    pid = create_persona(client)["id"]
    upload(client, pid, sample_docx)
    upload(client, pid, sample_docx, kind="influence", name="other.docx")
    settings = {"voice_profile_words": 900, "voice_sample_max_words": 40, "voice_influence_weight": 0}
    persona = client.patch(f"/api/personas/{pid}", json=settings).json()
    assert {k: persona[k] for k in settings} == settings

    client.post(f"/api/personas/{pid}/voice-profile")
    analyses = [c for c in fake_llm.calls if c["task"] == "sample analysis"]
    assert len(analyses) == 1  # influence weight 0 leaves the influence sample out
    assert "Humans are bad at comparing angles" not in analyses[0]["prompt"]  # only the first 40 words are read
    synthesis = next(c for c in fake_llm.calls if c["task"] == "voice profile synthesis")
    assert "about 900 words" in synthesis["prompt"] and "No influence posts are used" in synthesis["prompt"]

    # A new word limit re-analyzes; a minimum longer than every sample is a clear error.
    client.patch(f"/api/personas/{pid}", json={"voice_sample_max_words": 0, "voice_influence_weight": 8})
    client.post(f"/api/personas/{pid}/voice-profile")
    assert fake_llm.tasks().count("sample analysis") == 3
    assert "Influence weight 8/10" in [c for c in fake_llm.calls if c["task"] == "voice profile synthesis"][-1]["prompt"]
    client.patch(f"/api/personas/{pid}", json={"voice_sample_min_words": 5000})
    job = client.post(f"/api/personas/{pid}/voice-profile").json()
    assert job["status"] == "failed" and "5000 words" in job["error"]


def test_learns_from_edits_and_feedback(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM) -> None:
    project = ready_post(client, sample_docx)
    url = f"/api/projects/{project['id']}"
    sentence = next(line for line in project["markdown"].splitlines() if len(line.split()) > 12)
    words = sentence.split()
    edited_sentence = " ".join([*words[:3], *words[6:]])
    client.patch(url, json={"markdown": project["markdown"].replace(sentence, edited_sentence)})
    client.post(f"{url}/tweak", json={"feedback": "Fewer exclamation marks, please"})

    persona = client.get(f"/api/personas/{project['persona_id']}").json()
    kinds = {lesson["kind"] for lesson in persona["edit_lessons"]}
    assert kinds == {"remove", "feedback"}
    removed = next(lesson for lesson in persona["edit_lessons"] if lesson["kind"] == "remove")
    assert removed["old"] == " ".join(words[3:6])

    # Lessons reach the writer for the next post, and can be forgotten.
    fake_llm.calls.clear()
    client.post(f"{url}/generate")
    plan_call = next(c for c in fake_llm.calls if c["task"] == "post plan")
    system = "\n".join(block.text for block in plan_call["system"])
    assert "Edits the author keeps making" in system and "Fewer exclamation marks" in system
    persona = client.delete(f"/api/personas/{project['persona_id']}/lessons", params={"index": 0}).json()
    assert len(persona["edit_lessons"]) == 1
    assert client.delete(f"/api/personas/{project['persona_id']}/lessons").json()["edit_lessons"] == []


def test_callbacks_reach_the_editor(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM) -> None:
    pid = create_persona(client)["id"]
    upload(client, pid, sample_docx)
    client.post(f"/api/personas/{pid}/voice-profile")
    created = client.post("/api/projects", json={"prompt": "Pie charts", "dials": {"revision_passes": 1}}).json()
    project = client.get(f"/api/projects/{created['project']['id']}").json()
    assert [c["kind"] for c in project["plan"]["callbacks"]] == ["key_concept", "running_joke"]
    critique = next(c for c in fake_llm.calls if c["task"] == "critique")
    assert 'set up in "Why People Love Pies"' in critique["prompt"] and "set up in the opening" in critique["prompt"]


def test_brand_kit_and_edit_image(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM) -> None:
    pid = create_persona(client)["id"]
    upload(client, pid, sample_docx)
    client.post(f"/api/personas/{pid}/voice-profile")
    kit = {"style": "chalkboard sketch", "palette": ["#112233", "#AABBCC"], "font": "Georgia", "motif": "a tiny robot"}
    created = client.post("/api/projects", json={"prompt": "Pie charts", "brand_kit": kit, "dials": {"revision_passes": 0}}).json()
    project = client.get(f"/api/projects/{created['project']['id']}").json()
    assert project["brand_kit"]["palette"] == ["#112233", "#aabbcc"]
    hero_call = next(c for c in fake_llm.calls if c["task"] == "hero image design")
    assert "chalkboard sketch" in hero_call["prompt"] and "#112233" in hero_call["prompt"] and "a tiny robot" in hero_call["prompt"]
    bad = client.patch(f"/api/projects/{project['id']}", json={"brand_kit": {"palette": ["orange"]}})
    assert bad.status_code == 422

    diagram = next(i for i in project["images"] if i["kind"] == "diagram")
    fake_llm.calls.clear()
    job = client.post(f"/api/images/{diagram['id']}/edit", json={"instruction": "Make the box orange"}).json()
    assert job["status"] == "succeeded", job
    call = next(c for c in fake_llm.calls if c["task"] == "diagram image edit")
    assert "Make the box orange" in call["prompt"] and "<svg" in call["prompt"]
    edited = next(i for i in client.get(f"/api/projects/{project['id']}").json()["images"] if i["id"] == diagram["id"])
    assert len(edited["history"]) == 2 and edited["url"] != diagram["url"]


def test_redraw_all_images_uses_the_new_brand_kit(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM) -> None:
    project = ready_post(client, sample_docx)
    url = f"/api/projects/{project['id']}"
    client.patch(url, json={"brand_kit": {"style": "risograph print", "palette": ["#003366"]}})
    fake_llm.calls.clear()
    job = client.post(f"{url}/images/redraw").json()
    assert job["status"] == "succeeded", job
    designs = [c for c in fake_llm.calls if c["task"].endswith("image design") or c["task"].startswith("meme build")]
    assert len(designs) == len(project["images"]) and all("risograph print" in c["prompt"] for c in designs)
    # A redraw keeps the meme's joke: no new writers' room call.
    assert "meme ideas" not in fake_llm.tasks()
    after = client.get(url).json()["images"]
    assert all(len(i["history"]) == 2 for i in after)


def test_meme_formats_new_ideas_and_edits(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM) -> None:
    formats = client.get("/api/meme-formats").json()
    assert len(formats) == 18 and {"nope_yep", "joke_pie_3d", "comic_grid_4"} <= {f["id"] for f in formats}

    project = ready_post(client, sample_docx)
    meme = next(i for i in project["images"] if i["kind"] == "meme")
    hero = next(i for i in project["images"] if i["kind"] == "hero")
    ideas = next(c for c in fake_llm.calls if c["task"] == "meme ideas")
    assert "Pie Charts Are Lame" in ideas["prompt"] and "Running joke" in ideas["prompt"]

    def current() -> dict:
        return next(i for i in client.get(f"/api/projects/{project['id']}").json()["images"] if i["id"] == meme["id"])

    fake_llm.calls.clear()
    assert client.post(f"/api/images/{meme['id']}/redraw", json={"rethink": True}).json()["status"] == "succeeded"
    assert "meme ideas" not in fake_llm.tasks() and current()["meme"]["ideas_left"] == 3

    assert client.post(f"/api/images/{meme['id']}/redraw", json={"meme_format": "nutrition_label"}).json()["status"] == "succeeded"
    assert current()["meme"]["format"] == "nutrition_label"
    assert client.post(f"/api/images/{meme['id']}/redraw", json={"meme_format": "nope"}).status_code == 422
    assert client.post(f"/api/images/{hero['id']}/redraw", json={"meme_format": "venn"}).status_code == 422

    job = client.post(f"/api/images/{meme['id']}/edit", json={"instruction": "Make the footnote meaner"}).json()
    assert job["status"] == "succeeded", job
    assert current()["meme"]["format"] == "nutrition_label" and len(current()["history"]) == 4
