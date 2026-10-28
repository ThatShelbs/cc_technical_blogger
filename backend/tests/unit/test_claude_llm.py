from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from pydantic import BaseModel

from proseferno.config import Settings
from proseferno.llm.base import SystemBlock
from proseferno.llm.claude import ClaudeLLM


class Answer(BaseModel):
    value: str


class FakeStream:
    def __init__(self, message: Any) -> None:
        self.message = message

    async def __aenter__(self) -> FakeStream:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def get_final_message(self) -> Any:
        return self.message


class FakeMessages:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def stream(self, **kwargs: Any) -> FakeStream:
        self.calls.append(kwargs)
        usage = SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=0, cache_creation_input_tokens=0)
        return FakeStream(SimpleNamespace(stop_reason="end_turn", usage=usage, parsed_output=Answer(value="ok")))

    async def parse(self, **_: Any) -> Any:  # pragma: no cover - must not be used
        raise AssertionError("structured() must stream: the SDK rejects long non-streaming requests")


async def test_structured_streams_so_large_max_tokens_work(settings: Settings) -> None:
    messages = FakeMessages()
    client = SimpleNamespace(beta=SimpleNamespace(messages=messages))
    llm = ClaudeLLM(settings, lambda: client)  # type: ignore[arg-type, return-value]
    usage: list[dict[str, int]] = []

    result = await llm.structured(
        task="hero image design",
        system=[SystemBlock("sys")],
        prompt="draw",
        schema=Answer,
        effort="medium",
        max_tokens=24000,
        usage=usage.append,
    )

    assert result == Answer(value="ok")
    assert messages.calls[0]["output_format"] is Answer and messages.calls[0]["max_tokens"] == 24000
    assert usage[0]["output_tokens"] == 5
