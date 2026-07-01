"""Tests for skill_router.py — frontmatter parsing, embedding selection, prompt injection."""

import os
import re
import json
import math
import tempfile
import shutil
import pytest
from pathlib import Path
from typing import List, Tuple

from skill_router import (
    SkillRouter,
    _parse_frontmatter,
    _cosine_similarity,
    _text_fallback_vector,
)


# ── Fixtures ─────────────────────────────────────────────────

@pytest.fixture
def skill_dir():
    """Create a temporary skills directory with test skill files."""
    tmp = Path(tempfile.mkdtemp())

    (tmp / "general.md").write_text("""---
id: general
name: General
version: 1.0
embedding_keywords:
  - general research
  - investigation
always_include: true
---
# General
Always included skill.
""")

    (tmp / "osint.md").write_text("""---
id: osint
name: OSINT
version: 1.0
embedding_keywords:
  - osint
  - social media
  - person lookup
always_include: false
mcps:
  - sherlock-mcp
apis:
  - haveibeenpwned
tools:
  - search_username
---
# OSINT
Person lookup skill.
""")

    (tmp / "financial.md").write_text("""---
id: financial
name: Financial
version: 1.0
embedding_keywords:
  - financial analysis
  - annual report
  - credit risk
always_include: false
apis:
  - allabolag
tools:
  - fetch_annual_report
---
# Financial
Company finance skill.
""")

    (tmp / "SKILL_TEMPLATE.md").write_text("ignored template file")

    yield tmp
    shutil.rmtree(str(tmp))


@pytest.fixture
def mock_embed():
    """Deterministic mock embed that returns hash-based vectors."""
    @pytest.mark.asyncio
    async def embed(text: str) -> List[float]:
        return [hash(c + str(i)) % 1000 / 1000.0 for i, c in enumerate(text.ljust(128)[:128])]
    return embed


@pytest.fixture
def router(skill_dir, mock_embed):
    return SkillRouter(str(skill_dir), embed_fn=mock_embed, threshold=0.30, top_k=5)


# ── Frontmatter parsing ──────────────────────────────────────

class TestParseFrontmatter:
    def test_parses_simple_fields(self):
        md = """---
id: test
name: Test
version: 1.0
always_include: false
---
# Body"""
        meta, body = _parse_frontmatter(md)
        assert meta["id"] == "test"
        assert meta["name"] == "Test"
        assert meta["version"] == 1.0
        assert meta["always_include"] is False

    def test_parses_lists(self):
        md = """---
id: test
embedding_keywords:
  - hello
  - world
mcps:
  - mcp-one
apis: []
---
Body"""
        meta, body = _parse_frontmatter(md)
        assert meta["embedding_keywords"] == ["hello", "world"]
        assert meta["mcps"] == ["mcp-one"]
        assert meta["apis"] == []

    def test_no_frontmatter_returns_empty(self):
        meta, body = _parse_frontmatter("Just content\nno frontmatter")
        assert meta == {}
        assert "Just content" in body

    def test_boolean_values(self):
        md = """---
on: true
off: false
---"""
        meta, _ = _parse_frontmatter(md)
        assert meta["on"] is True
        assert meta["off"] is False

    def test_quoted_strings(self):
        md = """---
name: "Hello World"
desc: 'Single quoted'
---"""
        meta, _ = _parse_frontmatter(md)
        assert meta["name"] == "Hello World"
        assert meta["desc"] == "Single quoted"

    def test_preserves_body_after_frontmatter(self):
        md = """---
id: test
---
# Title

Content here."""
        _, body = _parse_frontmatter(md)
        assert "# Title" in body
        assert "Content here." in body


# ── Cosine similarity ────────────────────────────────────────

class TestCosineSimilarity:
    def test_identical_vectors(self):
        assert _cosine_similarity([1, 0, 0], [1, 0, 0]) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        assert _cosine_similarity([1, 0, 0], [0, 1, 0]) == pytest.approx(0.0)

    def test_partial_match(self):
        sim = _cosine_similarity([1, 1, 0], [1, 0, 0])
        assert 0.6 < sim < 0.8

    def test_zero_vector(self):
        assert _cosine_similarity([0, 0], [1, 0]) == pytest.approx(0.0)

    def test_both_zero(self):
        assert _cosine_similarity([0, 0], [0, 0]) == pytest.approx(0.0)


