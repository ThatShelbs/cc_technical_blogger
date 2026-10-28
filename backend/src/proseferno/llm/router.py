"""Send each model call to the connection chosen in Settings (API or Claude subscription)."""

from __future__ import annotations

from proseferno.config import Settings
from proseferno.llm.base import LLM, OnDelta, ResearchResult, SystemBlock, T, UsageSink


class RoutingLLM:
    """Reads ``settings.claude_connection`` on every call, so switching needs no restart."""

    def __init__(self, settings: Settings, *, api: LLM, subscription: LLM) -> None:
        self.settings = settings
        self.api = api
        self.subscription = subscription

    @property
    def active(self) -> LLM:
        return self.subscription if self.settings.claude_connection == "subscription" else self.api

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
        return await self.active.structured(
            task=task, system=system, prompt=prompt, schema=schema, effort=effort, max_tokens=max_tokens, usage=usage
        )

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
        return await self.active.text(
            task=task, system=system, prompt=prompt, effort=effort, max_tokens=max_tokens, on_delta=on_delta, usage=usage
        )

    async def research(
        self,
        *,
        system: list[SystemBlock],
        prompt: str,
        effort: str,
        max_searches: int = 8,
        usage: UsageSink | None = None,
    ) -> ResearchResult:
        return await self.active.research(system=system, prompt=prompt, effort=effort, max_searches=max_searches, usage=usage)
