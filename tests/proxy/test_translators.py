import asyncio

import pytest

from proxy.translators.anthropic import (
    anthropic_request_to_openai,
    openai_response_to_anthropic,
)


def test_anthropic_request_to_openai_basic():
    payload = {
        "system": "You are helpful",
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": "Hello"}],
            }
        ],
        "max_tokens": 64,
        "temperature": 0.2,
    }

    translated = anthropic_request_to_openai(payload, "gpt-4.1")
    assert translated["model"] == "gpt-4.1"
    assert translated["messages"][0]["role"] == "system"
    assert translated["messages"][1]["content"] == "Hello"
    assert translated["max_completion_tokens"] == 64


def test_openai_response_to_anthropic():
    payload = {
        "id": "chatcmpl-123",
        "choices": [
            {
                "message": {"content": "Response"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
    }

    anthropic = openai_response_to_anthropic(payload, "claude-sonnet")
    assert anthropic["content"][0]["text"] == "Response"
    assert anthropic["stop_reason"] == "end_turn"
    assert anthropic["usage"]["input_tokens"] == 10
