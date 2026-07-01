"""Free AI API Gateway — routes to OpenRouter free models with circuit-breaker retry chain"""

import os, time, json, asyncio, logging
from typing import Optional
import httpx

logger = logging.getLogger("tangle.gateway")

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
OLLAMA_BASE = "http://localhost:11434"
LMSTUDIO_BASE = os.getenv("LMSTUDIO_BASE_URL", "http://172.20.10.3:1234")

# Verified against https://openrouter.ai/api/v1/models on 2026-06-28.
# Drop entries here only after confirming they are gone from the live API --
# each one in the chain is a retry attempt that costs quota if dead.
# ─────────────────────────────────────────────────────────────
# OpenRouter Free Models — July 2026
# Source: https://openrouter.ai/models?order=newest&max_price=0
# Add new free models here as they appear. Fallback order: Tier 1 → 2 → 3
# ─────────────────────────────────────────────────────────────

OPENROUTER_FREE_MODELS = [
    # ── Tier 1: Best defaults (strong reasoning, coding, long context) ──
    "google/gemma-4-26b-a4b-it:free",                    # MoE, thinking mode, function calling, multimodal (image/video 60s), 262K ctx
    "google/gemma-4-31b-it:free",                         # Larger dense variant, strong multimodal (image), 262K ctx
    "nvidia/nemotron-3-ultra-550b-a55b:free",             # 550B MoE, advanced logic, 1M ctx
    "nvidia/nemotron-3-super-120b-a12b:free",             # 120B MoE, agents + tool use, 1M ctx
    "openai/gpt-oss-120b:free",                           # Open-weight MoE, reasoning + agents, 131K ctx
    "openai/gpt-oss-20b:free",                            # Lighter variant, strong coding, 131K ctx
    "nousresearch/hermes-3-llama-3.1-405b:free",          # Llama 3.1 finetune, roleplay + agents + code, 131K ctx
    "qwen/qwen3-coder:free",                              # Coding specialist, 1M ctx
    "qwen/qwen3-next-80b-a3b-instruct:free",               # Fast, stable, no visible thinking traces, RAG + long dialogue, 262K ctx
    "meta-llama/llama-3.3-70b-instruct:free",             # Meta flagship, multilingual, strong logic, 131K ctx
    "poolside/laguna-m.1:free",                           # Software engineering specialist, 262K ctx
    "poolside/laguna-xs.2:free",                          # Faster compact coding model, 262K ctx
    "openrouter/owl-alpha",                                # Native tool-use, 1M ctx
    # ── Tier 2: Specialists (vision, multi-modal, fast/small, rerank) ──
    "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",  # Uncensored, no moral filters, 33K ctx
    "liquid/lfm-2.5-1.2b-thinking:free",                  # Ultra-light thinking model, logical agents, 33K ctx
    "liquid/lfm-2.5-1.2b-instruct:free",                  # Compact instruction model, simple chat, 33K ctx
    "meta-llama/llama-3.2-3b-instruct:free",              # Small, low-resource text model, 131K ctx
    "nvidia/nemotron-nano-12b-v2-vl:free",                 # Vision default (parsing_engine), multimodal
    "nvidia/llama-nemotron-embed-vl-1b-v2:free",           # Embedding: text+image → vectors for RAG, 131K ctx
    "nvidia/llama-nemotron-rerank-vl-1b-v2:free",          # Reranking: cross-encoder for search result sorting, 10K ctx
    "nvidia/nemotron-3.5-content-safety:free",              # Content safety classifier, 128K ctx
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",   # Perception sub-agent
    "cohere/north-mini-code:free",                          # Agentic coding MoE
]

OLLAMA_CHAT_MODELS = ["llama3.2:3b", "llama3.1:8b", "qwen3:8b", "llama3.2:1b", "phi4-mini:3.8b"]

