from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from uuid import uuid4
from typing import AsyncGenerator, Dict

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from .config_manager import SettingsManager
from .models import ProviderConfig
from .runtime import ProxyRuntime
from .translators.anthropic import (
    anthropic_error_from_openai,
    anthropic_request_to_openai,
    iterate_openai_stream,
    openai_response_to_anthropic,
    openai_stream_to_anthropic,
)

CONFIG_PATH = Path("config/settings.json")

app = FastAPI(title="oai2ant proxy", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"]
)

logger = logging.getLogger(__name__)


def _summarize_anthropic_payload(payload: Dict) -> Dict:
    msgs = payload.get("messages") or []
    roles = [m.get("role") for m in msgs[:3]]
    content_types = [
        (type(m.get("content")).__name__ if not isinstance(m.get("content"), list) else "list")
        for m in msgs[:3]
    ]
    return {
        "model": payload.get("model"),
        "stream": bool(payload.get("stream", False)),
        "system_type": (type(payload.get("system")).__name__ if payload.get("system") is not None else None),
        "messages_count": len(msgs),
        "first_roles": roles,
        "first_content_types": content_types,
        "has_stop_sequences": "stop_sequences" in payload,
        "has_schema": "schema" in payload,
        "max_tokens": payload.get("max_tokens"),
        "temperature": payload.get("temperature"),
        "top_p": payload.get("top_p"),
    }


def _summarize_openai_payload(payload: Dict) -> Dict:
    msgs = payload.get("messages") or []
    roles = [m.get("role") for m in msgs[:3]]
    return {
        "upstream_model": payload.get("model"),
        "messages_count": len(msgs),
        "first_roles": roles,
        "has_response_format": bool(payload.get("response_format")),
        "has_stop": bool(payload.get("stop")),
        "max_tokens": payload.get("max_tokens"),
        "stream": bool(payload.get("stream", False)),
    }

settings_manager = SettingsManager(CONFIG_PATH)
runtime = ProxyRuntime(settings_manager)
startup_lock = asyncio.Lock()


def _provider_payload(provider: ProviderConfig) -> Dict:
    data = provider.model_dump()
    data["api_key"] = provider.api_key.get_secret_value()
    return data


async def ensure_startup() -> None:
    async with startup_lock:
        if not getattr(app.state, "initialized", False):
            await settings_manager.startup()
            await runtime.startup()
            app.state.initialized = True


@app.on_event("startup")
async def on_startup() -> None:  # pragma: no cover - executed by ASGI runtime
    await ensure_startup()
    logger.info("proxy started with config at %s", CONFIG_PATH)


@app.on_event("shutdown")
async def on_shutdown() -> None:  # pragma: no cover
    await runtime.shutdown()


async def get_settings() -> SettingsManager:
    await ensure_startup()
    return settings_manager


async def get_runtime() -> ProxyRuntime:
    await ensure_startup()
    return runtime


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/admin/config")
async def read_config(settings: SettingsManager = Depends(get_settings)) -> Dict:
    staged = await settings.get_staged()
    return {
        "providers": [_provider_payload(provider) for provider in staged.config.providers],
        "needs_restart": staged.needs_restart,
        "staged_at": staged.staged_at,
    }


@app.put("/admin/config")
async def update_config(payload: Dict, settings: SettingsManager = Depends(get_settings)) -> Dict:
    staged = await settings.stage(payload)
    return {
        "providers": [_provider_payload(provider) for provider in staged.config.providers],
        "needs_restart": staged.needs_restart,
        "staged_at": staged.staged_at,
    }


@app.post("/admin/restart")
async def apply_restart(settings: SettingsManager = Depends(get_settings)) -> Dict:
    staged = await settings.apply()
    await runtime.on_restart()
    return {
        "providers": [_provider_payload(provider) for provider in staged.config.providers],
        "needs_restart": staged.needs_restart,
        "staged_at": staged.staged_at,
    }


@app.post("/admin/test-chat")
async def test_chat(payload: Dict, runtime: ProxyRuntime = Depends(get_runtime)) -> Dict:
    req_id = str(uuid4())
    proxy_model = payload.get("model")
    if not proxy_model:
        raise HTTPException(status_code=400, detail="model is required")

    provider, mapping = await runtime.resolve_model(proxy_model)
    client = await runtime.get_client(provider.id)

    logger.debug("[%s] /admin/test-chat request: %s", req_id, _summarize_anthropic_payload(payload))
    upstream_payload = anthropic_request_to_openai(payload, mapping.upstream_name)
    logger.debug("[%s] translated payload: %s", req_id, _summarize_openai_payload(upstream_payload))
    response = await client.chat_completions(upstream_payload)
    logger.debug("[%s] upstream status=%s", req_id, response.status_code)

    if response.is_error:
        try:
            error_payload = response.json()
        except ValueError:
            error_payload = {"error": {"message": response.text}}
        logger.warning("[%s] upstream error: %s", req_id, error_payload.get("error", {}).get("type"))
        content = anthropic_error_from_openai(error_payload)
        raise HTTPException(status_code=response.status_code, detail=content["error"]["message"])
    return openai_response_to_anthropic(response.json(), proxy_model)


@app.post("/v1/messages")
async def proxy_messages(request: Request, runtime: ProxyRuntime = Depends(get_runtime)):
    req_id = str(uuid4())
    payload: Dict = await request.json()
    proxy_model = payload.get("model")
    if not proxy_model:
        raise HTTPException(status_code=400, detail="model is required")

    provider, mapping = await runtime.resolve_model(proxy_model)
    client = await runtime.get_client(provider.id)
    logger.debug("[%s] /v1/messages request: %s", req_id, _summarize_anthropic_payload(payload))
    openai_payload = anthropic_request_to_openai(payload, mapping.upstream_name)
    logger.debug("[%s] translated payload: %s", req_id, _summarize_openai_payload(openai_payload))

    if payload.get("stream"):
        async def event_stream() -> AsyncGenerator[str, None]:
            async with client.stream_chat_completions(openai_payload) as response:
                logger.debug("[%s] upstream(stream) status=%s", req_id, response.status_code)
                if response.is_error:
                    try:
                        error_payload = response.json()
                    except ValueError:
                        error_payload = {"error": {"message": response.text}}
                    detail = anthropic_error_from_openai(error_payload)
                    logger.warning("[%s] upstream(stream) error: %s", req_id, error_payload.get("error", {}).get("type"))
                    yield f"data: {json.dumps(detail)}\n\n"
                    return
                async for line in openai_stream_to_anthropic(
                    iterate_openai_stream(response),
                    proxy_model
                ):
                    yield line

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    response = await client.chat_completions(openai_payload)
    logger.debug("[%s] upstream status=%s", req_id, response.status_code)
    if response.is_error:
        try:
            error_payload = response.json()
        except ValueError:
            error_payload = {"error": {"message": response.text}}
        content = anthropic_error_from_openai(error_payload)
        logger.warning("[%s] upstream error: %s", req_id, error_payload.get("error", {}).get("type"))
        return JSONResponse(status_code=response.status_code, content=content)
    return openai_response_to_anthropic(response.json(), proxy_model)


@app.get("/v1/models")
async def list_models(settings: SettingsManager = Depends(get_settings)) -> Dict:
    active = await settings.get_active()
    return {
        "data": [
            {"id": mapping.proxy_name, "type": "model"}
            for provider in active.providers
            for mapping in provider.models
        ]
    }
