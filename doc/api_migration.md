# Complete Guide: Proxying Between OpenAI and Anthropic APIs

This comprehensive report covers API translation between OpenAI-compatible and Anthropic formats, with special attention to Claude Code integration.[1][2][3]

## Executive Summary

API proxying enables using OpenAI models with Anthropic clients (like Claude Code) or vice versa by translating request/response formats at a middleware layer. This requires understanding structural differences, implementing bidirectional transformation logic, and handling streaming, authentication, and model mapping.[4][5][6][1]

## API Format Differences Overview

### Request Structure Comparison

| Component | OpenAI | Anthropic |
|-----------|--------|-----------|
| Message parameter | `input` (string/array) | `messages` (required array) |
| Token limit | `max_output_tokens` (optional) | `max_tokens` (required) |
| System prompt | `instructions` | `system` |
| Streaming flag | `stream: true` | `stream: true` |
| Authentication | `Authorization: Bearer` | `x-api-key` |

### Response Structure Comparison

| Component | OpenAI | Anthropic |
|-----------|--------|-----------|
| Content location | Nested in `output` array | Direct `content` array |
| Text type | `output_text` | `text` |
| Stop reason | Inside message object | Top-level `stop_reason` |
| Token tracking | `input_tokens`, `output_tokens` | `input_tokens`, `output_tokens` |

## Proxy Architecture

### Core Components

**Translation Layer**: Converts request/response formats bidirectionally.[5][4]

**Model Mapper**: Maps model names between providers (e.g., `claude-sonnet-4-5` → `gpt-4.1`).[1]

**Authentication Handler**: Manages different auth mechanisms (API keys vs Bearer tokens).[7][3]

**Streaming Translator**: Transforms SSE events between formats.[6][4]

**Error Handler**: Normalizes error responses across providers.[5]

## Data Flow Diagrams

### Standard Request Flow: OpenAI Format → Anthropic Backend

```
┌──────────┐      ┌───────────────┐      ┌────────────────┐      ┌──────────┐
│  Client  │─────▶│ Proxy Server  │─────▶│  Translation   │─────▶│ Anthropic│
│ (OpenAI) │      │ (Port 8082)   │      │     Layer      │      │   API    │
└──────────┘      └───────────────┘      └────────────────┘      └──────────┘
     │                    │                       │                     │
     │ 1. OpenAI         │ 2. Extract params     │ 3. Transform        │
     │    Request        │    & model name       │    to Anthropic     │
     │                   │                       │    format           │
     │                   │                       │                     │
     │◀──────────────────┴───────────────────────┴─────────────────────┤
     │ 6. OpenAI Response (transformed back)                           │
```

### Reverse Flow: Anthropic Format → OpenAI Backend

```
┌──────────┐      ┌───────────────┐      ┌────────────────┐      ┌──────────┐
│  Claude  │─────▶│ Proxy Server  │─────▶│  Translation   │─────▶│  OpenAI  │
│   Code   │      │ (Port 8082)   │      │     Layer      │      │   API    │
└──────────┘      └───────────────┘      └────────────────┘      └──────────┘
     │                    │                       │                     │
     │ 1. Anthropic      │ 2. Extract messages   │ 3. Transform        │
     │    Request        │    & max_tokens       │    to OpenAI        │
     │    (messages)     │                       │    format           │
     │                   │                       │                     │
     │◀──────────────────┴───────────────────────┴─────────────────────┤
     │ 6. Anthropic Response (transformed back)                        │
```

## Implementation: Anthropic to OpenAI Proxy

### Request Transformation Logic

**Input**: Anthropic Messages API request[1]
**Output**: OpenAI Chat Completions request

```python
def anthropic_to_openai_request(anthropic_req):
    """Transform Anthropic request to OpenAI format"""
    
    # Extract messages array
    messages = anthropic_req.get("messages", [])
    
    # Transform message format
    openai_messages = []
    for msg in messages:
        openai_messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })
    
    # Map model names
    model = map_model_anthropic_to_openai(anthropic_req.get("model"))
    
    # Build OpenAI request
    openai_req = {
        "model": model,
        "messages": openai_messages,
        "max_tokens": anthropic_req.get("max_tokens"),
        "temperature": anthropic_req.get("temperature", 1.0),
        "stream": anthropic_req.get("stream", False)
    }
    
    # Handle system prompt
    if "system" in anthropic_req:
        openai_messages.insert(0, {
            "role": "system",
            "content": anthropic_req["system"]
        })
    
    return openai_req
```

