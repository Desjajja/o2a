from __future__ import annotations

import json
import logging
import time
from typing import AsyncGenerator, Dict, Iterable, List, Optional, Union
from uuid import uuid4

from fastapi import HTTPException

ANTHROPIC_EVENT_TERMINATOR = "data: [DONE]\n\n"

logger = logging.getLogger(__name__)


def _collapse_content(blocks: Iterable[Dict]) -> str:
    text_parts: List[str] = []
    for block in blocks:
        if block.get("type") == "text" and "text" in block:
            text_parts.append(block["text"])
    return "".join(text_parts)


def _collapse_openai_message_content(content: Union[str, List[Dict], None]) -> str:
    """Normalise OpenAI message content which may be a string or list of parts."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return _collapse_content(content)
    return str(content)


def anthropic_request_to_openai(payload: Dict, upstream_model: str) -> Dict:
    messages = []

    system_prompt = payload.get("system")
    if system_prompt:
        # Anthropic may pass system as string or content blocks
        if isinstance(system_prompt, list):
            system_text = _collapse_content(system_prompt)
        else:
            system_text = str(system_prompt)
        messages.append({"role": "system", "content": system_text})

    for message in payload.get("messages", []):
        role = message.get("role")
        content = message.get("content")
        # Accept either string content or list of content blocks per Anthropic spec
        if isinstance(content, str):
            content_text = content
        elif isinstance(content, list):
            content_text = _collapse_content(content)
        else:
            logger.warning(
                "Invalid message content type: %s", type(content).__name__
            )
            raise HTTPException(status_code=400, detail="Invalid content format")
        messages.append({
            "role": role,
            "content": content_text,
        })

    openai_payload = {
        "model": upstream_model,
        "messages": messages,
        "stream": payload.get("stream", False),
    }

    if "max_tokens" in payload:
        # OpenAI chat completions expects `max_tokens`
        openai_payload["max_tokens"] = payload["max_tokens"]
    if "temperature" in payload:
        openai_payload["temperature"] = payload["temperature"]
    if "top_p" in payload:
        openai_payload["top_p"] = payload["top_p"]
    if "metadata" in payload:
        openai_payload["metadata"] = payload["metadata"]
    # Map Anthropic stop control to OpenAI `stop`
    if "stop_sequences" in payload:
        openai_payload["stop"] = payload["stop_sequences"]
    # Map Anthropic structured output schema to OpenAI `response_format`
    if "schema" in payload:
        openai_payload["response_format"] = {
            "type": "json_schema",
            "schema": payload["schema"],
        }

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
    content = _collapse_openai_message_content(message.get("content"))
    finish_reason = choice.get("finish_reason")

    anthropic_resp = {
        "id": response.get("id") or str(uuid4()),
        "type": "message",
        "role": "assistant",
        "model": proxy_model,
        "stop_reason": map_stop_reason(finish_reason),
        "stop_sequence": None,
        "content": [
            {"type": "text", "text": content, "citations": None}
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
