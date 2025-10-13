from __future__ import annotations

from contextlib import asynccontextmanager
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

    async def close(self) -> None:
        await self._client.aclose()

    async def chat_completions(self, payload: Dict) -> httpx.Response:
        return await self._client.post("/chat/completions", json=payload)

    @asynccontextmanager
    async def stream_chat_completions(self, payload: Dict) -> AsyncGenerator[httpx.Response, None]:
        async with self._client.stream("POST", "/chat/completions", json=payload) as response:
            yield response


async def build_openai_client(base_url: str | Any, api_key: str) -> OpenAIProviderClient:
    return OpenAIProviderClient(base_url=base_url, api_key=api_key)