### Response Transformation Logic

**Input**: OpenAI Chat Completions response
**Output**: Anthropic Messages API response[4][1]

```python
def openai_to_anthropic_response(openai_resp):
    """Transform OpenAI response to Anthropic format"""
    
    choice = openai_resp["choices"][0]
    message = choice["message"]
    
    anthropic_resp = {
        "id": f"msg_{openai_resp['id']}",
        "type": "message",
        "role": "assistant",
        "content": [
            {
                "type": "text",
                "text": message["content"]
            }
        ],
        "model": openai_resp["model"],
        "stop_reason": map_finish_reason(choice["finish_reason"]),
        "usage": {
            "input_tokens": openai_resp["usage"]["prompt_tokens"],
            "output_tokens": openai_resp["usage"]["completion_tokens"]
        }
    }
    
    return anthropic_resp

def map_finish_reason(openai_reason):
    """Map OpenAI finish reasons to Anthropic"""
    mapping = {
        "stop": "end_turn",
        "length": "max_tokens",
        "content_filter": "stop_sequence"
    }
    return mapping.get(openai_reason, "end_turn")
```

### Model Mapping

```python
MODEL_MAPPING = {
    # Anthropic -> OpenAI
    "claude-3-5-haiku-20241022": "gpt-4.1-mini",
    "claude-sonnet-4-5-20250929": "gpt-4.1",
    "claude-3-7-sonnet-20250219": "gpt-4.1",
    "claude-4-0-opus-20250514": "gpt-4.1",
    
    # OpenAI -> Anthropic (reverse mapping)
    "gpt-4.1": "claude-sonnet-4-5-20250929",
    "gpt-4.1-mini": "claude-3-5-haiku-20241022",
    "gpt-4o": "claude-sonnet-4-5-20250929"
}

def map_model_anthropic_to_openai(anthropic_model):
    """Map Anthropic model names to OpenAI equivalents"""
    return MODEL_MAPPING.get(anthropic_model, "gpt-4.1")
```

## Streaming Translation

### Anthropic SSE → OpenAI SSE

```python
async def stream_openai_to_anthropic(openai_stream):
    """Transform OpenAI streaming events to Anthropic format"""
    
    # Track content index
    content_index = 0
    
    async for chunk in openai_stream:
        if chunk.choices[0].delta.content:
            # Transform to Anthropic delta event
            anthropic_event = {
                "type": "content_block_delta",
                "index": content_index,
                "delta": {
                    "type": "text_delta",
                    "text": chunk.choices[0].delta.content
                }
            }
            
            yield f"event: content_block_delta\n"
            yield f"data: {json.dumps(anthropic_event)}\n\n"
        
        # Handle finish
        if chunk.choices[0].finish_reason:
            yield f"event: message_stop\n"
            yield f"data: {json.dumps({'type': 'message_stop'})}\n\n"
```

### OpenAI SSE → Anthropic SSE

```python
async def stream_anthropic_to_openai(anthropic_stream):
    """Transform Anthropic streaming events to OpenAI format"""
    
    async for line in anthropic_stream:
        if line.startswith("data: "):
            event_data = json.loads(line[6:])
            
            if event_data["type"] == "content_block_delta":
                # Transform to OpenAI delta format
                openai_chunk = {
                    "id": "chatcmpl-123",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "gpt-4.1",
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "content": event_data["delta"]["text"]
                        },
                        "finish_reason": None
                    }]
                }
                
                yield f"data: {json.dumps(openai_chunk)}\n\n"
            
            elif event_data["type"] == "message_stop":
                # Send final chunk
                final_chunk = {
                    "id": "chatcmpl-123",
                    "choices": [{
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop"
                    }]
                }
                yield f"data: {json.dumps(final_chunk)}\n\n"
                yield "data: [DONE]\n\n"
```

## Claude Code Integration

### Configuration Requirements

