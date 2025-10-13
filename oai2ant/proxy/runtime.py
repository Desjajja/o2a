from __future__ import annotations

import asyncio
from typing import Dict, Tuple

from fastapi import HTTPException

from .config_manager import SettingsManager
from .models import ModelMapping, ProviderConfig, ProxyConfig
from .providers.openai import OpenAIProviderClient, build_openai_client


class ProxyRuntime:
    def __init__(self, settings: SettingsManager) -> None:
        self._settings = settings
        self._clients: Dict[str, OpenAIProviderClient] = {}
        self._lock = asyncio.Lock()

    async def startup(self) -> None:
        config = await self._settings.get_active()
        await self._rebuild_clients(config)

    async def shutdown(self) -> None:
        async with self._lock:
            for client in self._clients.values():
                await client.close()
            self._clients = {}

    async def on_restart(self) -> None:
        config = await self._settings.get_active()
        await self._rebuild_clients(config)

    async def resolve_model(self, proxy_name: str) -> Tuple[ProviderConfig, ModelMapping]:
        try:
            return await self._settings.lookup_model(proxy_name)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Model {proxy_name} is not configured")

    async def get_client(self, provider_id: str) -> OpenAIProviderClient:
        async with self._lock:
            if provider_id not in self._clients:
                provider = await self._settings.get_provider(provider_id)
                client = await build_openai_client(provider.base_url, provider.api_key.get_secret_value())
                self._clients[provider_id] = client
            return self._clients[provider_id]

    async def _rebuild_clients(self, config: ProxyConfig) -> None:
        async with self._lock:
            for client in self._clients.values():
                await client.close()
            self._clients = {}
            for provider in config.providers:
                client = await build_openai_client(provider.base_url, provider.api_key.get_secret_value())
                self._clients[provider.id] = client
