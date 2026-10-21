"""FLUX.2 [klein] 4B on Cloudflare Workers AI.

API: POST https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/@cf/black-forest-labs/flux-2-klein-4b
with a Bearer token and multipart/form-data fields (prompt, width, height, seed).
Steps are fixed at 4 by the distilled model. The image comes back base64-encoded.
"""

from __future__ import annotations

import base64
from collections.abc import Callable

import httpx

from proseferno.images.base import (
    ImageProviderError,
    ImageProviderNotConfiguredError,
    RenderedImage,
    to_png,
)

API_BASE = "https://api.cloudflare.com/client/v4"
MIN_SIDE, MAX_SIDE = 256, 1920


def clamp_side(value: int) -> int:
    value = max(MIN_SIDE, min(MAX_SIDE, value))
    return value - value % 16


class CloudflareFluxProvider:
    name = "cloudflare-flux"
    label = "FLUX.2 [klein] on Cloudflare Workers AI"

    def __init__(
        self,
        *,
        account_id: Callable[[], str | None],
        api_token: Callable[[], str | None],
        model: str = "@cf/black-forest-labs/flux-2-klein-4b",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._account_id = account_id
        self._api_token = api_token
        self.model = model
        self._transport = transport

    def is_configured(self) -> bool:
        return bool(self._account_id() and self._api_token())

    async def generate(self, prompt: str, *, width: int, height: int, seed: int) -> RenderedImage:
        account, token = self._account_id(), self._api_token()
        if not account or not token:
            raise ImageProviderNotConfiguredError("Add your Cloudflare account ID and API token in Settings to generate images.")
        url = f"{API_BASE}/accounts/{account}/ai/run/{self.model}"
        fields = {
            "prompt": (None, prompt[:2048]),
            "width": (None, str(clamp_side(width))),
            "height": (None, str(clamp_side(height))),
            "seed": (None, str(seed)),
        }
        async with httpx.AsyncClient(transport=self._transport, timeout=180) as client:
            try:
                response = await client.post(url, headers={"Authorization": f"Bearer {token}"}, files=fields)
            except httpx.HTTPError as exc:
                raise ImageProviderError(f"Could not reach Cloudflare Workers AI: {exc}") from exc
        if response.status_code in (401, 403):
            raise ImageProviderError("Cloudflare rejected the API token. It needs the 'Workers AI' permission.")
        if response.status_code == 429:
            raise ImageProviderError("Cloudflare Workers AI rate limit or daily free allocation reached. Try again later.")
        payload = _json(response)
        if response.status_code >= 400 or payload.get("success") is False:
            errors = payload.get("errors") or [{"message": response.text[:300]}]
            message = "; ".join(str(e.get("message", e)) for e in errors)
            raise ImageProviderError(f"Cloudflare image generation failed: {message}")
        result = payload.get("result") if isinstance(payload.get("result"), dict) else payload
        encoded = result.get("image") if isinstance(result, dict) else None
        if not encoded:
            raise ImageProviderError("Cloudflare returned no image.")
        png, w, h = to_png(base64.b64decode(encoded))
        return RenderedImage(png=png, width=w, height=h, provider=self.name, seed=seed)


def _json(response: httpx.Response) -> dict:  # type: ignore[type-arg]
    try:
        data = response.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}
