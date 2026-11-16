"""Read one web page the author pasted, so it can be worked into a post as a reference.

Only public http(s) pages are read: local and private addresses are refused, including after a redirect.
Tests and demo mode use ``NoPageReader`` and never go online.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import re
import socket
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import ClassVar, Protocol
from urllib.parse import urljoin, urlsplit

import httpx

log = logging.getLogger(__name__)

MAX_PAGE_BYTES = 1_000_000
MAX_PAGE_TEXT = 6000
MAX_REDIRECTS = 4
_OWN_NETWORK = "That address is on your own network, so it can't be used as a reference."
_NOT_AN_ADDRESS = "That doesn't look like a web address (it should start with http:// or https://)."


class PageReadError(Exception):
    """The page could not be read; the message is shown to the author."""


@dataclass
class Page:
    url: str
    title: str
    description: str
    text: str


class PageReader(Protocol):
    async def read(self, url: str) -> Page: ...


class NoPageReader:
    """Never goes online (tests, demo mode): answers with a canned page about the link's own address."""

    async def read(self, url: str) -> Page:
        parts = urlsplit(url.strip())
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise PageReadError(_NOT_AN_ADDRESS)
        host = parts.netloc.lower().removeprefix("www.")
        if "unreadable" in host:
            raise PageReadError("Couldn't reach that page. Check the address and try again.")
        return Page(
            url=url.strip(),
            title=f"A guide from {host}",
            description="A thorough, free guide the reader can use to go further.",
            text="A thorough, free guide that walks through the ideas step by step, with examples and exercises.",
        )


class _TextExtractor(HTMLParser):
    _SKIP: ClassVar[set[str]] = {"script", "style", "noscript", "svg", "nav", "header", "footer", "aside", "form", "template"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.og_title = ""
        self.description = ""
        self._in_title = False
        self._skip = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self._in_title = True
        elif tag in self._SKIP:
            self._skip += 1
        elif tag == "meta":
            a = {k.lower(): (v or "").strip() for k, v in attrs}
            key = (a.get("name") or a.get("property") or "").lower()
            if key in ("description", "og:description") and not self.description:
                self.description = a.get("content", "")
            elif key == "og:title" and not self.og_title:
                self.og_title = a.get("content", "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag in self._SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        elif not self._skip and data.strip():
            self._chunks.append(data.strip())


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_page(url: str, html: str) -> Page:
    parser = _TextExtractor()
    parser.feed(html)
    return Page(
        url=url,
        title=_squash(parser.title or parser.og_title)[:300],
        description=_squash(parser.description)[:600],
        text=_squash(" ".join(parser._chunks))[:MAX_PAGE_TEXT],
    )


def _blocked_address(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    return addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved or addr.is_multicast or addr.is_unspecified


class HttpPageReader:
    """Reads one public web page: its title, description and main text."""

    def __init__(self, *, timeout: float = 10.0, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.timeout = timeout
        self.transport = transport

    async def _check_host(self, url: str) -> None:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if parts.scheme not in ("http", "https") or not host:
            raise PageReadError(_NOT_AN_ADDRESS)
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            raise PageReadError(_OWN_NETWORK)
        try:
            ipaddress.ip_address(host)
            addresses = [host]
        except ValueError:
            if self.transport is not None:
                return  # tests: no DNS lookup
            try:
                infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
            except OSError as exc:
                raise PageReadError("That web address doesn't exist (the host name could not be found).") from exc
            addresses = [str(info[4][0]) for info in infos]
        if any(_blocked_address(a) for a in addresses):
            raise PageReadError(_OWN_NETWORK)

    async def read(self, url: str) -> Page:
        url = url.strip()
        headers = {"User-Agent": "Mozilla/5.0 (compatible; Inferno Ghostwriter link reader)", "Accept": "text/html,text/plain;q=0.8"}
        async with httpx.AsyncClient(follow_redirects=False, timeout=self.timeout, transport=self.transport, headers=headers) as client:
            for _ in range(MAX_REDIRECTS + 1):
                await self._check_host(url)
                try:
                    async with client.stream("GET", url) as response:
                        location = response.headers.get("location")
                        if response.is_redirect and location:
                            url = urljoin(url, location)
                            continue
                        if response.status_code in (404, 410):
                            raise PageReadError("That page doesn't exist (it answered 404 Not Found).")
                        if response.status_code >= 400:
                            raise PageReadError(f"That site wouldn't let the app read the page (it answered {response.status_code}).")
                        kind = response.headers.get("content-type", "text/html").lower()
                        if "html" not in kind and not kind.startswith("text/"):
                            raise PageReadError("That link isn't a web page the app can read (a PDF or a file?).")
                        body = b""
                        async for chunk in response.aiter_bytes():
                            body += chunk
                            if len(body) >= MAX_PAGE_BYTES:
                                break
                        html = body.decode(response.encoding or "utf-8", errors="replace")
                except httpx.HTTPError as exc:
                    log.debug("Could not read %s: %s", url, exc)
                    raise PageReadError("Couldn't reach that page. Check the address and try again.") from exc
                page = extract_page(url, html)
                if not page.text and not page.title:
                    raise PageReadError("That page has no readable text (it may need JavaScript or a login).")
                return page
        raise PageReadError("That link redirects too many times.")
