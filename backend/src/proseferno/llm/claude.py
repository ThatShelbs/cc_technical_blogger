"""Claude implementation of :class:`proseferno.llm.base.LLM` (Anthropic Python SDK)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import anthropic
from anthropic import AsyncAnthropic

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

# Server-side refusal fallbacks ("default" routing by refusal category).
FALLBACK_BETA = "server-side-fallback-2026-07-01"
WEB_SEARCH_TOOL = "web_search_20260209"


class ClaudeLLM:
    def __init__(self, settings: Settings, client_factory: Callable[[], AsyncAnthropic]) -> None:
        self.settings = settings
        self._client_factory = client_factory

    # -- public API ---------------------------------------------------------

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
        client = self._client_factory()
        with _translate_errors(task):
            response = await client.beta.messages.parse(
                **self._common(system, effort, max_tokens),
                messages=[{"role": "user", "content": prompt}],
                output_format=schema,
            )
        self._check(response, task)
        self._record(response, usage)
        parsed = response.parsed_output
        if parsed is None:
            raise LLMError(f"Claude returned no structured result for {task}.")
        return parsed  # type: ignore[return-value]

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
        client = self._client_factory()
        with _translate_errors(task):
            async with client.beta.messages.stream(
                **self._common(system, effort, max_tokens),
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                async for chunk in stream.text_stream:
                    if on_delta is not None:
                        await on_delta(chunk)
                final = await stream.get_final_message()
        self._check(final, task)
        self._record(final, usage)
        return "".join(block.text for block in final.content if block.type == "text")

    async def research(
        self,
        *,
        system: list[SystemBlock],
        prompt: str,
        effort: str,
        max_searches: int = 8,
        usage: UsageSink | None = None,
    ) -> ResearchResult:
        client = self._client_factory()
        messages: Any = [{"role": "user", "content": prompt}]
        tools: Any = [{"type": WEB_SEARCH_TOOL, "name": "web_search", "max_uses": max_searches}]
        response: Any = None
        for _ in range(6):
            with _translate_errors("web research"):
                async with client.beta.messages.stream(
                    **self._common(system, effort, 32000),
                    messages=messages,
                    tools=tools,
                ) as stream:
                    response = await stream.get_final_message()
            self._record(response, usage)
            if response.stop_reason != "pause_turn":
                break
            # Server tool hit its per-turn iteration limit: send the turn back to resume.
            messages.append({"role": "assistant", "content": response.content})
        assert response is not None
        self._check(response, "web research")

        texts: list[str] = []
        citations: dict[str, Citation] = {}
        for block in response.content:
            if block.type != "text":
                continue
            texts.append(block.text)
            for cite in getattr(block, "citations", None) or []:
                url = getattr(cite, "url", None)
                if url and url not in citations:
                    citations[url] = Citation(
                        url=url,
                        title=getattr(cite, "title", "") or "",
                        cited_text=getattr(cite, "cited_text", "") or "",
                    )
        return ResearchResult(text="".join(texts), citations=list(citations.values()))

    # -- helpers -------------------------------------------------------------

    def _common(self, system: list[SystemBlock], effort: str, max_tokens: int) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.settings.model,
            "max_tokens": max_tokens,
            "system": _system_param(system),
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": effort},
        }
        if self.settings.use_fallbacks and "haiku" not in self.settings.model:
            kwargs["betas"] = [FALLBACK_BETA]
            kwargs["fallbacks"] = "default"
        return kwargs

    @staticmethod
    def _check(response: Any, task: str) -> None:
        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            raise LLMRefusalError(
                getattr(details, "category", None),
                getattr(details, "explanation", None),
            )
        if response.stop_reason == "max_tokens":
            log.warning("%s hit max_tokens; output may be truncated", task)

    @staticmethod
    def _record(response: Any, sink: UsageSink | None) -> None:
        if sink is None or response is None:
            return
        u = response.usage
        sink(
            {
                "input_tokens": u.input_tokens or 0,
                "output_tokens": u.output_tokens or 0,
                "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
                "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
                "requests": 1,
            }
        )


def _system_param(blocks: list[SystemBlock]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for block in blocks:
        if not block.text:
            continue
        entry: dict[str, Any] = {"type": "text", "text": block.text}
        if block.cache:
            entry["cache_control"] = {"type": "ephemeral"}
        out.append(entry)
    return out


class _translate_errors:
    """Turn SDK exceptions into messages a writer can act on."""

    def __init__(self, task: str) -> None:
        self.task = task

    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type: Any, exc: Any, _tb: Any) -> None:
        if exc is None or isinstance(exc, LLMError):
            return
        if isinstance(exc, anthropic.AuthenticationError):
            raise LLMError("Claude rejected the credentials. Sign in again or update your API key in Settings.") from exc
        if isinstance(exc, anthropic.PermissionDeniedError):
            raise LLMError("Your Claude account does not have access to this model or feature.") from exc
        if isinstance(exc, anthropic.NotFoundError):
            raise LLMError(f"Model not found: check the model setting ({exc.message}).") from exc
        if isinstance(exc, anthropic.RateLimitError):
            raise LLMError("Claude rate limit reached. Wait a minute and try again.") from exc
        if isinstance(exc, anthropic.BadRequestError):
            raise LLMError(f"Claude rejected the {self.task} request: {exc.message}") from exc
        if isinstance(exc, anthropic.APIStatusError):
            raise LLMError(f"Claude API error {exc.status_code} during {self.task}. Try again shortly.") from exc
        if isinstance(exc, anthropic.APIConnectionError):
            raise LLMError("Could not reach Claude. Check your internet connection.") from exc