# ── Fallback vector ──────────────────────────────────────────

class TestTextFallbackVector:
    def test_returns_128_dim(self):
        vec = _text_fallback_vector("hello")
        assert len(vec) == 128

    def test_normalized(self):
        vec = _text_fallback_vector("test")
        norm = math.sqrt(sum(v * v for v in vec))
        assert norm == pytest.approx(1.0, rel=0.01)

    def test_deterministic(self):
        v1 = _text_fallback_vector("hello world")
        v2 = _text_fallback_vector("hello world")
        assert v1 == v2

    def test_different_texts_diverge(self):
        v1 = _text_fallback_vector("apple")
        v2 = _text_fallback_vector("banana")
        assert v1 != v2

    def test_empty_string_safe(self):
        vec = _text_fallback_vector("")
        assert len(vec) == 128
        norm = math.sqrt(sum(v * v for v in vec))
        assert norm == pytest.approx(1.0, rel=0.01)


# ── Skill loading ────────────────────────────────────────────

class TestSkillLoading:
    @pytest.mark.asyncio
    async def test_loads_all_skills(self, router):
        await router._ensure_loaded()
        assert len(router.skills) == 3  # general, osint, financial

    @pytest.mark.asyncio
    async def test_skips_template_files(self, router):
        await router._ensure_loaded()
        assert "SKILL_TEMPLATE" not in router.skills

    @pytest.mark.asyncio
    async def test_each_skill_has_vector(self, router):
        await router._ensure_loaded()
        for sid, skill in router.skills.items():
            assert len(skill["vector"]) > 0, f"{sid} missing vector"

    @pytest.mark.asyncio
    async def test_get_active_skill_ids(self, router):
        await router._ensure_loaded()
        ids = router.get_active_skill_ids()
        assert sorted(ids) == sorted(["general", "osint", "financial"])

    @pytest.mark.asyncio
    async def test_get_skill_info(self, router):
        await router._ensure_loaded()
        info = router.get_skill_info("osint")
        assert info is not None
        assert info["name"] == "OSINT"
        assert info["id"] == "osint"
        assert "_body" not in info  # body should not leak

    @pytest.mark.asyncio
    async def test_get_skill_info_missing(self, router):
        await router._ensure_loaded()
        assert router.get_skill_info("nonexistent") is None

    @pytest.mark.asyncio
    async def test_reload_clears_and_reloads(self, router):
        await router._ensure_loaded()
        assert len(router.skills) == 3
        await router.reload()
        assert len(router.skills) == 3

    @pytest.mark.asyncio
    async def test_empty_directory(self, mock_embed):
        tmp = Path(tempfile.mkdtemp())
        r = SkillRouter(str(tmp), embed_fn=mock_embed)
        await r._ensure_loaded()
        assert len(r.skills) == 0
        assert await r.select("test", "") == []
        shutil.rmtree(str(tmp))

    @pytest.mark.asyncio
    async def test_missing_directory(self, mock_embed):
        r = SkillRouter("/nonexistent/path", embed_fn=mock_embed)
        await r._ensure_loaded()
        assert len(r.skills) == 0


# ── Skill selection ──────────────────────────────────────────

class TestSkillSelection:
    @pytest.mark.asyncio
    async def test_always_include_at_top(self, router):
        await router._ensure_loaded()
        selected = await router.select("anything", "")
        assert selected[0][0] == "general"
        assert selected[0][1] == 1.0

    @pytest.mark.asyncio
    async def test_respects_threshold(self, router):
        await router._ensure_loaded()
        selected = await router.select("social media osint", "")
        scores = [s for _, s in selected]
        assert all(s >= 0.30 for s in scores)

    @pytest.mark.asyncio
    async def test_returns_top_k(self, router):
        await router._ensure_loaded()
        selected = await router.select("a", "", top_k=2)
        assert len(selected) <= 2

    @pytest.mark.asyncio
    async def test_ordering_by_score_desc(self, router):
        await router._ensure_loaded()
        selected = await router.select("a", "")
        scores = [s for _, s in selected]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_caches_results(self, router):
        await router._ensure_loaded()
        r1 = await router.select("test", "")
        r2 = await router.select("test", "")
        assert r1 == r2

    @pytest.mark.asyncio
    async def test_invalidate_cache(self, router):
        await router._ensure_loaded()
        r1 = await router.select("test", "")
        router.invalidate_cache()
        assert len(router._cache) == 0


