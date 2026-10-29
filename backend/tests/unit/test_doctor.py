from __future__ import annotations

from pathlib import Path

from proseferno.config import Settings
from proseferno.doctor import Check, data_dir_writable, format_report, frontend_state, run_checks, should_offer_demo
from proseferno.llm.auth import ClaudeAuth
from proseferno.secrets import MemorySecretStore


def make_auth(tmp_path: Path, secrets: MemorySecretStore | None = None, env: dict[str, str] | None = None) -> ClaudeAuth:
    return ClaudeAuth(
        secrets or MemorySecretStore(),
        env={"ANTHROPIC_CONFIG_DIR": str(tmp_path / "anthropic"), **(env or {})},
        discover_ant=False,
    )


def checks_by_name(settings: Settings, tmp_path: Path, **kwargs):  # type: ignore[no-untyped-def]
    options = {"auth": make_auth(tmp_path), "node": lambda: 22, "port_free": lambda _h, _p: True, "claude": lambda: None}
    options.update(kwargs)
    return {c.name: c for c in run_checks(settings, repo_root=tmp_path, **options)}


def test_a_fresh_machine_is_ready_to_run_with_notes(settings: Settings, tmp_path: Path) -> None:
    checks = checks_by_name(settings, tmp_path)
    assert checks["Data folder"].ok and checks["Python"].ok
    assert not checks["Claude connection"].ok and not checks["Claude connection"].hard
    report = format_report(list(checks.values()))
    assert "Ready to run" in report and "launch.bat --demo" in report


def test_hard_failures_are_reported_and_soft_ones_are_not_fatal() -> None:
    report = format_report([Check("A", False, "broke", "fix it", hard=True), Check("B", False, "meh")])
    assert "[FAIL] A: broke" in report and "Fix: fix it" in report and "[note] B" in report
    assert "must be fixed" in report


def test_connection_is_found_from_a_saved_key(settings: Settings, tmp_path: Path) -> None:
    auth = make_auth(tmp_path, MemorySecretStore({"anthropic_api_key": "sk-test"}))
    assert checks_by_name(settings, tmp_path, auth=auth)["Claude connection"].ok


def test_port_node_and_frontend_checks(settings: Settings, tmp_path: Path) -> None:
    (tmp_path / "frontend").mkdir()
    (tmp_path / "frontend" / "package.json").write_text("{}", encoding="utf-8")
    checks = checks_by_name(settings, tmp_path, node=lambda: 18, port_free=lambda _h, _p: False)
    assert not checks["Node.js"].ok and "22" in checks["Node.js"].fix
    assert not checks["Port"].ok
    assert not checks["Web interface"].ok

    dist = tmp_path / "frontend" / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html></html>", encoding="utf-8")
    assert frontend_state(tmp_path)[0] is True


def test_data_folder_must_be_writable(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("not a folder", encoding="utf-8")
    ok, detail = data_dir_writable(blocker / "data")
    assert not ok and "Cannot write" in detail


def test_long_windows_paths_are_flagged(settings: Settings, tmp_path: Path) -> None:
    deep = tmp_path / ("x" * 120)
    deep.mkdir()
    flagged = run_checks(settings, repo_root=deep, platform="win32", env={}, auth=make_auth(tmp_path), node=lambda: 22, claude=lambda: None)
    assert any(c.name == "Windows path length" for c in flagged)
    fixed = run_checks(
        settings,
        repo_root=deep,
        platform="win32",
        env={"UV_PROJECT_ENVIRONMENT": "C:/v"},
        auth=make_auth(tmp_path),
        node=lambda: 22,
        claude=lambda: None,
    )
    assert not any(c.name == "Windows path length" for c in fixed)


def test_demo_is_offered_only_on_a_bare_first_launch(settings: Settings, tmp_path: Path) -> None:
    bare = make_auth(tmp_path)
    assert should_offer_demo(settings, bare, interactive=True)
    assert not should_offer_demo(settings, bare, interactive=False)
    assert not should_offer_demo(settings, make_auth(tmp_path, MemorySecretStore({"anthropic_api_key": "k"})), interactive=True)
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    settings.db_path.write_bytes(b"")
    assert not should_offer_demo(settings, bare, interactive=True)
