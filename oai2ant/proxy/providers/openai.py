from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from typing import Any, AsyncGenerator, Dict

import httpx


class OpenAIProviderClient:
    def __init__(self, base_url: str | Any, api_key: str, timeout: float = 60.0) -> None:
        # `ProviderConfig.base_url` is a Pydantic `HttpUrl` which does not expose
        # string helpers like `rstrip`, so normalise via `str()` before trimming.
        self._base_url = str(base_url).rstrip("/")
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )
        self._log = logging.getLogger(__name__)

    async def close(self) -> None:
        await self._client.aclose()

    async def chat_completions(self, payload: Dict) -> httpx.Response:
        self._log.debug("POST %s/chat/completions", self._base_url)
        resp = await self._client.post("/chat/completions", json=payload)
        self._log.debug("POST /chat/completions -> %s", resp.status_code)
        return resp

    @asynccontextmanager
    async def stream_chat_completions(self, payload: Dict) -> AsyncGenerator[httpx.Response, None]:
        self._log.debug("STREAM POST %s/chat/completions", self._base_url)
        async with self._client.stream("POST", "/chat/completions", json=payload) as response:
            self._log.debug("STREAM /chat/completions -> %s", response.status_code)
            yield response


async def build_openai_client(base_url: str | Any, api_key: str) -> OpenAIProviderClient:
    return OpenAIProviderClient(base_url=base_url, api_key=api_key)
