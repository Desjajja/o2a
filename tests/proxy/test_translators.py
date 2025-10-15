import asyncio

import pytest

from proxy.translators.anthropic import (
    anthropic_request_to_openai,
    openai_response_to_anthropic,
)
import uuid


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
    assert translated["max_tokens"] == 64


def test_anthropic_request_accepts_string_message_content():
    payload = {
        "messages": [
            {"role": "user", "content": "Hello, world"}
        ],
        "max_tokens": 16,
    }

    translated = anthropic_request_to_openai(payload, "gpt-4o-mini")
    assert translated["messages"][0]["role"] == "user"
    assert translated["messages"][0]["content"] == "Hello, world"
    assert translated["max_tokens"] == 16


def test_anthropic_request_allows_block_system_prompt():
    payload = {
        "system": [{"type": "text", "text": "Be terse"}],
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": "Ping"}]}
        ],
    }

    translated = anthropic_request_to_openai(payload, "gpt-4.1")
    assert translated["messages"][0]["role"] == "system"
    assert translated["messages"][0]["content"] == "Be terse"


def test_maps_top_p_and_stop_sequences_and_schema():
    payload = {
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": "Say hello"}]}
        ],
        "top_p": 0.9,
        "stop_sequences": ["\n\n"],
        "schema": {
            "name": "hello_response",
            "type": "object",
            "properties": {"greeting": {"type": "string"}},
            "required": ["greeting"],
        },
    }

    translated = anthropic_request_to_openai(payload, "gpt-4o-mini")
    assert translated["top_p"] == 0.9
    assert translated["stop"] == ["\n\n"]
    assert translated["response_format"]["type"] == "json_schema"
    assert translated["response_format"]["schema"]["name"] == "hello_response"


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
    assert anthropic["stop_sequence"] is None
    assert anthropic["content"][0]["citations"] is None


def test_openai_response_to_anthropic_collapses_list_content():
    payload = {
        "id": "chatcmpl-456",
        "choices": [
            {
                "message": {
                    "content": [
                        {"type": "text", "text": "Hi"},
                        {"type": "text", "text": " there"},
                    ]
                },
                "finish_reason": "length",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 2},
    }

    anthropic = openai_response_to_anthropic(payload, "claude-sonnet")
    assert anthropic["content"][0]["text"] == "Hi there"
    assert anthropic["stop_reason"] == "max_tokens"


def test_openai_response_generates_uuid_when_missing_id():
    payload = {
        # intentionally omit 'id'
        "choices": [
            {"message": {"content": "Hello"}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 1},
    }

    anthropic = openai_response_to_anthropic(payload, "claude-sonnet")
    assert "id" in anthropic and isinstance(anthropic["id"], str) and anthropic["id"]
    # Validate UUID format
    uuid_obj = uuid.UUID(anthropic["id"])  # will raise if invalid
    assert str(uuid_obj) == anthropic["id"].lower()