Claude Code uses the Anthropic Messages API format and can be redirected to a proxy using environment variables.[8][9][3][10]

**Key environment variables**:[3][10][8]
- `ANTHROPIC_BASE_URL`: Custom API endpoint (default: `https://api.anthropic.com`)
- `ANTHROPIC_API_KEY`: Authentication token forwarded to proxy

### Claude Code Data Flow with OpenAI Backend

```
┌─────────────┐         ┌──────────────────┐         ┌─────────────────┐         ┌──────────┐
│             │         │                  │         │                 │         │          │
│ Claude Code │────────▶│  Proxy Server    │────────▶│  Transformation │────────▶│  OpenAI  │
│    CLI      │         │  (localhost:8082)│         │     Engine      │         │   API    │
│             │         │                  │         │                 │         │          │
└─────────────┘         └──────────────────┘         └─────────────────┘         └──────────┘
      │                         │                            │                         │
      │ 1. Anthropic           │ 2. Intercept               │ 3. Convert             │
      │    Messages API        │    request                 │    messages[] to       │
      │    format with         │    (validates              │    OpenAI format       │
      │    messages[]          │    x-api-key)              │    (map model)         │
      │                        │                            │                        │
      │                        │ 4. Forward OpenAI request ─────────────────────────▶│
      │                        │                            │                        │
      │                        │◀────────────────────────────────── 5. OpenAI resp ──│
      │                        │                            │                        │
      │                        │ 6. Transform back          │                        │
      │                        │    to Anthropic format     │                        │
      │◀──────────────────────────── 7. Return Anthropic response                    │
```

### Proxy Setup for Claude Code

**Step 1**: Install proxy server[1]

```bash
# Using claude-code-proxy
git clone https://github.com/1rgs/claude-code-proxy.git
cd claude-code-proxy
```

**Step 2**: Configure environment[1]

```bash
# .env file
OPENAI_API_KEY="sk-..."
PREFERRED_PROVIDER="openai"
BIG_MODEL="gpt-4.1"           # Maps to Claude Sonnet
SMALL_MODEL="gpt-4.1-mini"    # Maps to Claude Haiku
```

**Step 3**: Start proxy[1]

```bash
# Run proxy on port 8082
uv run uvicorn server:app --host 0.0.0.0 --port 8082
```

**Step 4**: Configure Claude Code[8][3]

```bash
# Set custom endpoint
export ANTHROPIC_BASE_URL=http://localhost:8082
export ANTHROPIC_API_KEY=dummy-key  # Forwarded to proxy

# Run Claude Code
claude "Write a Python hello world"
```

### Alternative Configuration: Settings File

Create `~/.claude/settings.json`:[9][10]

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://localhost:8082",
    "ANTHROPIC_API_KEY": "dummy-key"
  },
  "model": "claude-sonnet-4-5-20250929"
}
```

### Model Mapping for Claude Code

Claude Code requests models like `claude-sonnet-4-5-20250929` or `claude-3-5-haiku`. The proxy must map these to OpenAI equivalents:[1]

```python
CLAUDE_CODE_MODEL_MAPPING = {
    # Sonnet variants (high capability)
    "claude-sonnet-4-5-20250929": "gpt-4.1",
    "claude-3-7-sonnet-20250219": "gpt-4.1",
    "claude-opus-4-0-20250514": "gpt-4.1",
    
    # Haiku variants (fast, economical)
    "claude-3-5-haiku-20241022": "gpt-4.1-mini",
    "claude-3-haiku-20240307": "gpt-4.1-mini"
}
```

## Extended Thinking Support

### Challenge with Extended Thinking

Claude Code can request **Extended Thinking** mode, which includes special `thinking` content blocks. OpenAI doesn't natively support this format, requiring special handling.[11][12][13]

### Extended Thinking Request Detection

```python
def has_extended_thinking(anthropic_req):
    """Check if request uses extended thinking"""
    return "thinking" in anthropic_req and \
           anthropic_req["thinking"].get("type") == "enabled"