class FreeGateway:
    # Circuit breaker states
    _CB_CLOSED = "closed"      # Normal operation
    _CB_OPEN = "open"          # Failing fast, not calling provider
    _CB_HALF_OPEN = "half_open"  # Probing with a single request

    def __init__(self):
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")
        self._client = httpx.AsyncClient(timeout=60)
        self._rate_limits = {"openrouter": {"remaining": 50, "reset": time.time() + 86400}}
        self._ollama_available = None
        self._lmstudio_available = None

        # Circuit breaker state per provider
        self._cb: dict[str, dict] = {
            "openrouter": {
                "state": self._CB_CLOSED,
                "failures": 0,
                "opened_at": 0.0,
                "cooldown": 30.0,  # doubles on each open, max 240s
            },
            "gemini": {
                "state": self._CB_CLOSED,
                "failures": 0,
                "opened_at": 0.0,
                "cooldown": 30.0,
            },
            "lmstudio": {
                "state": self._CB_CLOSED,
                "failures": 0,
                "opened_at": 0.0,
                "cooldown": 10.0,  # local — faster recovery
            },
        }

    async def health(self) -> dict:
        """Check health of all providers."""
        health = {
            "openrouter": bool(self.openrouter_key),
            "gemini": bool(self.gemini_key),
            "ollama": await self._check_ollama(),
            "lmstudio": await self._check_lmstudio(),
        }
        # Add circuit breaker status
        for provider, cb in self._cb.items():
            if cb["state"] != self._CB_CLOSED:
                health[f"{provider}_circuit"] = cb["state"]
        return health

    # ── Circuit breaker helpers ─────────────────────────────────

    def _cb_record_success(self, provider: str) -> None:
        """Record a successful call — reset circuit breaker."""
        cb = self._cb.get(provider)
        if not cb:
            return
        if cb["state"] == self._CB_HALF_OPEN:
            logger.info(f"Circuit breaker CLOSED for {provider} (probe succeeded)")
        cb["state"] = self._CB_CLOSED
        cb["failures"] = 0
        cb["cooldown"] = 30.0

    def _cb_record_failure(self, provider: str) -> None:
        """Record a failed call — may open circuit breaker."""
        cb = self._cb.get(provider)
        if not cb:
            return
        cb["failures"] += 1
        if cb["failures"] >= 3:
            cb["state"] = self._CB_OPEN
            cb["opened_at"] = time.time()
            logger.warning(
                f"Circuit breaker OPEN for {provider} "
                f"(cooldown {cb['cooldown']:.0f}s, {cb['failures']} consecutive failures)"
            )

    def _cb_should_allow(self, provider: str) -> bool:
        """Check if the circuit breaker allows a request."""
        cb = self._cb.get(provider)
        if not cb:
            return True
        if cb["state"] == self._CB_CLOSED:
            # Even when closed, check if rate limit is nearly exhausted
            if provider == "openrouter":
                rate = self._rate_limits.get("openrouter", {})
                remaining = rate.get("remaining", 999)
                reset = rate.get("reset", 0)
                if remaining <= 1 and time.time() < reset:
                    logger.warning(f"CircuitBreaker: openrouter rate near zero (remaining={remaining}, reset_in={reset - time.time():.0f}s) — OPENING")
                    cb["state"] = self._CB_OPEN
                    cb["opened_at"] = time.time()
                    cb["cooldown"] = reset - time.time() + 1
                    return False
            return True
        if cb["state"] == self._CB_HALF_OPEN:
            return True  # Allow probe
        # OPEN state — check if cooldown expired
        elapsed = time.time() - cb["opened_at"]
        if elapsed >= cb["cooldown"]:
            cb["state"] = self._CB_HALF_OPEN
            logger.info(f"Circuit breaker HALF_OPEN for {provider} (cooldown expired)")
            return True
        return False

    def _cb_update_rate_from_headers(self, provider: str, headers: dict) -> None:
        """Parse rate-limit headers from OpenRouter response.

        OpenRouter returns per-request headers:
          x-ratelimit-limit       — max requests in current window
          x-ratelimit-remaining   — requests left in current window
          x-ratelimit-reset       — epoch seconds when window resets
        """
        if provider == "openrouter":
            remaining = headers.get("x-ratelimit-remaining")
            reset = headers.get("x-ratelimit-reset")
            limit = headers.get("x-ratelimit-limit")
            if remaining is not None:
                try:
                    self._rate_limits["openrouter"]["remaining"] = int(remaining)
                except (ValueError, TypeError):
                    pass
            if reset is not None:
                try:
                    self._rate_limits["openrouter"]["reset"] = float(reset)
                except (ValueError, TypeError):
                    pass
            if limit is not None:
                try:
                    self._rate_limits["openrouter"]["limit"] = int(limit)
                except (ValueError, TypeError):
                    pass

    async def _check_ollama(self) -> bool:
        """Check if Ollama is running and accessible."""
        if self._ollama_available is not None:
            return self._ollama_available
        try:
            resp = await self._client.get(f"{OLLAMA_BASE}/api/tags", timeout=5)
            self._ollama_available = resp.status_code == 200
            return self._ollama_available
        except Exception:
            self._ollama_available = False
            return False

    async def _check_lmstudio(self) -> bool:
        """Check if LM Studio is running and accessible."""
        if self._lmstudio_available is not None:
            return self._lmstudio_available
        try:
            resp = await self._client.get(f"{LMSTUDIO_BASE}/api/v1/models", timeout=5)
            self._lmstudio_available = resp.status_code == 200
            return self._lmstudio_available
        except Exception:
            self._lmstudio_available = False
            return False

    async def chat(self, model: str, messages: list[dict], agent_context: Optional[dict] = None, tools: Optional[list] = None, reasoning: str = "medium") -> dict:
        errors = []

        if model == "ollama":
            return await self._call_ollama(messages)

        if model.startswith("gemini"):
            if not self.gemini_key:
                return {"error": "GEMINI_API_KEY not set", "provider": "gemini"}
            return await self._call_gemini(model, messages)

        if model.startswith("lmstudio/"):
            model_actual = model.replace("lmstudio/", "")
            return await self._call_lmstudio(model_actual, messages, tools, reasoning)

        if model.startswith("openrouter/"):
            model_actual = model.replace("openrouter/", "")
            return await self._call_openrouter(model_actual, messages, tools)

        return await self._call_openrouter(f"{model}:free", messages, tools)

    async def _call_ollama(self, messages: list[dict]) -> dict:
        try:
            model = "llama3.2:3b"
            resp = await self._client.post(
                f"{OLLAMA_BASE}/api/chat",
                json={"model": model, "messages": messages, "stream": False, "options": {"num_predict": 2048}},
            )
            if resp.status_code != 200:
                return {"error": f"Ollama {resp.status_code}: {resp.text[:200]}", "provider": "ollama"}
            data = resp.json()
            return {
                "provider": "ollama",
                "model": model,
                "content": data.get("message", {}).get("content", ""),
                "finish_reason": "stop",
                "usage": {},
            }
        except Exception as e:
            return {"error": f"Ollama error: {e}", "provider": "ollama"}

    async def _call_openrouter(self, model: str, messages: list[dict], tools: Optional[list] = None) -> dict:
        if not self.openrouter_key:
            return {"error": "OpenRouter API key not set. Set OPENROUTER_API_KEY in .env", "provider": "openrouter"}

        # Circuit breaker check
        if not self._cb_should_allow("openrouter"):
            cb = self._cb["openrouter"]
            remaining_cooldown = cb["cooldown"] - (time.time() - cb["opened_at"])
            return {"error": f"OpenRouter circuit breaker open (cooldown {remaining_cooldown:.0f}s remaining)", "provider": "openrouter"}

        remaining = self._rate_limits["openrouter"]["remaining"]
        if remaining <= 0:
            wait = self._rate_limits["openrouter"]["reset"] - time.time()
            if wait > 0:
                return {"error": f"OpenRouter rate limited (resets in {wait:.0f}s)", "provider": "openrouter"}

        body = {"model": model, "messages": messages, "max_tokens": 4096}
        if tools:
            body["tools"] = tools

        resp = await self._client.post(
            f"{OPENROUTER_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {self.openrouter_key}", "Content-Type": "application/json"},
            json=body,
        )

        # Parse rate-limit headers from OpenRouter
        self._cb_update_rate_from_headers("openrouter", dict(resp.headers))

        if resp.status_code in (429, 503):
            if resp.status_code == 429:
                self._rate_limits["openrouter"]["remaining"] = 0
                # Use Retry-After header if present, else default to 60s
                retry_after = resp.headers.get("retry-after")
                if retry_after:
                    try:
                        self._rate_limits["openrouter"]["reset"] = time.time() + float(retry_after)
                    except (ValueError, TypeError):
                        self._rate_limits["openrouter"]["reset"] = time.time() + 60
                else:
                    self._rate_limits["openrouter"]["reset"] = time.time() + 60
            self._cb_record_failure("openrouter")
            return await self._try_other_free_models(model, messages, tools)

        if resp.status_code != 200:
            self._cb_record_failure("openrouter")
            return await self._try_other_free_models(model, messages, tools)

        # Success — record it
        self._cb_record_success("openrouter")

        data = resp.json()
        choice = data["choices"][0]
        msg = choice["message"]

        result = {
            "provider": "openrouter",
            "model": data.get("model", model),
            "content": msg.get("content") or "",
            "finish_reason": choice.get("finish_reason", "stop"),
            "usage": data.get("usage", {}),
        }

        if msg.get("tool_calls"):
            result["tool_calls"] = msg["tool_calls"]

        return result

    async def _try_other_free_models(self, failed_model: str, messages: list[dict], tools: Optional[list] = None) -> dict:
        for fallback_model in OPENROUTER_FREE_MODELS:
            normalized = fallback_model
            if normalized.startswith("openrouter/"):
                normalized = normalized[len("openrouter/"):]
                normalized = normalized.removesuffix(":free")
            else:
                normalized = normalized.removesuffix(":free")

            # Skip the model that just failed
            failed_normalized = failed_model
            if failed_normalized.startswith("openrouter/"):
                failed_normalized = failed_normalized[len("openrouter/"):]
            failed_normalized = failed_normalized.removesuffix(":free")
            if normalized == failed_normalized:
                continue

            result = await self._call_single_openrouter(normalized, messages, tools)
            if "error" not in result:
                return result

        return {"error": "All OpenRouter free models failed. No further fallback configured.", "provider": "openrouter"}

    async def _call_single_openrouter(self, model: str, messages: list[dict], tools: Optional[list] = None) -> dict:
        if not self.openrouter_key:
            return {"error": "no key"}
        try:
            body = {"model": model, "messages": messages, "max_tokens": 4096}
            if tools:
                body["tools"] = tools
            resp = await self._client.post(
                f"{OPENROUTER_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {self.openrouter_key}", "Content-Type": "application/json"},
                json=body,
            )
            if resp.status_code != 200:
                return {"error": f"status {resp.status_code}"}
            data = resp.json()
            choice = data["choices"][0]
            msg = choice["message"]
            result = {
                "provider": "openrouter",
                "model": data.get("model", model),
                "content": msg.get("content") or "",
                "finish_reason": choice.get("finish_reason", "stop"),
                "usage": data.get("usage", {}),
            }
            if msg.get("tool_calls"):
                result["tool_calls"] = msg["tool_calls"]
            return result
        except Exception as e:
            return {"error": str(e)}

    async def _call_lmstudio(self, model: str, messages: list[dict], tools: Optional[list] = None, reasoning: str = "medium") -> dict:
        """Call LM Studio v1 API with reasoning control.

        LM Studio v1 uses a different API format from OpenAI:
        - system_prompt (top-level) instead of system message
        - input (string or array) for the user content
        - reasoning parameter to control chain-of-thought
        - output array with typed entries (message, reasoning, tool_call, etc.)
        - response_id for stateful conversation tracking
        """
        if not self._cb_should_allow("lmstudio"):
            cb = self._cb["lmstudio"]
            remaining_cooldown = cb["cooldown"] - (time.time() - cb["opened_at"])
            return {"error": f"LM Studio circuit breaker open (cooldown {remaining_cooldown:.0f}s)", "provider": "lmstudio"}

        # Extract system prompt from messages
        system_prompt = ""
        non_system = []
        for m in messages:
            if m.get("role") == "system":
                system_prompt += (m["content"] or "") + "\n"
            else:
                non_system.append(m)

        system_prompt = system_prompt.strip()

        # Build input: for stateless mode, concatenate full conversation history
        input_str = ""
        for m in non_system:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "user":
                input_str += f"User: {content}\n"
            elif role == "assistant":
                input_str += f"Assistant: {content}\n"
            elif role == "tool":
                input_str += f"Tool result: {content}\n"
        input_str = input_str.strip()

        body = {
            "model": model,
            "input": input_str,
            "system_prompt": system_prompt,
            "reasoning": reasoning,
            "max_output_tokens": 4096,
            "temperature": 0.3,
            "store": False,
            "stream": False,
        }

        try:
            resp = await self._client.post(
                f"{LMSTUDIO_BASE}/api/v1/chat",
                json=body,
                timeout=120,  # thinking models can be slow
            )
        except Exception as e:
            self._cb_record_failure("lmstudio")
            return {"error": f"LM Studio connection error: {e}", "provider": "lmstudio"}

        if resp.status_code != 200:
            self._cb_record_failure("lmstudio")
            return {"error": f"LM Studio {resp.status_code}: {resp.text[:500]}", "provider": "lmstudio"}

        self._cb_record_success("lmstudio")

        data = resp.json()

        # Extract content and tool_calls from output array
        content = ""
        tool_calls = []
        reasoning_text = None
        for item in data.get("output", []):
            t = item.get("type", "")
            if t == "message":
                content = item.get("content", "")
            elif t == "reasoning":
                reasoning_text = item.get("content", "")
            elif t == "tool_call":
                tc = {
                    "id": f"call_{item.get('tool', 'unknown')}",
                    "type": "function",
                    "function": {
                        "name": item.get("tool", ""),
                        "arguments": json.dumps(item.get("arguments", {})),
                    },
                }
                tool_calls.append(tc)

        result = {
            "provider": "lmstudio",
            "model": data.get("model_instance_id", model),
            "content": content,
            "finish_reason": "stop",
            "usage": data.get("stats", {}),
        }
        if reasoning_text:
            result["reasoning"] = reasoning_text
        if tool_calls:
            result["tool_calls"] = tool_calls

        return result

    async def _call_gemini(self, model: str, messages: list[dict]) -> dict:
        if not self.gemini_key:
            return {"error": "GEMINI_API_KEY not set", "provider": "gemini"}

        if not self._cb_should_allow("gemini"):
            cb = self._cb["gemini"]
            remaining_cooldown = cb["cooldown"] - (time.time() - cb["opened_at"])
            logger.info(
                f"Circuit breaker OPEN for gemini — "
                f"skipping (cooldown {remaining_cooldown:.0f}s remaining)"
            )
            return {"error": f"Circuit breaker open for gemini (cooldown {remaining_cooldown:.0f}s)", "provider": "gemini"}

        contents = self._convert_to_gemini(messages)
        model_name = model.replace("gemini/", "")

        resp = await self._client.post(
            f"{GEMINI_BASE}/models/{model_name}:generateContent",
            params={"key": self.gemini_key},
            json={"contents": contents, "generationConfig": {"maxOutputTokens": 4096}},
        )

        if resp.status_code != 200:
            self._cb_record_failure("gemini")
            return {"error": f"Gemini {resp.status_code}: {resp.text[:200]}", "provider": "gemini"}

        self._cb_record_success("gemini")
        data = resp.json()
        candidate = data.get("candidates", [{}])[0]
        content = candidate.get("content", {}).get("parts", [{}])[0].get("text", "")

        return {
            "provider": "gemini",
            "model": model_name,
            "content": content,
            "finish_reason": candidate.get("finishReason", "STOP"),
            "usage": data.get("usageMetadata", {}),
        }

    def _convert_to_gemini(self, messages: list[dict]) -> list[dict]:
        contents = []
        for msg in messages:
            role = "user" if msg["role"] in ("user", "system") else "model"
            text = msg["content"]
            if msg["role"] == "system":
                text = f"[System Instruction]\n{text}"
            contents.append({"role": role, "parts": [{"text": text}]})
        return contents

    async def close(self):
        await self._client.aclose()
