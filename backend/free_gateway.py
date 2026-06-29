"""Free AI API Gateway — routes to OpenRouter (free) and Google Gemini (free)"""

import os, time, json, asyncio
from typing import Optional
import httpx

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
OLLAMA_BASE = "http://localhost:11434"

# Verified against https://openrouter.ai/api/v1/models on 2026-06-28.
# Drop entries here only after confirming they are gone from the live API --
# each one in the chain is a retry attempt that costs quota if dead.
OPENROUTER_FREE_MODELS = [
    # Tier 1: Best defaults (retry order -- best first)
    "qwen/qwen3-coder:free",                          # coding king, 1M ctx
    "nvidia/nemotron-3-ultra-550b-a55b:free",         # reasoning king, 1M ctx
    "openai/gpt-oss-120b:free",                       # tool-calling + structured JSON, Apache 2.0
    "meta-llama/llama-3.3-70b-instruct:free",         # stable all-rounder (orchestrator default)
    "poolside/laguna-m.1:free",                       # agentic coding specialist
    "openrouter/owl-alpha",                           # native tool-use, 1M ctx
    # Tier 2: Specialists
    "nvidia/nemotron-3-super-120b-a12b:free",         # hybrid MoE
    "cohere/north-mini-code:free",                    # agentic coding MoE
    "qwen/qwen3-next-80b-a3b-instruct:free",          # fast + long ctx
    "google/gemma-4-31b-it:free",                     # multimodal (text+image)
    "google/gemma-4-26b-a4b-it:free",                 # MoE multimodal
    "nvidia/nemotron-nano-12b-v2-vl:free",            # vision default (parsing_engine)
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",  # perception sub-agent
    "nousresearch/hermes-3-llama-3.1-405b:free",      # stable long-time fallback
    "meta-llama/llama-3.2-3b-instruct:free",          # small + fast bulk fallback
    # Tier 3: Last resort
    "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",  # uncensored (use last)
    "openrouter/free",                                              # auto-route to any available free model
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
        }

    async def health(self) -> dict:
        """Check health of all providers."""
        health = {
            "openrouter": bool(self.openrouter_key),
            "gemini": bool(self.gemini_key),
            "ollama": await self._check_ollama(),
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
            import logging
            logging.getLogger("tangle.gateway").info(
                f"Circuit breaker CLOSED for {provider} (probe succeeded)"
            )
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
            import logging
            logging.getLogger("tangle.gateway").warning(
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

    async def chat(self, model: str, messages: list[dict],agent_context: Optional[dict] = None, tools: Optional[list] = None) -> dict:
        errors = []

        if model == "ollama":
            return await self._call_ollama(messages)

        if model.startswith("gemini"):
            if not self.gemini_key:
                return {"error": "GEMINI_API_KEY not set", "provider": "gemini"}
            return await self._call_gemini(model, messages)

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
            return await self._fallback_to_gemini(model, messages)

        # Circuit breaker check
        if not self._cb_should_allow("openrouter"):
            import logging
            cb = self._cb["openrouter"]
            remaining_cooldown = cb["cooldown"] - (time.time() - cb["opened_at"])
            logging.getLogger("tangle.gateway").info(
                f"Circuit breaker OPEN for openrouter — "
                f"falling back (cooldown {remaining_cooldown:.0f}s remaining)"
            )
            return await self._fallback_to_gemini(model, messages)

        remaining = self._rate_limits["openrouter"]["remaining"]
        if remaining <= 0:
            wait = self._rate_limits["openrouter"]["reset"] - time.time()
            if wait > 0:
                return await self._fallback_to_gemini(model, messages)

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
            # Normalize: strip optional "openrouter/" prefix (for entries like openrouter/owl-alpha
            # whose ID does NOT carry a :free suffix), and strip optional :free suffix.
            # Exception: keep "openrouter/free" as-is — it's a special routing endpoint.
            normalized = fallback_model
            if normalized == "openrouter/free":
                pass  # keep full ID
            elif normalized.startswith("openrouter/"):
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
        return await self._fallback_to_gemini(failed_model, messages)

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

    async def _call_gemini(self, model: str, messages: list[dict]) -> dict:
        if not self.gemini_key:
            return {"error": "GEMINI_API_KEY not set", "provider": "gemini"}

        if not self._cb_should_allow("gemini"):
            import logging
            cb = self._cb["gemini"]
            remaining_cooldown = cb["cooldown"] - (time.time() - cb["opened_at"])
            logging.getLogger("tangle.gateway").info(
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

    async def _fallback_to_gemini(self, model: str, messages: list[dict]) -> dict:
        result = await self._call_gemini("gemini/gemini-2.0-flash-exp", messages)
        if "error" not in result:
            return result
        ollama_result = await self._call_ollama(messages)
        if "error" in ollama_result:
            return {"error": f"All providers failed. OpenRouter: no key, Gemini: {result['error']}, Ollama: {ollama_result['error']}", "provider": "none"}
        return ollama_result

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
