# LM Studio v1 REST API — Reference

Base: `http://localhost:1234` (default). Auth via `Authorization: Bearer $LM_API_TOKEN` (optional).

---

## Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/models` | GET | List available models with capabilities |
| `/api/v1/models/load` | POST | Load a model (set context length, flash attention, etc.) |
| `/api/v1/models/unload` | POST | Unload a model |
| `/api/v1/models/download` | POST | Download model from LM Studio catalog |
| `/api/v1/models/download/status/{job_id}` | GET | Track download progress |
| `/api/v1/chat` | POST | Chat (stateful, supports reasoning control + MCP + images) |

---

## `/api/v1/chat` — Full Request

```json
{
  "model": "google/gemma-4-26b-a4b",
  "input": "Hello!",                          // string or array of {type, content/data_url}
  "system_prompt": "You are...",
  "temperature": 0.3,
  "max_output_tokens": 4096,
  "reasoning": "off",                         // off | low | medium | high | on
  "context_length": 32768,
  "stream": false,
  "store": true,                              // stateful — returns response_id
  "previous_response_id": "resp_abc...",      // continue a conversation
  "integrations": []                          // MCP servers
}
```

### Image input (for Vision models)

```json
{
  "model": "google/gemma-4-26b-a4b",
  "input": [
    { "type": "text", "content": "Describe this image" },
    { "type": "image", "data_url": "data:image/png;base64,..." }
  ]
}
```

### Reasoning control

| Value | Effect |
|---|---|
| `"off"` | No chain-of-thought — fastest, best for simple tasks |
| `"low"` | Minimal reasoning |
| `"medium"` | Balanced |
| `"high"` | Deep reasoning — best for planner, critic, contradiction |
| `"on"` | Model default |

Will error if model does not support reasoning control.

---

## Response Format

```json
{
  "model_instance_id": "google/gemma-4-26b-a4b",
  "output": [
    { "type": "reasoning", "content": "..." },
    { "type": "tool_call", "tool": "...", "arguments": {}, "output": "..." },
    { "type": "message", "content": "..." }
  ],
  "stats": {
    "input_tokens": 329,
    "total_output_tokens": 268,
    "reasoning_output_tokens": 5,
    "tokens_per_second": 43.73,
    "time_to_first_token_seconds": 0.781,
    "model_load_time_seconds": 0.0
  },
  "response_id": "resp_abc..."       // present when store: true
}
```

Output types: `message`, `reasoning`, `tool_call`, `invalid_tool_call`.

---

## Streaming Events (SSE)

Set `"stream": true`. Events arrive as SSE named events.

| Event | When |
|---|---|
| `chat.start` | Stream started |
| `model_load.start` / `.progress` / `.end` | Model loading (if not already loaded) |
| `prompt_processing.start` / `.progress` / `.end` | Prompt ingestion |
| `reasoning.start` / `.delta` / `.end` | Thinking tokens |
| `tool_call.start` / `.arguments` / `.success` / `.failure` | Tool execution |
| `message.start` / `.delta` / `.end` | Output text |
| `error` | Something went wrong |
| `chat.end` | Final aggregated result |

---

## Model Management

### Load a model

```json
POST /api/v1/models/load
{
  "model": "google/gemma-4-26b-a4b",
  "context_length": 131072,
  "flash_attention": true,
  "offload_kv_cache_to_gpu": true,
  "num_experts": 4,
  "echo_load_config": true
}
```

### Download a model

```json
POST /api/v1/models/download
{ "model": "google/gemma-4-26b-a4b" }

→ { "job_id": "..." }

GET /api/v1/models/download/status/{job_id}
→ { "status": "downloading", "progress": 0.65 }
```

### List models with capabilities

`GET /api/v1/models` returns per-model:
- `type`: `"llm"` | `"embedding"` | `"vlm"`
- `capabilities.vision`: bool
- `capabilities.trained_for_tool_use`: bool
- `format`: `"gguf"` | `"mlx"`
- `max_context_length`: number
- `quantization.name`: `"Q4_K_M"` etc.
- `loaded_instances[].config.context_length`: current loaded context length

---

## Stateful Chats

First request returns `response_id`. Pass it as `previous_response_id` in the next request. LM Studio stores conversation history server-side — you don't resend it.

```json
// Turn 1
{ "input": "My name is Per.", "store": true }
→ { "response_id": "resp_abc" }

// Turn 2
{ "input": "What is my name?", "previous_response_id": "resp_abc" }
→ { ... "output": [{"content": "Per"}] }
```

Set `"store": false` for stateless one-off requests.

---

## API Comparison

| Feature | v1 `/api/v1/chat` | OpenAI `/v1/chat/completions` |
|---|---|---|
| Reasoning control | ✅ `off\|low\|med\|high\|on` | ❌ |
| Stateful | ✅ `response_id` | ❌ |
| MCP support | ✅ | ❌ |
| Images | ✅ `data_url` | ✅ via OpenAI format |
| Custom tools | ❌ | ✅ `tools` param |
| Model load streaming | ✅ events | ❌ |
| Prompt processing progress | ✅ events | ❌ |
| Stats (tok/s, TTFT) | ✅ | ❌ |
| `context_length` per request | ✅ | ❌ |
