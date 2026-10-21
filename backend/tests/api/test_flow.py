"""End-to-end API flow with a fake Claude and a fake image model."""

from __future__ import annotations

import io
import zipfile

from fastapi.testclient import TestClient

from proseferno.config import Settings
from proseferno.demo import FakeLLM, FakeRaster, png_bytes


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


def test_full_post_flow(client: TestClient, sample_docx: bytes, fake_llm: FakeLLM, fake_raster: FakeRaster) -> None:
    persona = create_persona(client)
    pid = persona["id"]

    # Writing samples: one of mine, one influence; bad files are reported, not fatal.
    result = upload(client, pid, sample_docx)
    assert len(result["added"]) == 1 and result["added"][0]["title"] == "Pie Charts Are Lame"
    upload(client, pid, sample_docx, kind="influence", name="other.docx")
    bad = upload(client, pid, b"not a docx", name="broken.docx")
    assert bad["added"] == [] and bad["errors"]

    # Projects need a voice soul first.
    assert client.post("/api/projects", json={"prompt": "Pie charts"}).status_code == 422

    # Voice soul (with research).
    client.patch(f"/api/personas/{pid}", json={"research_enabled": True})
    job = client.post(f"/api/personas/{pid}/voice-soul").json()
    assert job["status"] == "succeeded", job
    soul = client.get(f"/api/personas/{pid}/voice-soul").json()
    assert soul["version"] == 1 and soul["markdown"].startswith("# Voice Soul")
    assert "Sources" in soul["best_practices"]
    assert client.get(f"/api/personas/{pid}").json()["visual_style"].startswith("warm flat")
    assert fake_llm.tasks().count("sample analysis") == 2

    # Regenerating reuses cached analyses and keeps history.
    client.post(f"/api/personas/{pid}/voice-soul")
    assert fake_llm.tasks().count("sample analysis") == 2
    edited = client.put(f"/api/personas/{pid}/voice-soul", json={"markdown": "# Voice Soul: edited by hand, with care"}).json()
    assert edited["version"] == 3 and edited["edited_by_user"]
    assert len(client.get(f"/api/personas/{pid}/voice-soul/versions").json()) == 3

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
    assert "(illustrative data)" in project["images"][2]["caption"]
    assert "draft" in fake_llm.tasks() and "revision" in fake_llm.tasks()
    # The writer saw the voice soul and the user's own example post.
    draft_call = next(c for c in fake_llm.calls if c.get("task") == "draft")
    system_text = "\n".join(block.text for block in draft_call["system"])
    assert "edited by hand" in system_text and "Pie Charts Are Lame" in system_text

    # Images: file, redraw (new seed, same prompt), upload, revert.
    hero = project["images"][0]
    assert client.get(hero["url"]).headers["content-type"] == "image/png"
    prompts_before = len(fake_raster.prompts)
    redraw = client.post(f"/api/images/{hero['id']}/redraw", json={}).json()
    assert redraw["status"] == "succeeded", redraw
    assert len(fake_raster.prompts) == prompts_before + 1
    assert fake_raster.prompts[-1][0] == fake_raster.prompts[0][0]
    uploaded = client.post(f"/api/images/{hero['id']}/upload", files={"file": ("shot.png", png_bytes(), "image/png")}).json()
    assert uploaded["provider"] == "upload" and len(uploaded["history"]) == 3
    reverted = client.post(f"/api/images/{hero['id']}/revert", json={"index": 0}).json()
    assert reverted["provider"] == "cloudflare-flux"
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
    assert client.get(f"/api/projects/{project_id}/export/myspace").status_code == 404

    summaries = client.get("/api/projects").json()
    assert summaries[0]["thumbnail_url"] and summaries[0]["persona_name"] == "Shelby"

    # Deleting the persona removes its projects too.
    assert client.delete(f"/api/personas/{pid}").status_code == 204
    assert client.get("/api/projects").json() == []


def test_without_cloudflare_raster_images_fall_back_to_svg(client: TestClient, sample_docx: bytes, fake_raster: FakeRaster) -> None:
    fake_raster.configured = False
    pid = create_persona(client)["id"]
    upload(client, pid, sample_docx)
    client.post(f"/api/personas/{pid}/voice-soul")
    created = client.post("/api/projects", json={"prompt": "Pie charts", "dials": {"image_count": 2, "revision_passes": 0}}).json()
    images = created["project"]["images"] or client.get(f"/api/projects/{created['project']['id']}").json()["images"]

    assert [i["kind"] for i in images] == ["hero", "meme"]
    assert all(i["provider"] == "claude-svg" and i["status"] == "ready" for i in images)
    assert fake_raster.prompts == []


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

    out = client.put("/api/settings", json={"cloudflare_account_id": "acct", "revision_passes": 2, "model": "claude-sonnet-5-5"}).json()
    assert out["cloudflare_account_id"] == "acct" and out["revision_passes"] == 2 and out["model"] == "claude-sonnet-5-5"
    assert client.get("/api/settings").json()["revision_passes"] == 2
