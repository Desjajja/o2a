from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

from pydantic import ValidationError

from .models import ModelMapping, ProviderConfig, ProxyConfig, StagedConfig


class SettingsManager:
    """Handles active and staged configuration with restart semantics."""

    def __init__(self, config_path: Path) -> None:
        self._config_path = config_path
        self._lock = asyncio.Lock()
        self._active_config = ProxyConfig(providers=[])
        self._staged_config: Optional[StagedConfig] = None
        self._model_index: Dict[str, Tuple[ProviderConfig, ModelMapping]] = {}

    async def startup(self) -> None:
        async with self._lock:
            if not self._config_path.exists():
                self._config_path.parent.mkdir(parents=True, exist_ok=True)
                self._config_path.write_text(json.dumps({"providers": []}, indent=2))
            self._active_config = self._load_file()
            self._staged_config = StagedConfig(config=self._active_config, needs_restart=False)
            self._rebuild_index(self._active_config)

    def _load_file(self) -> ProxyConfig:
        data = json.loads(self._config_path.read_text())
        return ProxyConfig.model_validate(data)

    async def get_staged(self) -> StagedConfig:
        async with self._lock:
            assert self._staged_config is not None
            return self._staged_config

    async def get_active(self) -> ProxyConfig:
        async with self._lock:
            return self._active_config

    async def stage(self, payload: dict) -> StagedConfig:
        config = ProxyConfig.model_validate(payload)
        staged = StagedConfig(
            config=config,
            needs_restart=True,
            staged_at=int(time.time())
        )
        async with self._lock:
            self._staged_config = staged
            self._write_config(config)
        return staged

    async def apply(self) -> StagedConfig:
        async with self._lock:
            if not self._staged_config:
                raise RuntimeError("No staged configuration to apply")
            self._active_config = self._staged_config.config
            self._write_config(self._active_config)
            self._rebuild_index(self._active_config)
            self._staged_config.needs_restart = False
            return self._staged_config

    def _rebuild_index(self, config: ProxyConfig) -> None:
        index: Dict[str, Tuple[ProviderConfig, ModelMapping]] = {}
        for provider in config.providers:
            for mapping in provider.models:
                index[mapping.proxy_name] = (provider, mapping)
        self._model_index = index

    def _write_config(self, config: ProxyConfig) -> None:
        serialised = {
            "providers": [
                {
                    "id": provider.id,
                    "name": provider.name,
                    "base_url": str(provider.base_url),
                    "api_key": provider.api_key.get_secret_value(),
                    "models": [
                        {
                            "proxy_name": mapping.proxy_name,
                            "upstream_name": mapping.upstream_name,
                        }
                        for mapping in provider.models
                    ],
                }
                for provider in config.providers
            ]
        }
        self._config_path.write_text(json.dumps(serialised, indent=2))

    async def lookup_model(self, proxy_name: str) -> Tuple[ProviderConfig, ModelMapping]:
        async with self._lock:
            if proxy_name not in self._model_index:
                raise KeyError(proxy_name)
            return self._model_index[proxy_name]

    async def get_provider(self, provider_id: str) -> ProviderConfig:
        async with self._lock:
            for provider in self._active_config.providers:
                if provider.id == provider_id:
                    return provider
        raise KeyError(provider_id)

    async def validate_payload(self, payload: dict) -> ProxyConfig:
        try:
            return ProxyConfig.model_validate(payload)
        except ValidationError as exc:  # pragma: no cover - returning clean error downstream
            raise exc
