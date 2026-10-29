"""``proseferno doctor``: check that this machine is ready, with a one-line fix for anything that is not.

Checks never call Claude and never start a sign-in. A failed *hard* check means the app cannot
run; a failed *soft* check is something to know about (for example, no Claude connection yet).
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import keyring

from proseferno.config import REPO_ROOT, Settings
from proseferno.llm.auth import ClaudeAuth
from proseferno.llm.claude_code import find_claude
from proseferno.secrets import KeyringSecretStore

MIN_PYTHON = (3, 13)
MIN_NODE = 22
# Windows stops resolving paths near 260 characters, and the Anthropic SDK has a very long file name.
LONG_PATH = 110
FRONTEND_INPUTS = ("src", "public", "index.html", "package.json", "vite.config.ts")


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    fix: str = ""
    # A failed hard check means the app cannot run; a failed soft check is advice.
    hard: bool = False


def node_major() -> int | None:
    node = shutil.which("node")
    if not node:
        return None
    try:
        out = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=10, check=False).stdout.strip()
        return int(out.lstrip("v").split(".")[0])
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def port_is_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex((host, port)) != 0


def newest_mtime(path: Path) -> float:
    if not path.is_dir():
        return path.stat().st_mtime
    return max([path.stat().st_mtime, *(newest_mtime(child) for child in path.iterdir())])


def frontend_state(repo_root: Path) -> tuple[bool, str]:
    """(up to date, detail). Same rule as ``frontend/scripts/needs-build.mjs``."""
    built = repo_root / "frontend" / "dist" / "index.html"
    if not built.is_file():
        return False, "The web interface has not been built."
    inputs = [repo_root / "frontend" / name for name in FRONTEND_INPUTS if (repo_root / "frontend" / name).exists()]
    if any(newest_mtime(p) > built.stat().st_mtime for p in inputs):
        return False, "The web interface build is older than its source."
    return True, "The web interface is built and up to date."


def data_dir_writable(data_dir: Path) -> tuple[bool, str]:
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=data_dir):
            pass
    except OSError as exc:
        return False, f"Cannot write to {data_dir}: {exc}"
    return True, f"Your data lives in {data_dir}."


def claude_auth(settings: Settings) -> ClaudeAuth:
    return ClaudeAuth(KeyringSecretStore(settings.keyring_service))


def has_claude_connection(auth: ClaudeAuth) -> bool:
    """True when API credentials exist (a saved key, an environment key or a Claude sign-in)."""
    return auth.status("api").signed_in


def should_offer_demo(settings: Settings, auth: ClaudeAuth, *, interactive: bool) -> bool:
    """A bare first launch (no data yet, no Claude connection, a person at the keyboard) gets the demo offered."""
    return interactive and not settings.demo and not settings.db_path.exists() and not has_claude_connection(auth)


def run_checks(
    settings: Settings,
    *,
    auth: ClaudeAuth | None = None,
    repo_root: Path = REPO_ROOT,
    platform: str = sys.platform,
    env: dict[str, str] | os._Environ[str] = os.environ,
    node: Callable[[], int | None] = node_major,
    port_free: Callable[[str, int], bool] = port_is_free,
    claude: Callable[[], list[str] | None] = find_claude,
) -> list[Check]:
    auth = auth or claude_auth(settings)
    checks: list[Check] = []

    ok = sys.version_info >= MIN_PYTHON
    checks.append(
        Check(
            "Python",
            ok,
            f"Python {sys.version_info.major}.{sys.version_info.minor}",
            f"Run through uv, which installs Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} for you: uv run --project backend proseferno",
            hard=True,
        )
    )

    writable, detail = data_dir_writable(settings.data_dir)
    checks.append(Check("Data folder", writable, detail, "Set PROSEFERNO_DATA_DIR to a folder you can write to.", hard=True))

    has_frontend = (repo_root / "frontend" / "package.json").is_file()
    if has_frontend:
        built, detail = frontend_state(repo_root)
        checks.append(Check("Web interface", built, detail, "Run launch.bat (or ./launch.sh); it builds the interface when needed."))
        major = node()
        checks.append(
            Check(
                "Node.js",
                major is not None and major >= MIN_NODE,
                f"Node.js {major}" if major else "Node.js was not found.",
                f"Install Node.js {MIN_NODE} LTS from https://nodejs.org (or: winget install OpenJS.NodeJS.LTS).",
            )
        )

    free = port_free(settings.host, settings.port)
    checks.append(
        Check(
            "Port",
            free,
            f"Port {settings.port} is free." if free else f"Port {settings.port} is in use (Proseferno may already be running).",
            "Close the other program, or set PROSEFERNO_PORT to another number.",
        )
    )

    try:
        backend = keyring.get_keyring()
        name = type(backend).__module__.split(".")[-2:]
        usable = "fail" not in type(backend).__module__ and "null" not in type(backend).__module__
        checks.append(
            Check(
                "Keychain",
                usable,
                f"API keys are stored in {'.'.join(name)}." if usable else "No operating system keychain is available.",
                "Use 'Sign in with Claude' instead of pasting an API key, or install a Secret Service provider (Linux).",
            )
        )
    except Exception as exc:  # noqa: BLE001  (a broken backend must not stop the report)
        checks.append(Check("Keychain", False, f"Could not check the keychain: {exc}", "Use 'Sign in with Claude' instead of an API key."))

    connected = has_claude_connection(auth)
    checks.append(
        Check(
            "Claude connection",
            connected,
            "Claude credentials found." if connected else "No Claude connection yet.",
            "Open Settings in the app to sign in or paste an API key, or try the app first with: launch.bat --demo",
        )
    )
    code = claude()
    checks.append(
        Check(
            "Claude Code (optional)",
            code is not None,
            "Claude Code found; the Claude subscription connection is available." if code else "Claude Code is not installed.",
            "Only needed to use your Claude Pro/Max plan: https://code.claude.com/docs/en/setup",
        )
    )

    deep = len(str(repo_root)) > LONG_PATH and not env.get("UV_PROJECT_ENVIRONMENT")
    if platform == "win32" and deep:
        checks.append(
            Check(
                "Windows path length",
                False,
                f"This folder's path is {len(str(repo_root))} characters long; Windows may fail to install packages here.",
                "Set UV_PROJECT_ENVIRONMENT to a short folder, for example %USERPROFILE%\\.venvs\\proseferno, then run uv sync again.",
            )
        )
    return checks


def format_report(checks: list[Check]) -> str:
    lines = ["", "  Proseferno doctor", ""]
    for check in checks:
        mark = "ok  " if check.ok else ("FAIL" if check.hard else "note")
        lines.append(f"  [{mark}] {check.name}: {check.detail}")
        if not check.ok and check.fix:
            lines.append(f"         Fix: {check.fix}")
    hard = [c for c in checks if c.hard and not c.ok]
    soft = [c for c in checks if not c.hard and not c.ok]
    lines.append("")
    if hard:
        lines.append(f"  {len(hard)} problem{'s' if len(hard) != 1 else ''} must be fixed before Proseferno can run.")
    elif soft:
        lines.append(f"  Ready to run. {len(soft)} note{'s' if len(soft) != 1 else ''} above for you to look at.")
    else:
        lines.append("  Everything looks good.")
    lines.append("")
    return "\n".join(lines)


def run_doctor(settings: Settings) -> int:
    """Print the report; exit code 1 when a hard check failed."""
    checks = run_checks(settings)
    print(format_report(checks))
    return 1 if any(c.hard and not c.ok for c in checks) else 0
