"""The Claude-subscription backend, driven by a fake Claude Code CLI (never the real one)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from proseferno.config import Settings
from proseferno.demo import FakeLLM
from proseferno.llm import LLMError, SystemBlock
from proseferno.llm.claude_code import ClaudeCodeCLI, ClaudeCodeLLM
from proseferno.llm.router import RoutingLLM

FAKE = Path(__file__).parents[1] / "fixtures" / "fake_claude.py"
SYSTEM = [SystemBlock("You are the writer.", cache=True), SystemBlock("Voice profile here.")]


class Plan(BaseModel):
    title: str
    points: list[str]


@pytest.fixture
def record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "call.json"
    monkeypatch.setenv("FAKE_CLAUDE_RECORD", str(path))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-must-not-reach-claude-code")
    return path


@pytest.fixture
def llm() -> ClaudeCodeLLM:
    return ClaudeCodeLLM(Settings(_env_file=None), ClaudeCodeCLI([sys.executable, str(FAKE)]))  # type: ignore[call-arg]


def recorded(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


async def test_text_streams_deltas_and_isolates_the_call(llm: ClaudeCodeLLM, record: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "text")
    deltas: list[str] = []
    usage: list[dict[str, int]] = []

    async def on_delta(text: str) -> None:
        deltas.append(text)

    out = await llm.text(task="draft", system=SYSTEM, prompt="Write it.", effort="high", on_delta=on_delta, usage=usage.append)

    assert out == "Hello from your plan."
    assert "".join(deltas) == out
    assert usage == [
        {"input_tokens": 11, "output_tokens": 7, "cache_read_input_tokens": 3, "cache_creation_input_tokens": 0, "requests": 1}
    ]
    call = recorded(record)
    assert call["stdin"] == "Write it."
    assert call["system"] == "You are the writer.\n\nVoice profile here."
    assert call["api_key_seen"] is False  # would bill the API instead of the plan
    args = call["args"]
    assert args[0] == "-p"
    assert args[args.index("--model") + 1] == "claude-opus-5-5"
    assert args[args.index("--effort") + 1] == "high"
    assert args[args.index("--tools") + 1] == ""
    assert args[args.index("--setting-sources") + 1] == ""
    for flag in ("--strict-mcp-config", "--no-session-persistence", "--disable-slash-commands"):
        assert flag in args


async def test_structured_output_is_validated(llm: ClaudeCodeLLM, record: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "structured")
    monkeypatch.setenv("FAKE_CLAUDE_PAYLOAD", json.dumps({"title": "No Single Truth", "points": ["a", "b"]}))

    plan = await llm.structured(task="post plan", system=SYSTEM, prompt="Plan it.", schema=Plan, effort="medium")

    assert plan == Plan(title="No Single Truth", points=["a", "b"])
    args = recorded(record)["args"]
    assert json.loads(args[args.index("--json-schema") + 1])["required"] == ["title", "points"]


async def test_structured_output_with_the_wrong_shape_fails_cleanly(llm: ClaudeCodeLLM, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "structured")
    monkeypatch.setenv("FAKE_CLAUDE_PAYLOAD", json.dumps({"title": 3}))
    with pytest.raises(LLMError, match="post plan"):
        await llm.structured(task="post plan", system=SYSTEM, prompt="Plan it.", schema=Plan, effort="medium")


async def test_research_uses_web_tools_and_returns_citations(llm: ClaudeCodeLLM, record: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "structured")
    payload = {"text": "Use short titles.", "citations": [{"url": "https://example.com/titles", "title": "Titles"}]}
    monkeypatch.setenv("FAKE_CLAUDE_PAYLOAD", json.dumps(payload))

    result = await llm.research(system=SYSTEM, prompt="Research titles.", effort="medium", max_searches=4)

    assert result.text == "Use short titles."
    assert [c.url for c in result.citations] == ["https://example.com/titles"]
    args = recorded(record)["args"]
    assert args[args.index("--tools") + 1] == "WebSearch,WebFetch"
    assert args[args.index("--allowedTools") + 1] == "WebSearch,WebFetch"


@pytest.mark.parametrize(
    ("mode", "message"),
    [
        ("limit", "usage limit is reached. It resets at"),
        ("auth", "not signed in"),
        ("crash", "without a result"),
    ],
)
async def test_failures_explain_themselves(llm: ClaudeCodeLLM, monkeypatch: pytest.MonkeyPatch, mode: str, message: str) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_MODE", mode)
    with pytest.raises(LLMError, match=message):
        await llm.text(task="draft", system=SYSTEM, prompt="Write it.", effort="high")


async def test_missing_claude_code_says_how_to_install() -> None:
    llm = ClaudeCodeLLM(Settings(_env_file=None), ClaudeCodeCLI(discover=False))  # type: ignore[call-arg]
    with pytest.raises(LLMError, match="not installed"):
        await llm.text(task="draft", system=SYSTEM, prompt="Write it.", effort="high")


def test_status_reads_claude_auth_status() -> None:
    status = ClaudeCodeCLI([sys.executable, str(FAKE)]).status()
    assert status.installed and status.uses_subscription
    assert (status.version, status.subscription_type, status.email) == ("2.1.300", "pro", "writer@example.com")
    assert ClaudeCodeCLI(discover=False).status().installed is False


async def test_router_follows_the_connection_setting() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    api, subscription = FakeLLM(), FakeLLM()
    router = RoutingLLM(settings, api=api, subscription=subscription)
    assert router.active is api
    settings.claude_connection = "subscription"
    assert router.active is subscription