def transform_extended_thinking_request(anthropic_req):
    """Handle extended thinking requests"""
    
    if has_extended_thinking(anthropic_req):
        # Extract thinking budget
        budget = anthropic_req["thinking"].get("budget_tokens", 5000)
        
        # Add instruction to OpenAI system prompt
        system_addition = (
            f"\n\nYou have {budget} tokens to think through "
            "your response step-by-step before answering. "
            "Show your reasoning process."
        )
        
        # Modify OpenAI request
        openai_req["messages"].insert(0, {
            "role": "system",
            "content": system_addition
        })
    
    return openai_req
```

### Extended Thinking Response Simulation

```python
def simulate_extended_thinking_response(openai_resp):
    """Simulate Anthropic extended thinking format"""
    
    content_text = openai_resp["choices"][0]["message"]["content"]
    
    # Attempt to split thinking from answer
    if "Step-by-step:" in content_text or "Reasoning:" in content_text:
        parts = content_text.split("\n\n", 1)
        thinking_part = parts[0] if len(parts) > 1 else ""
        answer_part = parts[1] if len(parts) > 1 else content_text
        
        # Build Anthropic response with thinking block
        anthropic_resp = {
            "content": [
                {
                    "type": "thinking",
                    "thinking": thinking_part
                },
                {
                    "type": "text",
                    "text": answer_part
                }
            ],
            "usage": {
                "input_tokens": openai_resp["usage"]["prompt_tokens"],
                "output_tokens": openai_resp["usage"]["completion_tokens"],
                "thinking_tokens": len(thinking_part.split()) * 1.3  # Estimate
            }
        }
    else:
        # Standard response without thinking
        anthropic_resp = standard_response_transform(openai_resp)
    
    return anthropic_resp
```

### Extended Thinking Streaming

```python
async def stream_with_thinking_simulation(openai_stream):
    """Stream with simulated thinking blocks"""
    
    buffer = ""
    in_thinking = True
    
    async for chunk in openai_stream:
        delta_text = chunk.choices[0].delta.content or ""
        buffer += delta_text
        
        # Detect transition from thinking to answer
        if in_thinking and "\n\nAnswer:" in buffer:
            thinking_text = buffer.split("\n\nAnswer:")[0]
            
            # Send thinking block
            yield format_anthropic_event("content_block_start", {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "thinking"}
            })
            
            yield format_anthropic_event("content_block_delta", {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "thinking_delta", "thinking": thinking_text}
            })
            
            yield format_anthropic_event("content_block_stop", {
                "type": "content_block_stop",
                "index": 0
            })
            
            # Start text block
            in_thinking = False
            buffer = buffer.split("\n\nAnswer:")[1]
        
        # Stream regular text
        if not in_thinking:
            yield format_anthropic_event("content_block_delta", {
                "type": "content_block_delta",
                "index": 1,
                "delta": {"type": "text_delta", "text": delta_text}
            })
```

## Complete Proxy Implementation

### Minimal FastAPI Proxy Server

```python
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
import httpx
import json

app = FastAPI()

OPENAI_API_KEY = "sk-..."
OPENAI_BASE_URL = "https://api.openai.com/v1"

@app.post("/v1/messages")
async def proxy_messages(request: Request):
    """Anthropic Messages API endpoint"""
    
    # Parse Anthropic request
    anthropic_req = await request.json()
    
    # Transform to OpenAI format
    openai_req = anthropic_to_openai_request(anthropic_req)
    
    # Check streaming
    is_streaming = anthropic_req.get("stream", False)
    
    async with httpx.AsyncClient() as client:
        if is_streaming:
            # Handle streaming
            async def stream_generator():
                async with client.stream(
                    "POST",
                    f"{OPENAI_BASE_URL}/chat/completions",
                    json=openai_req,
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                    timeout=60.0
                ) as resp:
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            # Transform to Anthropic format
                            anthropic_line = transform_streaming_line(line)
                            yield anthropic_line
            
            return StreamingResponse(
                stream_generator(),
                media_type="text/event-stream"
            )
        else:
            # Non-streaming
            resp = await client.post(
                f"{OPENAI_BASE_URL}/chat/completions",
                json=openai_req,
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}
            )
            
            openai_resp = resp.json()
            anthropic_resp = openai_to_anthropic_response(openai_resp)
            
            return anthropic_resp

