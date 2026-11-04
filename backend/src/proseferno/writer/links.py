"""Check that reference links still exist before they go into a post.

Only clear evidence counts as dead: a 404 or 410, or a host that does not resolve. Sites that block bots
(403, 429, timeouts) are given the benefit of the doubt, because that is how most social sites answer
an unknown client.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol

import httpx

log = logging.getLogger(__name__)

DEAD_STATUSES = {404, 410}


class LinkChecker(Protocol):
    async def dead(self, urls: list[str]) -> set[str]: ...


class NoLinkChecker:
    """Trusts every link (tests, demo mode, or when the check is turned off)."""

    async def dead(self, urls: list[str]) -> set[str]:
        return set()


class HttpLinkChecker:
    def __init__(self, *, timeout: float = 8.0, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.timeout = timeout
        self.transport = transport

    async def dead(self, urls: list[str]) -> set[str]:
        unique = list(dict.fromkeys(u for u in urls if u.startswith(("http://", "https://"))))
        if not unique:
            return set()
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=self.timeout,
            transport=self.transport,
            headers={"User-Agent": "Mozilla/5.0 (compatible; Proseferno link check)"},
        ) as client:
            results = await asyncio.gather(*(self._is_dead(client, url) for url in unique))
        return {url for url, is_dead in zip(unique, results, strict=True) if is_dead}

    async def _is_dead(self, client: httpx.AsyncClient, url: str) -> bool:
        try:
            async with client.stream("GET", url) as response:
                return response.status_code in DEAD_STATUSES
        except httpx.ConnectError as exc:
            # A host that does not resolve is gone; other connection trouble may be ours, not theirs.
            message = str(exc).lower()
            return any(m in message for m in ("name or service not known", "nodename nor servname", "getaddrinfo failed", "no address"))
        except httpx.HTTPError as exc:
            log.debug("Link check inconclusive for %s: %s", url, exc)
            return False
