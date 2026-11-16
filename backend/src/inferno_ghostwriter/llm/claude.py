"""Claude implementation of :class:`inferno_ghostwriter.llm.base.LLM` (Anthropic Python SDK)."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import json
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import anthropic
from anthropic import AsyncAnthropic

from inferno_ghostwriter.config import Settings
from inferno_ghostwriter.llm.base import (
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
        self._gate = _PrefixGate()

    @contextlib.asynccontextmanager
    async def _warm(self, system: list[SystemBlock]) -> AsyncIterator[_Warmup]:
        """Hold back a request whose cached prefix another in-flight request is still writing."""
        keyed = _prefix_key(self.settings.model, _system_param(system))
        if keyed is None:
            yield _Warmup(None, "", None)
            return
        key, ttl = keyed
        warm = _Warmup(self._gate, key, await self._gate.enter(key, ttl))
        try:
            yield warm
        finally:
            warm.abandon()  # no-op once started()

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
        images: list[bytes] | None = None,
    ) -> T:
        client = self._client_factory()
        content: Any = prompt
        if images:
            content = [
                *(
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.b64encode(png).decode()}}
                    for png in images
                ),
                {"type": "text", "text": prompt},
            ]

        async with self._warm(system) as warm:

            async def attempt() -> Any:
                # Streamed even though nothing reads the deltas: the SDK refuses non-streaming
                # requests whose max_tokens could take longer than 10 minutes.
                async with client.beta.messages.stream(
                    **self._common(system, effort, max_tokens),
                    messages=[{"role": "user", "content": content}],
                    output_format=schema,
                ) as stream:
                    async for _ in stream:
                        warm.started()
                    return await stream.get_final_message()

            response = await _with_retries(task, attempt)
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
        streamed = False

        async with self._warm(system) as warm:

            async def attempt() -> Any:
                nonlocal streamed
                async with client.beta.messages.stream(
                    **self._common(system, effort, max_tokens),
                    messages=[{"role": "user", "content": prompt}],
                ) as stream:
                    # Raw events (not text_stream) so the first one, before any thinking, releases waiting twins.
                    async for event in stream:
                        warm.started()
                        chunk = event.text if event.type == "text" else ""
                        if chunk:
                            streamed = True
                            if on_delta is not None:
                                await on_delta(chunk)
                    return await stream.get_final_message()

            # Retrying after text reached the reader would duplicate it.
            final = await _with_retries(task, attempt, can_retry=lambda: not streamed)
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
        # Text written before a pause is not repeated after it, so keep the content of every round.
        content: list[Any] = []
        async with self._warm(system) as warm:
            for _ in range(6):

                async def attempt() -> Any:
                    async with client.beta.messages.stream(
                        **self._common(system, effort, 32000),
                        messages=messages,
                        tools=tools,
                    ) as stream:
                        async for _event in stream:
                            warm.started()
                        return await stream.get_final_message()

                response = await _with_retries("web research", attempt)
                self._record(response, usage)
                content.extend(response.content)
                if response.stop_reason != "pause_turn":
                    break
                # Server tool hit its per-turn iteration limit: send the turn back to resume.
                messages.append({"role": "assistant", "content": response.content})
        assert response is not None
        self._check(response, "web research")

        texts: list[str] = []
        citations: dict[str, Citation] = {}
        for block in content:
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


_RETRY_DELAYS = (2.0, 6.0, 15.0)


def _is_transient(exc: BaseException) -> bool:
    """Overloaded/5xx, mid-stream error events (reported as status 200) and dropped connections."""
    if isinstance(exc, anthropic.APIConnectionError):
        return True
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code == 200 or exc.status_code in (408, 409, 429) or exc.status_code >= 500
    return False


async def _with_retries(task: str, attempt: Callable[[], Awaitable[Any]], can_retry: Callable[[], bool] = lambda: True) -> Any:
    """Run one streamed request, retrying transient failures the SDK cannot (it only retries before the stream starts)."""
    for delay in (*_RETRY_DELAYS, None):
        try:
            with _translate_errors(task):
                return await attempt()
        except LLMError as exc:
            cause = exc.__cause__
            if delay is None or cause is None or not _is_transient(cause) or not can_retry():
                raise
            log.warning("%s failed (%s); retrying in %.0fs", task, cause, delay)
            await asyncio.sleep(delay)


def _system_param(blocks: list[SystemBlock]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for block in blocks:
        if not block.text:
            continue
        entry: dict[str, Any] = {"type": "text", "text": block.text}
        if block.cache:
            entry["cache_control"] = {"type": "ephemeral", **({"ttl": "1h"} if block.ttl == "1h" else {})}
        out.append(entry)
    return out


_TTL_SECONDS = {"5m": 300.0, "1h": 3600.0}
_MAX_WAIT = 90.0


class _Warmup:
    """Handle for one request: call :meth:`started` once the response begins streaming."""

    def __init__(self, gate: _PrefixGate | None, key: str, event: asyncio.Event | None) -> None:
        self._gate, self._key, self._event = gate, key, event

    def started(self) -> None:
        if self._gate is not None and self._event is not None:
            self._gate.started(self._key, self._event)
            self._event = None

    def abandon(self) -> None:
        if self._gate is not None and self._event is not None:
            self._gate.abandon(self._key, self._event)
            self._event = None


class _PrefixGate:
    """Lets one request write a cached prefix before its concurrent twins send theirs.

    A cache entry is readable only once the first response starts streaming, so N parallel calls over the same
    prefix would each pay a full write. The first becomes the leader; the rest wait for its first event (at most
    ``_MAX_WAIT`` seconds) and then read the cache. Later calls inside the TTL go straight through.
    """

    def __init__(self) -> None:
        self._state: dict[str, float | asyncio.Event] = {}

    async def enter(self, key: str, ttl: float) -> asyncio.Event | None:
        """Return an event when this call must write the prefix, else None (after waiting if a write is in flight)."""
        state = self._state.get(key)
        if isinstance(state, asyncio.Event):
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(state.wait(), _MAX_WAIT)
            return None
        now = time.monotonic()
        if state is not None and now - state < ttl:
            self._state[key] = now  # every read refreshes the cache's lifetime
            return None
        event = asyncio.Event()
        self._state[key] = event
        return event

    def started(self, key: str, event: asyncio.Event) -> None:
        self._state[key] = time.monotonic()
        event.set()

    def abandon(self, key: str, event: asyncio.Event) -> None:
        if self._state.get(key) is event:
            del self._state[key]
        event.set()


def _prefix_key(model: str, system: list[dict[str, Any]]) -> tuple[str, float] | None:
    """Key and shortest TTL of the cached prefix (everything up to the last cache marker), or None if nothing is cached."""
    last = max((i for i, b in enumerate(system) if "cache_control" in b), default=None)
    if last is None:
        return None
    prefix = system[: last + 1]
    ttl = min(_TTL_SECONDS[b["cache_control"].get("ttl", "5m")] for b in prefix if "cache_control" in b)
    digest = hashlib.sha256(json.dumps([model, prefix], sort_keys=True).encode()).hexdigest()
    return digest, ttl


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
        if isinstance(exc, anthropic.BadRequestError) and "credit balance" in str(exc.message).lower():
            raise LLMError(
                "Your Anthropic API credit balance is too low. Inferno Ghostwriter bills the Claude API (Console), "
                "not your Claude Pro plan. Add credits at console.anthropic.com under Plans & Billing."
            ) from exc
        if isinstance(exc, anthropic.BadRequestError):
            raise LLMError(f"Claude rejected the {self.task} request: {exc.message}") from exc
        if isinstance(exc, anthropic.APIStatusError):
            detail = f": {exc.message}" if getattr(exc, "message", "") else ""
            raise LLMError(f"Claude API error {exc.status_code} during {self.task}{detail}. Try again shortly.") from exc
        if isinstance(exc, anthropic.APIConnectionError):
            raise LLMError("Could not reach Claude. Check your internet connection.") from exc
        if isinstance(exc, anthropic.AnthropicError):
            raise LLMError(f"Claude request failed during {self.task}: {exc}") from exc
