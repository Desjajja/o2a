from __future__ import annotations

from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, HttpUrl, SecretStr


class ModelMapping(BaseModel):
    proxy_name: str = Field(..., description="Anthropic-facing model name")
    upstream_name: str = Field(..., description="Provider backend model identifier")


class ProviderConfig(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex, description="Unique provider id")
    name: str = Field(..., min_length=1, description="Human-friendly provider label")
    base_url: HttpUrl = Field(..., description="Upstream API base URL")
    api_key: SecretStr = Field(..., description="API key used for upstream authentication")
    models: List[ModelMapping] = Field(default_factory=list, description="Model mapping table")


class ProxyConfig(BaseModel):
    providers: List[ProviderConfig] = Field(default_factory=list)


class StagedConfig(BaseModel):
    config: ProxyConfig
    needs_restart: bool = False
    staged_at: Optional[int] = None
