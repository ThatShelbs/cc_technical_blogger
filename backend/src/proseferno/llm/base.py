"""The LLM interface the rest of the app depends on.

Everything that talks to a model goes through :class:`LLM`, so tests swap in a
fake and the pipeline code stays provider-agnostic.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

OnDelta = Callable[[str], Awaitable[None]]
UsageSink = Callable[[dict[str, int]], None]


class LLMError(RuntimeError):
    """A model call failed in a way the user should see."""


class LLMNotConfiguredError(LLMError):
    def __init__(self) -> None:
        super().__init__(
            "Proseferno is not signed in to Claude. Open Settings and choose 'Sign in with Claude' or paste an Anthropic API key."
        )


class LLMRefusalError(LLMError):
    def __init__(self, category: str | None, explanation: str | None = None) -> None:
        self.category = category
        detail = f" ({category})" if category else ""
        super().__init__(f"Claude declined this request{detail}. {explanation or ''}".strip())


@dataclass(frozen=True)
class SystemBlock:
    """One block of a system prompt. ``cache`` marks the end of a stable prefix."""

    text: str
    cache: bool = False


@dataclass
class Citation:
    url: str
    title: str = ""
    cited_text: str = ""


@dataclass
class ResearchResult:
    text: str
    citations: list[Citation] = field(default_factory=list)


class LLM(Protocol):
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
    ) -> T: ...

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
    ) -> str: ...

    async def research(
        self,
        *,
        system: list[SystemBlock],
        prompt: str,
        effort: str,
        max_searches: int = 8,
        usage: UsageSink | None = None,
    ) -> ResearchResult: ...
