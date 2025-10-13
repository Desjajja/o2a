from __future__ import annotations

import asyncio
import json
from pathlib import Path
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

# Try to find config relative to the package, then fall back to project root
config_in_package = Path(__file__).parent.parent / "config" / "settings.json"
config_in_project = Path("config/settings.json")

if config_in_package.exists():
    CONFIG_PATH = config_in_package
elif config_in_project.exists():
    CONFIG_PATH = config_in_project
else:
    # Default to the package location (will be created if needed)
    CONFIG_PATH = config_in_package

app = FastAPI(title="oai2ant proxy", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"]
)

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
    proxy_model = payload.get("model")
    if not proxy_model:
        raise HTTPException(status_code=400, detail="model is required")

    provider, mapping = await runtime.resolve_model(proxy_model)
    client = await runtime.get_client(provider.id)

    upstream_payload = anthropic_request_to_openai(payload, mapping.upstream_name)
    response = await client.chat_completions(upstream_payload)

    if response.is_error:
        try:
            error_payload = response.json()
        except ValueError:
            error_payload = {"error": {"message": response.text}}
        content = anthropic_error_from_openai(error_payload)
        raise HTTPException(status_code=response.status_code, detail=content["error"]["message"])
    return openai_response_to_anthropic(response.json(), proxy_model)


@app.post("/v1/messages")
async def proxy_messages(request: Request, runtime: ProxyRuntime = Depends(get_runtime)):
    payload: Dict = await request.json()
    proxy_model = payload.get("model")
    if not proxy_model:
        raise HTTPException(status_code=400, detail="model is required")

    provider, mapping = await runtime.resolve_model(proxy_model)
    client = await runtime.get_client(provider.id)
    openai_payload = anthropic_request_to_openai(payload, mapping.upstream_name)

    if payload.get("stream"):
        async def event_stream() -> AsyncGenerator[str, None]:
            async with client.stream_chat_completions(openai_payload) as response:
                if response.is_error:
                    try:
                        error_payload = response.json()
                    except ValueError:
                        error_payload = {"error": {"message": response.text}}
                    detail = anthropic_error_from_openai(error_payload)
                    yield f"data: {json.dumps(detail)}\n\n"
                    return
                async for line in openai_stream_to_anthropic(
                    iterate_openai_stream(response),
                    proxy_model
                ):
                    yield line

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    response = await client.chat_completions(openai_payload)
    if response.is_error:
        try:
            error_payload = response.json()
        except ValueError:
            error_payload = {"error": {"message": response.text}}
        content = anthropic_error_from_openai(error_payload)
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
