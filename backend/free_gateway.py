"""Free AI API Gateway — routes to OpenRouter (free) and Google Gemini (free)"""

import os, time, json, asyncio
from typing import Optional
import httpx

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
OLLAMA_BASE = "http://localhost:11434"

OPENROUTER_FREE_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-4-26b-a4b-it:free",
    "deepseek/deepseek-v4-flash:free",
    "qwen/qwen3-coder:free",
    "minimax/minimax-m2.5:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
    "openai/gpt-oss-120b:free",
    "google/gemma-4-31b-it:free",
    "arcee-ai/trinity-large-thinking:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "nvidia/nemotron-nano-12b-v2-vl:free",
    "poolside/laguna-m.1:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
]

OLLAMA_CHAT_MODELS = ["llama3.2:3b", "llama3.1:8b", "qwen3:8b", "llama3.2:1b", "phi4-mini:3.8b"]

class FreeGateway:
    def __init__(self):
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")
        self._client = httpx.AsyncClient(timeout=60)
        self._rate_limits = {"openrouter": {"remaining": 50, "reset": time.time() + 86400}}
        self._ollama_available = None

    async def health(self) -> dict:
        """Check health of all providers."""
        health = {
            "openrouter": bool(self.openrouter_key),
            "gemini": bool(self.gemini_key),
            "ollama": await self._check_ollama(),
        }
        return health

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

        self._rate_limits["openrouter"]["remaining"] = max(0, remaining - 1)

        if resp.status_code in (429, 503):
            if resp.status_code == 429:
                self._rate_limits["openrouter"]["remaining"] = 0
                self._rate_limits["openrouter"]["reset"] = time.time() + 60
            return await self._try_other_free_models(model, messages, tools)

        if resp.status_code != 200:
            return await self._try_other_free_models(model, messages, tools)

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
            stripped = fallback_model.removesuffix(":free")
            if fallback_model == failed_model or stripped == failed_model:
                continue
            result = await self._call_single_openrouter(fallback_model, messages, tools)
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

        contents = self._convert_to_gemini(messages)
        model_name = model.replace("gemini/", "")

        resp = await self._client.post(
            f"{GEMINI_BASE}/models/{model_name}:generateContent",
            params={"key": self.gemini_key},
            json={"contents": contents, "generationConfig": {"maxOutputTokens": 4096}},
        )

        if resp.status_code != 200:
            return {"error": f"Gemini {resp.status_code}: {resp.text[:200]}", "provider": "gemini"}

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
