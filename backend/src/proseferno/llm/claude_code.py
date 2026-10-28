"""Claude through the user's own Claude Code CLI (``claude -p``): how Proseferno uses a Pro/Max plan.

Anthropic does not let third-party apps sign in with Claude.ai or use subscription
tokens themselves. What it does allow is the user signing in to the *unmodified*
Claude Code binary with their own subscription, so this backend runs that binary
headless and reads its JSON event stream. Proseferno never reads, stores or
forwards Claude.ai credentials; sign-in happens in Claude Code's own browser flow.

Each call is isolated: Proseferno's prompt replaces Claude Code's system prompt,
no tools (web tools for research only), no MCP servers, no settings, hooks or
CLAUDE.md, no saved session, and an empty working directory.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from proseferno.config import Settings
from proseferno.llm.base import (
    Citation,
    LLMError,
    LLMRefusalError,
    OnDelta,
    ResearchResult,
    SystemBlock,
    T,
    UsageSink,
)

log = logging.getLogger(__name__)

# Removed from Claude Code's environment: it prefers these over the subscription login,
# which would silently bill the API instead of the plan.
API_CREDENTIAL_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
CALL_TIMEOUT_S = 30 * 60
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
INSTALL_URL = "https://code.claude.com/docs/en/setup"


def find_claude() -> list[str] | None:
    """The command that starts Claude Code, avoiding npm's ``.cmd`` shim.

    Running the shim goes through cmd.exe, which mangles JSON arguments, so an npm
    install resolves to the native binary (or ``node cli.js``) inside the package.
    """
    candidates: list[Path] = []
    found = shutil.which("claude")
    if found:
        candidates.append(Path(found))
    home = Path.home()
    candidates += [home / ".local" / "bin" / "claude.exe", home / ".local" / "bin" / "claude"]
    if os.environ.get("APPDATA"):
        candidates.append(Path(os.environ["APPDATA"]) / "npm" / "claude.cmd")
    for path in candidates:
        if not path.is_file():
            continue
        if sys.platform != "win32" or path.suffix.lower() == ".exe":
            return [str(path)]
        package = path.parent / "node_modules" / "@anthropic-ai" / "claude-code"
        native = package / "bin" / "claude.exe"
        if native.is_file():
            return [str(native)]
        script = package / "cli.js"
        node = shutil.which("node")
        if script.is_file() and node:
            return [node, str(script)]
    return None


def child_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in API_CREDENTIAL_VARS}
    env["CLAUDE_CODE_SKIP_PROMPT_HISTORY"] = "1"
    return env


@dataclass
class ClaudeCodeStatus:
    installed: bool
    version: str | None = None
    logged_in: bool = False
    auth_method: str | None = None
    subscription_type: str | None = None
    email: str | None = None
    error: str | None = None

    @property
    def uses_subscription(self) -> bool:
        return self.logged_in and self.auth_method == "claude.ai"


class ClaudeCodeCLI:
    """Finds and runs the Claude Code binary. Tests pass ``discover=False`` so the real CLI never runs."""

    def __init__(self, command: list[str] | None = None, *, discover: bool = True) -> None:
        self._command = command
        self._discover = discover
        self._status: tuple[float, ClaudeCodeStatus] | None = None
        self._status_lock = threading.Lock()

    @property
    def command(self) -> list[str] | None:
        if self._command:
            return self._command
        return find_claude() if self._discover else None

    def _run(self, *args: str, timeout: float = 20) -> subprocess.CompletedProcess[str]:
        command = self.command
        if command is None:
            raise FileNotFoundError("Claude Code is not installed.")
        return subprocess.run(
            [*command, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=child_env(),
            stdin=subprocess.DEVNULL,
            creationflags=NO_WINDOW,
            check=False,
        )

    def status(self, *, max_age: float = 5.0) -> ClaudeCodeStatus:
        """``claude auth status`` (free, no model call), cached briefly because the UI polls it."""
        with self._status_lock:
            if self._status and time.monotonic() - self._status[0] < max_age:
                return self._status[1]
            status = self._read_status()
            self._status = (time.monotonic(), status)
            return status

    def forget_status(self) -> None:
        with self._status_lock:
            self._status = None

    def _read_status(self) -> ClaudeCodeStatus:
        if self.command is None:
            return ClaudeCodeStatus(installed=False)
        try:
            version = self._run("--version").stdout.strip().split(" ")[0] or None
            done = self._run("auth", "status")
            data = json.loads(done.stdout or "{}")
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
            return ClaudeCodeStatus(installed=True, error=f"Could not read Claude Code's sign-in status: {exc}")
        return ClaudeCodeStatus(
            installed=True,
            version=version,
            logged_in=bool(data.get("loggedIn")),
            auth_method=data.get("authMethod"),
            subscription_type=data.get("subscriptionType"),
            email=data.get("email"),
        )

    def start_login(self) -> subprocess.Popen[str]:
        """``claude auth login``: Anthropic's own browser sign-in. Proseferno only shows its output."""
        command = self.command
        if command is None:
            raise FileNotFoundError(f"Claude Code is not installed. Install it from {INSTALL_URL}.")
        self.forget_status()
        return subprocess.Popen(
            [*command, "auth", "login"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=child_env(),
            creationflags=NO_WINDOW,
        )


class ClaudeCodeLLM:
    """The :class:`proseferno.llm.base.LLM` protocol on top of ``claude -p``."""

    def __init__(self, settings: Settings, cli: ClaudeCodeCLI, *, max_parallel: int = 3) -> None:
        self.settings = settings
        self.cli = cli
        # Image generation fans out; each call is a whole process.
        self._slots = threading.BoundedSemaphore(max_parallel)

    async def structured(
        self,
        *,
        task: str,
        system: list[SystemBlock],
        prompt: str,
        schema: type[T],
        effort: str,
        max_tokens: int = 16000,
        usage: UsageSink | None = None,
    ) -> T:
        result = await self._call(
            task,
            system,
            prompt,
            effort,
            ["--tools", "", "--json-schema", json.dumps(schema.model_json_schema()), "--max-turns", "3"],
        )
        _record(result, usage)
        return _parse_structured(result, schema, task)

    async def text(
        self,
        *,
        task: str,
        system: list[SystemBlock],
        prompt: str,
        effort: str,
        max_tokens: int = 64000,
        on_delta: OnDelta | None = None,
        usage: UsageSink | None = None,
    ) -> str:
        result = await self._call(task, system, prompt, effort, ["--tools", "", "--max-turns", "1"], on_delta)
        _record(result, usage)
        return str(result.get("result") or "")

    async def research(
        self,
        *,
        system: list[SystemBlock],
        prompt: str,
        effort: str,
        max_searches: int = 8,
        usage: UsageSink | None = None,
    ) -> ResearchResult:
        tools = "WebSearch,WebFetch"
        prompt += (
            f"\n\nUse web search (at most {max_searches} searches). In `text`, write the full findings as Markdown;"
            " list every page you relied on in `citations`."
        )
        result = await self._call(
            "web research",
            system,
            prompt,
            effort,
            [
                "--tools",
                tools,
                "--allowedTools",
                tools,
                "--json-schema",
                json.dumps(_ResearchPayload.model_json_schema()),
                "--max-turns",
                str(max_searches * 3 + 5),
            ],
        )
        _record(result, usage)
        payload = _parse_structured(result, _ResearchPayload, "web research")
        return ResearchResult(text=payload.text, citations=[Citation(**c.model_dump()) for c in payload.citations])

    # -- process ---------------------------------------------------------------

    async def _call(
        self,
        task: str,
        system: list[SystemBlock],
        prompt: str,
        effort: str,
        extra: list[str],
        on_delta: OnDelta | None = None,
    ) -> dict[str, Any]:
        command = self.cli.command
        if command is None:
            raise LLMError(
                f"Claude Code is not installed, so Proseferno cannot use your Claude subscription. "
                f"Install it from {INSTALL_URL}, or switch to the Anthropic API in Settings."
            )
        loop = asyncio.get_running_loop()
        lines: asyncio.Queue[str | None] = asyncio.Queue()
        cancel = threading.Event()

        with tempfile.TemporaryDirectory(prefix="proseferno-cc-") as workdir:
            system_file = Path(workdir) / "system.md"
            system_file.write_text("\n\n".join(b.text for b in system if b.text), encoding="utf-8")
            args = [
                *command,
                "-p",
                "--model",
                self.settings.model,
                "--effort",
                effort,
                "--system-prompt-file",
                str(system_file),
                "--output-format",
                "stream-json",
                "--verbose",
                "--include-partial-messages",
                "--strict-mcp-config",
                "--disallowedTools",
                "mcp__*",
                "--setting-sources",
                "",
                "--disable-slash-commands",
                "--no-session-persistence",
                *extra,
            ]

            def emit(line: str | None) -> None:
                loop.call_soon_threadsafe(lines.put_nowait, line)

            worker = asyncio.ensure_future(asyncio.to_thread(self._run_process, args, prompt, workdir, emit, cancel))
            result: dict[str, Any] | None = None
            limit: dict[str, Any] | None = None
            try:
                while (line := await lines.get()) is not None:
                    event = _json_line(line)
                    if event is None:
                        continue
                    kind = event.get("type")
                    if kind == "stream_event" and on_delta is not None and event.get("parent_tool_use_id") is None:
                        delta = (event.get("event") or {}).get("delta") or {}
                        if delta.get("type") == "text_delta" and delta.get("text"):
                            await on_delta(delta["text"])
                    elif kind == "rate_limit_event":
                        limit = event.get("rate_limit_info") or limit
                    elif kind == "result":
                        result = event
                code, stderr = await worker
            except BaseException:
                cancel.set()
                raise

        if result is None:
            detail = stderr.strip().splitlines()[-1] if stderr.strip() else f"exit code {code}"
            raise LLMError(f"Claude Code stopped during {task} without a result ({detail}).")
        _check(result, limit, task)
        return result

    def _run_process(
        self,
        args: list[str],
        prompt: str,
        workdir: str,
        emit: Callable[[str | None], None],
        cancel: threading.Event,
    ) -> tuple[int, str]:
        with self._slots:
            proc = subprocess.Popen(
                args,
                cwd=workdir,
                env=child_env(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=NO_WINDOW,
            )
            stderr: list[str] = []
            drain = threading.Thread(target=lambda: stderr.extend(proc.stderr or []), daemon=True)
            drain.start()
            watchdog = threading.Thread(target=_kill_when, args=(proc, cancel), daemon=True)
            watchdog.start()
            try:
                assert proc.stdin is not None and proc.stdout is not None
                try:
                    proc.stdin.write(prompt)
                    proc.stdin.close()
                except OSError:
                    pass  # the process exited early; its result explains why
                for line in proc.stdout:
                    emit(line)
                code = proc.wait()
            finally:
                cancel.set()
                if proc.poll() is None:
                    proc.kill()
                emit(None)
            drain.join(timeout=5)
            return code, "".join(stderr)


def _kill_when(proc: subprocess.Popen[str], cancel: threading.Event) -> None:
    """Stop the process when the job is cancelled or the call runs past its timeout."""
    cancel.wait(CALL_TIMEOUT_S)
    if proc.poll() is None:
        proc.kill()


def _json_line(line: str) -> dict[str, Any] | None:
    line = line.strip()
    if not line.startswith("{"):
        return None
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return None
    return event if isinstance(event, dict) else None


def _check(result: dict[str, Any], limit: dict[str, Any] | None, task: str) -> None:
    if result.get("stop_reason") == "refusal":
        raise LLMRefusalError(None)
    if not result.get("is_error"):
        return
    message = str(result.get("result") or result.get("subtype") or "unknown error").strip()
    status = result.get("api_error_status")
    lowered = message.lower()
    if status == 429 or "usage limit" in lowered or "rate limit" in lowered or (limit or {}).get("status") == "rejected":
        resets = (limit or {}).get("resetsAt")
        when = f" It resets at {datetime.fromtimestamp(resets).strftime('%I:%M %p').lstrip('0')}." if resets else ""
        raise LLMError(
            f"Your Claude plan's usage limit is reached.{when} Wait for it to reset, or switch to the Anthropic API in Settings."
        )
    if status in (401, 403) or "/login" in lowered or "not logged in" in lowered or "log in" in lowered:
        raise LLMError("Claude Code is not signed in to your Claude account. Open Settings and choose 'Sign in with Claude'.")
    raise LLMError(f"Claude Code failed during {task}: {message}")


def _parse_structured(result: dict[str, Any], schema: type[T], task: str) -> T:
    raw = result.get("structured_output")
    if raw is None:
        raise LLMError(f"Claude returned no structured result for {task}.")
    try:
        return schema.model_validate(raw)
    except ValidationError as exc:
        raise LLMError(f"Claude's {task} result did not match the expected shape: {exc.errors()[0]['msg']}") from exc


def _record(result: dict[str, Any], sink: UsageSink | None) -> None:
    if sink is None:
        return
    u = result.get("usage") or {}
    sink(
        {
            "input_tokens": int(u.get("input_tokens") or 0),
            "output_tokens": int(u.get("output_tokens") or 0),
            "cache_read_input_tokens": int(u.get("cache_read_input_tokens") or 0),
            "cache_creation_input_tokens": int(u.get("cache_creation_input_tokens") or 0),
            "requests": int(result.get("num_turns") or 1),
        }
    )


class _ResearchCitation(BaseModel):
    url: str
    title: str = ""
    cited_text: str = ""


class _ResearchPayload(BaseModel):
    text: str
    citations: list[_ResearchCitation] = []
