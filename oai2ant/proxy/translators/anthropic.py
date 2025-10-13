from __future__ import annotations

import json
import time
from typing import AsyncGenerator, Dict, Iterable, List, Optional

from fastapi import HTTPException

ANTHROPIC_EVENT_TERMINATOR = "data: [DONE]\n\n"


def _collapse_content(blocks: Iterable[Dict]) -> str:
    text_parts: List[str] = []
    for block in blocks:
        if block.get("type") == "text" and "text" in block:
            text_parts.append(block["text"])
    return "".join(text_parts)


def anthropic_request_to_openai(payload: Dict, upstream_model: str) -> Dict:
    messages = []

    system_prompt = payload.get("system")
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    for message in payload.get("messages", []):
        role = message.get("role")
        content = message.get("content")
        if not isinstance(content, list):
            raise HTTPException(status_code=400, detail="Invalid content format")
        messages.append({
            "role": role,
            "content": _collapse_content(content),
        })

    openai_payload = {
        "model": upstream_model,
        "messages": messages,
        "stream": payload.get("stream", False),
    }

    if "max_tokens" in payload:
        openai_payload["max_completion_tokens"] = payload["max_tokens"]
    if "temperature" in payload:
        openai_payload["temperature"] = payload["temperature"]
    if "metadata" in payload:
        openai_payload["metadata"] = payload["metadata"]

    return openai_payload


def map_stop_reason(openai_reason: Optional[str]) -> Optional[str]:
    mapping = {
        None: None,
        "stop": "end_turn",
        "length": "max_tokens",
        "content_filter": "content_filter"
    }
    return mapping.get(openai_reason, "end_turn")


def openai_response_to_anthropic(response: Dict, proxy_model: str) -> Dict:
    choices = response.get("choices", [])
    if not choices:
        raise HTTPException(status_code=502, detail="Upstream response missing choices")
    choice = choices[0]
    message = choice.get("message", {})
    content = message.get("content", "")
    finish_reason = choice.get("finish_reason")

    anthropic_resp = {
        "id": response.get("id", ""),
        "type": "message",
        "role": "assistant",
        "model": proxy_model,
        "stop_reason": map_stop_reason(finish_reason),
        "content": [
            {"type": "text", "text": content}
        ],
        "usage": {
            "input_tokens": response.get("usage", {}).get("prompt_tokens"),
            "output_tokens": response.get("usage", {}).get("completion_tokens"),
        }
    }
    return anthropic_resp


async def openai_stream_to_anthropic(
    upstream_stream: AsyncGenerator[str, None],
    proxy_model: str
) -> AsyncGenerator[str, None]:
    """Convert OpenAI SSE responses to Anthropic-style SSE events."""

    async for line in upstream_stream:
        if not line.startswith("data: "):
            continue
        payload = line[6:]
        if payload.strip() == "[DONE]":
            yield ANTHROPIC_EVENT_TERMINATOR
            return

        chunk = json.loads(payload)
        choices = chunk.get("choices", [])
        if not choices:
            continue
        delta = choices[0].get("delta", {})
        text = delta.get("content")
        finish_reason = choices[0].get("finish_reason")

        if text:
            anthropic_event = {
                "type": "content_block_delta",
                "index": 0,
                "delta": {
                    "type": "text_delta",
                    "text": text,
                },
                "model": proxy_model,
            }
            yield f"event: content_block_delta\n" f"data: {json.dumps(anthropic_event)}\n\n"

        if finish_reason:
            stop_event = {
                "type": "message_stop",
                "stop_reason": map_stop_reason(finish_reason),
                "model": proxy_model,
            }
            yield f"event: message_stop\n" f"data: {json.dumps(stop_event)}\n\n"
            yield ANTHROPIC_EVENT_TERMINATOR
            return

    # If the upstream stream completes without explicit finish
    final_stop = {
        "type": "message_stop",
        "stop_reason": "end_turn",
        "model": proxy_model,
    }
    yield f"event: message_stop\n" f"data: {json.dumps(final_stop)}\n\n"
    yield ANTHROPIC_EVENT_TERMINATOR


async def iterate_openai_stream(response) -> AsyncGenerator[str, None]:
    async for line in response.aiter_lines():
        yield line + "\n"


def anthropic_error_from_openai(error: Dict) -> Dict:
    openai_error = error.get("error", {})
    oa_type = openai_error.get("type", "api_error")
    mapping = {
        "invalid_api_key": "authentication_error",
        "insufficient_quota": "rate_limit_error",
        "rate_limit_exceeded": "rate_limit_error",
        "model_not_found": "invalid_request_error",
    }
    return {
        "type": "error",
        "error": {
            "type": mapping.get(oa_type, "api_error"),
            "message": openai_error.get("message", "Upstream error"),
        },
    }


def make_anthropic_test_message(user_prompt: str) -> Dict:
    timestamp = int(time.time())
    return {
        "id": f"msg_{timestamp}",
        "role": "assistant",
        "model": "test",
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": user_prompt}]
    }