@app.get("/v1/models")
async def list_models():
    """List available models (Anthropic format)"""
    return {
        "data": [
            {"id": "claude-sonnet-4-5-20250929", "type": "model"},
            {"id": "claude-3-5-haiku-20241022", "type": "model"}
        ]
    }
```

## Authentication Handling

### Anthropic → OpenAI Authentication

```python
def extract_anthropic_auth(request: Request):
    """Extract Anthropic API key from request"""
    
    # Check x-api-key header
    api_key = request.headers.get("x-api-key")
    
    # Check Authorization header
    if not api_key:
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            api_key = auth[7:]
    
    return api_key

def forward_to_openai(anthropic_key):
    """Map Anthropic key to OpenAI key"""
    
    # Simple key mapping (or use key database)
    KEY_MAPPING = {
        "anthropic-key-1": "sk-openai-key-1",
        "anthropic-key-2": "sk-openai-key-2"
    }
    
    return KEY_MAPPING.get(anthropic_key, OPENAI_API_KEY)
```

## Error Handling

### Error Response Translation

```python
def translate_error_response(openai_error):
    """Convert OpenAI errors to Anthropic format"""
    
    error_mapping = {
        "invalid_api_key": "authentication_error",
        "rate_limit_exceeded": "rate_limit_error",
        "model_not_found": "invalid_request_error"
    }
    
    openai_type = openai_error.get("error", {}).get("type")
    anthropic_type = error_mapping.get(openai_type, "api_error")
    
    return {
        "type": "error",
        "error": {
            "type": anthropic_type,
            "message": openai_error.get("error", {}).get("message", "Unknown error")
        }
    }
```

## Testing the Proxy

### Test with cURL

```bash
# Test Anthropic format request
curl -X POST http://localhost:8082/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: dummy-key" \
  -d '{
    "model": "claude-sonnet-4-5-20250929",
    "max_tokens": 100,
    "messages": [
      {"role": "user", "content": "Say hello"}
    ]
  }'
```

### Test with Claude Code

```bash
# Configure Claude Code to use proxy
export ANTHROPIC_BASE_URL=http://localhost:8082
export ANTHROPIC_API_KEY=dummy-key

# Run test command
claude "Write a Python function to calculate factorial"
```

## Performance Considerations

### Latency Overhead

**Translation overhead**: 2-5ms per request.[6]

**Network hop**: 10-50ms depending on proxy location.[6]

**Streaming buffering**: Minimal (<1ms per chunk).[6]

### Optimization Strategies

**Connection pooling**: Reuse HTTP connections to upstream APIs.[6]

**Response caching**: Cache non-streaming responses for identical requests.[5][6]

**Async processing**: Use async/await for concurrent request handling.[1]

**Model preloading**: Cache model mapping tables in memory.[1]

## Security Considerations

### API Key Management

**Never log API keys** in proxy server logs.[5][6]

**Use environment variables** for credentials, not hardcoded values.[3][1]

**Implement key rotation** mechanisms for production deployments.[5]

**Rate limiting** per client to prevent abuse.[14][6]

### Request Validation

```python
def validate_anthropic_request(req_data):
    """Validate incoming Anthropic request"""
    
    # Check required fields
    if "messages" not in req_data:
        raise ValueError("messages field is required")
    
    if "max_tokens" not in req_data:
        raise ValueError("max_tokens field is required")
    
    # Validate message structure
    for msg in req_data["messages"]:
        if "role" not in msg or "content" not in msg:
            raise ValueError("Invalid message format")
    
    # Validate token limits
    max_tokens = req_data["max_tokens"]
    if max_tokens < 1 or max_tokens > 200000:
        raise ValueError("max_tokens must be between 1 and 200000")
    
    return True
```

## Production Deployment

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8082

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8082"]
```

### Docker Compose Configuration

```yaml
version: '3.8'

services:
  anthropic-proxy:
    build: .
    ports:
      - "8082:8082"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - PREFERRED_PROVIDER=openai
      - BIG_MODEL=gpt-4.1
      - SMALL_MODEL=gpt-4.1-mini
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8082/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Monitoring and Logging

```python
import logging
from prometheus_client import Counter, Histogram

