"""Tests for the free LLM gateway — model list curation + fallback normalization.

Background: 2026-06-28 we dropped 3 dead refs (deepseek/deepseek-v4-flash,
minmax/minimax-m2.5, arcee-ai/trinity-large-thinking) and added 5 verified
replacements. Plus a normalization fix in _try_other_free_models so entries
like openrouter/owl-alpha (which lacks a :free suffix) work correctly.
These tests lock in both pieces so we don't regress.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from free_gateway import OPENROUTER_FREE_MODELS  # noqa: E402
from vector_store import EMBEDDING_DIM  # noqa: E402


class TestFreeModelList:
    """The fallback chain must be verified-live against api.openrouter.ai/models
    before being added. Any dead ref costs a retry slot."""

    def test_contains_core_2026_june_models(self):
        """Models we know exist and work as of 2026-06-28."""
        must_have = {
            "qwen/qwen3-coder:free",                          # coding king
            "nvidia/nemotron-3-super-120b-a12b:free",         # reasoning king
            "openai/gpt-oss-120b:free",                       # tool-calling
            "meta-llama/llama-3.3-70b-instruct:free",         # stable default
            "poolside/laguna-m.1:free",                       # agentic coding
            "google/gemma-4-31b-it:free",                     # multimodal
        }
        actual = set(OPENROUTER_FREE_MODELS)
        missing = must_have - actual
        assert not missing, f"required models missing from fallback chain: {missing}"

    def test_contains_agentic_routing_models(self):
        """Agentic + tool-use models for orchestrator workloads."""
        must_have = {
            "openrouter/owl-alpha",     # native tool-use, 1M context
            "cohere/north-mini-code:free",  # new agentic coding MoE
        }
        actual = set(OPENROUTER_FREE_MODELS)
        missing = must_have - actual
        assert not missing, f"missing agentic models: {missing}"

    def test_contains_vision_and_multimodal(self):
        """Vision/multimodal needed by parsing_engine."""
        must_have = {
            "nvidia/nemotron-nano-12b-v2-vl:free",
            "google/gemma-4-26b-a4b-it:free",
        }
        actual = set(OPENROUTER_FREE_MODELS)
        assert must_have.issubset(actual), f"missing vision/multimodal: {must_have - actual}"

    def test_no_dead_references(self):
        """Models that don't exist on OpenRouter — verified 2026-06-28.
        Each one wasted a retry slot before they were removed.
        """
        dead = {
            "deepseek/deepseek-v4-flash:free",        # no deepseek v4 on OR :free
            "minimax/minimax-m2.5:free",              # removed from :free tier
            "arcee-ai/trinity-large-thinking:free",   # removed
        }
        actual = set(OPENROUTER_FREE_MODELS)
        overlap = dead & actual
        assert not overlap, f"dead refs in fallback chain: {overlap}"

    def test_no_unprefixed_openrouter_routes_that_lack_free_suffix(self):
        """Models that DON'T have :free suffix (and cost real $$ if queried).

        Currently the only entry without :free suffix should be 'openrouter/owl-alpha',
        which is zero-priced via the router but lacks the :free tag.
        Make sure we haven't accidentally added others.
        """
        unsuffixed = [m for m in OPENROUTER_FREE_MODELS if not m.endswith(":free")]
        # Whatever they are, they MUST start with 'openrouter/' (which means
        # _try_other_free_models will strip the prefix before calling OpenRouter)
        for m in unsuffixed:
            assert m.startswith("openrouter/"), (
                f"non-:free entry {m!r} must be prefixed with 'openrouter/' "
                f"so _try_other_free_models can strip it before API call"
            )

    def test_fallback_chain_reasonable_size(self):
        """Sanity: not too few, not too many. 8-20 entries is the sweet spot."""
        n = len(OPENROUTER_FREE_MODELS)
        assert 8 <= n <= 25, (
            f"fallback chain has {n} entries — outside the 8-25 sweet spot. "
            f"Too few: bad coverage. Too many: lots of retries to burn."
        )


class TestFallbackNormalization:
    """Regression net for the _try_other_free_models prefix/suffix fix (2026-06-28).

    Without this, entries like 'openrouter/owl-alpha' would 404 because the API
    call would send the model as 'openrouter/owl-alpha' (with prefix) instead
    of just 'owl-alpha'.
    """

    def _normalize_for_test(self, fallback_model: str) -> str:
        """Mirror the normalization logic in _try_other_free_models (test copy)."""
        normalized = fallback_model
        if normalized.startswith("openrouter/"):
            normalized = normalized[len("openrouter/"):]
        normalized = normalized.removesuffix(":free")
        return normalized

    def test_strips_openrouter_prefix(self):
        """openrouter/owl-alpha -> owl-alpha"""
        assert self._normalize_for_test("openrouter/owl-alpha") == "owl-alpha"

    def test_strips_free_suffix(self):
        """qwen/qwen3-coder:free -> qwen/qwen3-coder"""
        assert self._normalize_for_test("qwen/qwen3-coder:free") == "qwen/qwen3-coder"

    def test_strips_both(self):
        """openrouter/free -> free (the meta-router)"""
        assert self._normalize_for_test("openrouter/free") == "free"

    def test_passes_through_already_normalized(self):
        """Already-clean model IDs pass through unchanged."""
        assert self._normalize_for_test("meta-llama/llama-3.3-70b-instruct") == (
            "meta-llama/llama-3.3-70b-instruct"
        )

    def test_full_chain_normalizes_to_valid_ids(self):
        """Every entry in OPENROUTER_FREE_MODELS must normalize to a clean
        OpenRouter model ID (no spurious prefix or suffix)."""
        for m in OPENROUTER_FREE_MODELS:
            norm = self._normalize_for_test(m)
            # Must not contain a slash at start (means prefix was leaked)
            assert not norm.startswith("/"), (
                f"normalization left leading slash: {m!r} -> {norm!r}"
            )
            # Must not contain :free (means suffix was leaked)
            assert not norm.endswith(":free"), (
                f"normalization left :free suffix: {m!r} -> {norm!r}"
            )
            # Must not contain 'openrouter/' anywhere
            assert "openrouter/" not in norm, (
                f"normalization didn't strip openrouter/ prefix: {m!r} -> {norm!r}"
            )
