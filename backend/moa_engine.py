import json
import asyncio
import logging
from typing import AsyncGenerator

logger = logging.getLogger("tangle.moa")

REFERENCE_MODELS = [
    "openrouter/meta-llama/llama-3.2-3b-instruct:free",
    "openrouter/google/gemma-2-2b-it:free",
    "openrouter/microsoft/phi-3-mini-128k-instruct:free",
]

FALLBACK_MODELS = [
    "openrouter/qwen/qwen3-coder:free",
    "openrouter/poolside/laguna-m.1:free",
    "openrouter/nvidia/nemotron-nano-12b-v2-vl:free",
]

AGGREGATOR_MODEL = "openrouter/nousresearch/hermes-3-llama-3.1-70b:free"
AGGREGATOR_FALLBACK = "openrouter/meta-llama/llama-3.3-70b-instruct:free"

REF_DELAY = 1.5

def _model_name(model: str) -> str:
    return model.split("/")[-1].split(":")[0]

def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"

class MoAEngine:
    def __init__(self, gateway):
        self.gateway = gateway

    async def analyze(self, prompt: str, system_prompt: str = "") -> AsyncGenerator[str, None]:
        yield _sse("phase", {"phase": "reference", "total": len(REFERENCE_MODELS)})

        ref_sections = []
        used_ref_models = []

        for i, model in enumerate(REFERENCE_MODELS):
            if i > 0:
                await asyncio.sleep(REF_DELAY)

            result = await self._call_ref_with_retry(model, prompt, system_prompt)
            name = _model_name(model)

            if result.get("error"):
                logger.warning(f"MoA reference {name} failed: {result['error']}")
                fallback_ok = False
                for fb in FALLBACK_MODELS:
                    await asyncio.sleep(REF_DELAY)
                    fb_result = await self._call_ref_with_retry(fb, prompt, system_prompt)
                    fb_name = _model_name(fb)
                    if not fb_result.get("error"):
                        content = fb_result.get("content", "")
                        ref_sections.append(f"## {fb_name}\n{content}\n")
                        yield _sse("ref_done", {"model": fb_name, "output": content[:600]})
                        used_ref_models.append(fb)
                        fallback_ok = True
                        break
                    else:
                        yield _sse("ref_error", {"model": fb_name, "error": fb_result["error"]})
                if not fallback_ok:
                    ref_sections.append(f"## {name}: ERROR\nAll fallbacks exhausted.\n")
                    yield _sse("ref_error", {"model": name, "error": "All models failed"})
                    used_ref_models.append(model)
            else:
                content = result.get("content", "")
                ref_sections.append(f"## {name}\n{content}\n")
                yield _sse("ref_done", {"model": name, "output": content[:600]})
                used_ref_models.append(model)

        agg_name = _model_name(AGGREGATOR_MODEL)
        yield _sse("phase", {"phase": "aggregator", "model": agg_name})

        if not ref_sections:
            yield _sse("ref_error", {"model": "all", "error": "All reference models failed - no context for synthesis"})
            agg_prompt = f"Answer this query directly (no context available from reference models):\n\n{prompt}"
            if system_prompt:
                agg_prompt = f"{system_prompt}\n\n{agg_prompt}"
        else:
            agg_prompt = self._synthesis_prompt(prompt, system_prompt, ref_sections)

        await asyncio.sleep(REF_DELAY)
        final = await self.gateway.chat(AGGREGATOR_MODEL, [{"role": "user", "content": agg_prompt}])

        if final.get("error") and AGGREGATOR_FALLBACK:
            logger.warning(f"MoA aggregator {agg_name} failed: {final['error']} — trying fallback")
            fb_name = _model_name(AGGREGATOR_FALLBACK)
            yield _sse("phase", {"phase": "aggregator", "model": fb_name})
            await asyncio.sleep(REF_DELAY)
            final = await self.gateway.chat(AGGREGATOR_FALLBACK, [{"role": "user", "content": agg_prompt}])

        content = final.get("content", "") or final.get("error", "")
        all_models_used = used_ref_models + ([AGGREGATOR_FALLBACK] if final.get("error") else [AGGREGATOR_MODEL])

        yield _sse("complete", {
            "final": content,
            "models_used": all_models_used,
        })

    async def _call_ref_with_retry(self, model: str, prompt: str, system_prompt: str, max_retries: int = 2) -> dict:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        for attempt in range(max_retries):
            result = await self.gateway.chat(model, messages)
            err = result.get("error", "")
            if not err:
                return result
            if "circuit breaker" in err.lower() and attempt < max_retries - 1:
                wait = 8 * (attempt + 1)
                logger.info(f"Circuit breaker hit, retrying {model} in {wait}s")
                await asyncio.sleep(wait)
                continue
            return result
        return result

    def _synthesis_prompt(self, prompt: str, system_prompt: str, refs: list[str]) -> str:
        sp = f"\n{system_prompt}\n" if system_prompt else ""
        refs_text = "\n".join(refs)
        return (
            f"You are an expert AI analyst synthesizing multiple independent analyses. "
            f"Produce a comprehensive, accurate, well-structured final answer.{sp}\n\n"
            f"Original query: {prompt}\n\n"
            f"=== INDEPENDENT ANALYSES ===\n\n"
            f"{refs_text}\n\n"
            f"=== SYNTHESIS ===\n\n"
            f"Now produce your synthesized answer based on all analyses above:"
        )