# Metrics
request_counter = Counter('proxy_requests_total', 'Total requests', ['provider', 'model'])
response_time = Histogram('proxy_response_seconds', 'Response time')

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log and monitor requests"""
    
    start_time = time.time()
    
    # Log request
    logging.info(f"Request: {request.method} {request.url.path}")
    
    # Process request
    response = await call_next(request)
    
    # Calculate duration
    duration = time.time() - start_time
    
    # Record metrics
    response_time.observe(duration)
    
    # Log response
    logging.info(f"Response: {response.status_code} ({duration:.3f}s)")
    
    return response
```

## Troubleshooting Common Issues

### Issue 1: Authentication Failures

**Symptom**: `authentication_error` responses from proxy.[5]

**Solution**: Verify API keys are correctly configured and forwarded:[3]

```bash
# Check environment variables
echo $ANTHROPIC_API_KEY
echo $OPENAI_API_KEY

# Test authentication
curl -H "x-api-key: $ANTHROPIC_API_KEY" http://localhost:8082/v1/models
```

### Issue 2: Streaming Not Working

**Symptom**: Claude Code hangs or shows incomplete responses.[1]

**Solution**: Ensure SSE headers are correctly set:[6]

```python
return StreamingResponse(
    stream_generator(),
    media_type="text/event-stream",
    headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no"  # Disable nginx buffering
    }
)
```

### Issue 3: Model Not Found Errors

**Symptom**: `invalid_request_error` with model name issues.[1]

**Solution**: Add comprehensive model mapping:[1]

```python
# Add fallback mapping
if model not in MODEL_MAPPING:
    if "sonnet" in model.lower():
        return "gpt-4.1"
    elif "haiku" in model.lower():
        return "gpt-4.1-mini"
    else:
        return "gpt-4.1"  # Default fallback
```

## Conclusion

Proxying between OpenAI and Anthropic APIs requires careful attention to request/response format differences, streaming event translation, authentication mechanisms, and model mapping. For Claude Code specifically, environment variables like `ANTHROPIC_BASE_URL` enable seamless integration with OpenAI backends while maintaining the familiar Anthropic API interface. Extended Thinking support requires special handling to simulate Anthropic's multi-block response format. Production deployments should include monitoring, error handling, and security measures to ensure reliable operation.[10][12][14][11][4][8][3][5][6][1]

[1](https://github.com/1rgs/claude-code-proxy)
[2](https://jimmysong.io/en/ai/copilot-api-proxy/)
[3](https://xaixapi.com/en/docs/tools/claude-code/)
[4](https://github.com/maxnowack/anthropic-proxy)
[5](https://www.truefoundry.com/blog/llm-gateway)
[6](https://api7.ai/learning-center/api-gateway-guide/api-gateway-proxy-llm-requests)
[7](https://www.reddit.com/r/LocalLLaMA/comments/1mfuu40/gatewayproxy_for_claudecode_to_openai_api/)
[8](https://www.reddit.com/r/ClaudeAI/comments/1l88015/how_to_set_custom_base_url_in_claude_code_like/)
[9](https://github.com/zed-industries/zed/discussions/37842)
[10](https://docs.claude.com/en/docs/claude-code/settings)
[11](https://docs.aws.amazon.com/bedrock/latest/userguide/claude-messages-extended-thinking.html)
[12](https://www.anthropic.com/news/visible-extended-thinking)
[13](https://www.cometapi.com/how-to-use-claude-4-extended-thinking/)
[14](https://tyk.io/docs/ai-management/ai-studio/proxy/)
[15](https://dev.to/jeffdev03/how-to-create-a-simple-openai-api-proxy-with-steps-2d1f)
[16](https://www.lunar.dev/flows/switching-requests-from-the-openai-api-to-anthropics-claude-apis)
[17](https://community.openai.com/t/introduction-openai-api-proxy/920452)
[18](https://docs.litellm.ai/docs/providers/anthropic)
[19](https://github.com/anthropics/claude-code/issues/216)
[20](https://www.lasso.security/blog/llm-gateway)
[21](https://docs.openpipe.ai/features/chat-completions/anthropic)
[22](https://www.anthropic.com/engineering/claude-code-best-practices)
[23](https://konghq.com/products/kong-ai-gateway)