# ── Prompt building ──────────────────────────────────────────

class TestBuildSystemPrompt:
    @pytest.mark.asyncio
    async def test_empty_selection_returns_empty(self, router):
        prompt = router.build_system_prompt([])
        assert prompt == ""

    @pytest.mark.asyncio
    async def test_includes_skill_names(self, router):
        await router._ensure_loaded()
        selected = await router.select("finance", "")
        prompt = router.build_system_prompt(selected)
        assert "Skill:" in prompt or "General" in prompt or "Financial" in prompt or "OSINT" in prompt

    @pytest.mark.asyncio
    async def test_includes_relevance_scores(self, router):
        await router._ensure_loaded()
        selected = await router.select("a", "")
        prompt = router.build_system_prompt(selected)
        for _, score in selected:
            assert f"{score:.2f}" in prompt


# ── MCP/API/Tool collection ──────────────────────────────────

class TestResourceCollection:
    @pytest.mark.asyncio
    async def test_get_mcps(self, router):
        await router._ensure_loaded()
        selected = [("osint", 0.9)]
        assert router.get_mcps(selected) == ["sherlock-mcp"]

    @pytest.mark.asyncio
    async def test_get_apis(self, router):
        await router._ensure_loaded()
        selected = [("osint", 0.9), ("financial", 0.8)]
        apis = router.get_apis(selected)
        assert "haveibeenpwned" in apis
        assert "allabolag" in apis

    @pytest.mark.asyncio
    async def test_get_tools(self, router):
        await router._ensure_loaded()
        selected = [("osint", 0.9)]
        assert router.get_tools(selected) == ["search_username"]

    @pytest.mark.asyncio
    async def test_empty_for_no_selection(self, router):
        assert router.get_mcps([]) == []
        assert router.get_apis([]) == []
        assert router.get_tools([]) == []


# ── Real skills parsing (integration) ────────────────────────

class TestRealSkills:
    """Validate that our actual skill files parse correctly."""

    @pytest.fixture
    def real_skills_dir(self):
        p = Path(__file__).parent.parent / "skills"
        if p.exists():
            return p
        pytest.skip("skills/ directory not found")

    def test_all_real_skills_parse(self, real_skills_dir):
        count = 0
        for f in sorted(real_skills_dir.glob("*.md")):
            if f.name in ("SKILL_ARCHITECTURE.md", "SKILL_TEMPLATE.md"):
                continue
            meta, body = _parse_frontmatter(f.read_text())
            assert meta.get("id"), f"{f.name} missing id"
            assert "embedding_keywords" in meta, f"{f.name} missing keywords"
            assert meta["embedding_keywords"], f"{f.name} has empty keywords"
            assert "always_include" in meta, f"{f.name} missing always_include"
            assert body.strip(), f"{f.name} has empty body"
            count += 1
        assert count >= 8, f"Expected >= 8 skills, got {count}"

    def test_always_include_skills_present(self, real_skills_dir):
        always = []
        for f in real_skills_dir.glob("*.md"):
            if f.name in ("SKILL_ARCHITECTURE.md", "SKILL_TEMPLATE.md"):
                continue
            meta, _ = _parse_frontmatter(f.read_text())
            if meta.get("always_include"):
                always.append(meta["id"])
        assert "general" in always, "general must be always_include"
        assert "synthesis_reporting" in always, "synthesis_reporting must be always_include"

    def test_no_duplicate_ids(self, real_skills_dir):
        ids = []
        for f in real_skills_dir.glob("*.md"):
            if f.name in ("SKILL_ARCHITECTURE.md", "SKILL_TEMPLATE.md"):
                continue
            meta, _ = _parse_frontmatter(f.read_text())
            ids.append(meta.get("id"))
        assert len(ids) == len(set(ids)), f"Duplicate skill IDs: {ids}"

    def test_keywords_reasonable_length(self, real_skills_dir):
        for f in real_skills_dir.glob("*.md"):
            if f.name in ("SKILL_ARCHITECTURE.md", "SKILL_TEMPLATE.md"):
                continue
            meta, _ = _parse_frontmatter(f.read_text())
            kw = meta.get("embedding_keywords", [])
            assert 5 <= len(kw) <= 25, f"{f.name} has {len(kw)} keywords (want 5-25)"
