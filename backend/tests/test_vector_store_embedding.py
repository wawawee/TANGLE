"""Tests for vector_store embedding setup.

These tests verify the embedding configuration stays consistent — the
constants + dummy vector contract together act as a regression net for
the dim-mismatch trap that bit TANGLE on 2026-06-28 (switched from
paid openai/text-embedding-3-small @ 1536 to local qwen3-embedding:8b @ 4096).
"""
import sys
import math
from pathlib import Path

import pytest

# Make backend importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from vector_store import (  # noqa: E402
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    EMBEDDING_SOURCE,
)
from vector_store import VectorStore  # noqa: E402


def _stub_dummy(text: str, dimensions: int = EMBEDDING_DIM) -> list:
    """Call _generate_dummy_vector without instantiating VectorStore (which
    has side effects: tries to connect to Qdrant/Supabase)."""
    class _Stub:
        pass
    return VectorStore._generate_dummy_vector(_Stub(), text, dimensions)


class TestEmbeddingConstants:
    def test_dim_is_4096(self):
        """EMBEDDING_DIM must be 4096 to match local qwen3-embedding:8b.

        Regression net: changing this without re-seeding Qdrant + Supabase
        will produce 4096-dim vectors that the 4096-dim collections accept
        but if someone bumps it to e.g. 768 without re-seeding, every
        upsert crashes with size mismatch.
        """
        assert EMBEDDING_DIM == 4096, f"EMBEDDING_DIM should be 4096, got {EMBEDDING_DIM}"

    def test_default_model_is_qwen3_8b(self):
        """Default model is the local 8B, not the older 0.6B or paid OpenAI."""
        assert "qwen3-embedding" in EMBEDDING_MODEL.lower()
        assert ":8b" in EMBEDDING_MODEL.lower() or "8b" in EMBEDDING_MODEL.lower(), (
            f"default model should be the 8B variant, got {EMBEDDING_MODEL!r}"
        )

    def test_default_source_is_ollama(self):
        """Default source must be local Ollama — never paid OpenRouter for embeddings."""
        assert EMBEDDING_SOURCE == "ollama", (
            f"EMBEDDING_SOURCE should default to 'ollama', got {EMBEDDING_SOURCE!r}"
        )


class TestDummyVector:
    """_generate_dummy_vector is the offline fallback. It must produce consistent
    vectors at exactly EMBEDDING_DIM and in [0, 1] so cosine search works."""

    def test_returns_exact_dim(self):
        v = _stub_dummy("any text")
        assert isinstance(v, list)
        assert len(v) == EMBEDDING_DIM, (
            f"dummy vector must have {EMBEDDING_DIM} dims, got {len(v)}"
        )

    def test_values_normalized_to_unit_range(self):
        v = _stub_dummy("any text")
        # The hash-based generator emits val/1000.0, so range is [0, 1].
        assert all(isinstance(x, (int, float)) for x in v), "non-numeric value"
        assert all(0.0 <= x <= 1.0 for x in v), (
            f"values out of [0,1] range: min={min(v)}, max={max(v)}"
        )

    def test_deterministic(self):
        """Same text -> same vector. Critical for offline search consistency."""
        v1 = _stub_dummy("the quick brown fox")
        v2 = _stub_dummy("the quick brown fox")
        assert v1 == v2, "non-deterministic dummy vector — would break offline search"

    def test_different_texts_diverge(self):
        """Different texts -> different vectors (otherwise search is useless)."""
        v1 = _stub_dummy("the quick brown fox")
        v2 = _stub_dummy("completely different sentence here")
        # At least 30% of dims should differ
        diff_count = sum(1 for a, b in zip(v1, v2) if a != b)
        assert diff_count > EMBEDDING_DIM * 0.3, (
            f"dummy vectors too similar ({diff_count}/{EMBEDDING_DIM} differ) — "
            f"search wouldn't discriminate"
        )

    def test_empty_string_safe(self):
        """Hashing '' must not crash."""
        v = _stub_dummy("")
        assert len(v) == EMBEDDING_DIM
        assert all(0.0 <= x <= 1.0 for x in v)

    def test_long_string_safe(self):
        """10KB text must not blow up."""
        big = "lorem ipsum dolor sit amet " * 500
        v = _stub_dummy(big)
        assert len(v) == EMBEDDING_DIM


class TestEmbeddingRouting:
    """The SHA256 fallback path returns the dummy vector (no API/Ollama)."""

    def test_sha256_source_returns_dummy_vector(self, monkeypatch):
        """When EMBEDDING_SOURCE=sha256 (offline), get_embeddings must NOT call Ollama.
        We patch the env var before importing — but vector_store reads it at module
        load, so we patch _get_ollama_embeddings to detect accidental calls instead.
        """
        from vector_store import VectorStore
        store = VectorStore()
        ollama_called = {"called": False}

        async def spy(*args, **kwargs):
            ollama_called["called"] = True
            return _stub_dummy("spy")

        # Patch the bound method on the instance
        monkeypatch.setattr(store, "_get_ollama_embeddings", spy)

        import asyncio
        # Force the sha256 branch regardless of module-level EMBEDDING_SOURCE
        original_source = EMBEDDING_SOURCE
        try:
            import vector_store as vs
            vs.EMBEDDING_SOURCE = "sha256"
            v = asyncio.run(store.get_embeddings("hello"))
            assert v == _stub_dummy("hello")
            assert not ollama_called["called"], (
                "sha256 path must not invoke Ollama"
            )
        finally:
            import vector_store as vs
            vs.EMBEDDING_SOURCE = original_source
