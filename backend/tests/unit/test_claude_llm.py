from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel

from inferno_ghostwriter.config import Settings
from inferno_ghostwriter.llm.base import SystemBlock
from inferno_ghostwriter.llm.claude import ClaudeLLM


class Answer(BaseModel):
    value: str


class FakeStream:
    def __init__(self, message: Any) -> None:
        self.message = message

    async def __aenter__(self) -> FakeStream:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    def __aiter__(self) -> Any:
        return self._events()

    async def _events(self) -> Any:
        await asyncio.sleep(0)
        yield SimpleNamespace(type="message_start")
        yield SimpleNamespace(type="text", text="ok")

    async def get_final_message(self) -> Any:
        return self.message


class FakeMessages:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.started: list[int] = []

    def stream(self, **kwargs: Any) -> FakeStream:
        self.calls.append(kwargs)
        self.started.append(len(self.calls))
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


def _llm(settings: Settings) -> tuple[ClaudeLLM, FakeMessages]:
    messages = FakeMessages()
    client = SimpleNamespace(beta=SimpleNamespace(messages=messages))
    return ClaudeLLM(settings, lambda: client), messages  # type: ignore[arg-type, return-value]


async def _ask(llm: ClaudeLLM, system: list[SystemBlock]) -> Answer:
    return await llm.structured(task="t", system=system, prompt="p", schema=Answer, effort="low")


async def test_one_hour_ttl_is_sent_only_where_asked(settings: Settings) -> None:
    llm, messages = _llm(settings)
    await _ask(llm, [SystemBlock("a", cache=True, ttl="1h"), SystemBlock("b", cache=True), SystemBlock("c")])

    blocks = messages.calls[0]["system"]
    assert blocks[0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert blocks[1]["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in blocks[2]


async def test_parallel_calls_wait_for_the_first_to_write_the_cache(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    llm, messages = _llm(settings)
    order: list[str] = []
    original = FakeStream._events

    async def logged(self: FakeStream) -> Any:
        order.append("first-event")
        async for event in original(self):
            yield event

    real_stream = messages.stream

    def opened(**kwargs: Any) -> FakeStream:
        order.append("open")
        return real_stream(**kwargs)

    monkeypatch.setattr(FakeStream, "_events", logged)
    monkeypatch.setattr(messages, "stream", opened)

    await asyncio.gather(*(_ask(llm, [SystemBlock("shared prefix", cache=True)]) for _ in range(3)))

    # The leader opens and starts streaming before either twin sends its request.
    assert order[:2] == ["open", "first-event"]
    assert order.count("open") == 3


async def test_different_prefixes_and_uncached_prompts_do_not_wait(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    llm, messages = _llm(settings)
    order: list[str] = []
    original = FakeStream._events

    async def logged(self: FakeStream) -> Any:
        await asyncio.sleep(0)  # let every request open before any first event
        order.append("first-event")
        async for event in original(self):
            yield event

    real_stream = messages.stream

    def opened(**kwargs: Any) -> FakeStream:
        order.append("open")
        return real_stream(**kwargs)

    monkeypatch.setattr(FakeStream, "_events", logged)
    monkeypatch.setattr(messages, "stream", opened)
    await asyncio.gather(
        _ask(llm, [SystemBlock("one", cache=True)]),
        _ask(llm, [SystemBlock("two", cache=True)]),
        _ask(llm, [SystemBlock("plain")]),
    )
    assert order[:3] == ["open"] * 3  # nobody waited for anybody


async def test_a_leader_that_fails_before_streaming_releases_its_twins(settings: Settings) -> None:
    llm, _ = _llm(settings)
    system = [SystemBlock("shared prefix", cache=True)]
    entered, fail = asyncio.Event(), asyncio.Event()

    async def doomed_leader() -> None:
        async with llm._warm(system):
            entered.set()
            await fail.wait()
            raise RuntimeError("leader died before streaming")

    leader = asyncio.create_task(doomed_leader())
    await entered.wait()
    twin = asyncio.create_task(_ask(llm, system))
    await asyncio.sleep(0.01)
    assert not twin.done()  # still waiting behind the leader

    fail.set()
    with pytest.raises(RuntimeError):
        await leader
    assert await asyncio.wait_for(twin, timeout=5) == Answer(value="ok")
