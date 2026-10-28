import anthropic
import httpx
import pytest

from proseferno.llm import LLMError
from proseferno.llm import claude as claude_mod


def _status_error(status: int) -> anthropic.APIStatusError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return anthropic.APIStatusError("Overloaded", response=httpx.Response(status, request=request), body=None)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    async def instant(_: float) -> None:
        return None

    monkeypatch.setattr(claude_mod.asyncio, "sleep", instant)


async def test_retries_midstream_error_then_succeeds() -> None:
    calls = 0

    async def attempt() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise _status_error(200)
        return "ok"

    assert await claude_mod._with_retries("critique", attempt) == "ok"
    assert calls == 3


async def test_gives_up_with_detail_after_retries() -> None:
    async def attempt() -> str:
        raise _status_error(200)

    with pytest.raises(LLMError, match="Overloaded"):
        await claude_mod._with_retries("critique", attempt)


async def test_does_not_retry_after_text_was_shown() -> None:
    calls = 0

    async def attempt() -> str:
        nonlocal calls
        calls += 1
        raise _status_error(529)

    with pytest.raises(LLMError):
        await claude_mod._with_retries("draft", attempt, can_retry=lambda: False)
    assert calls == 1
