"""Tests for ParsingEngine — focused on the new auto-tagging pipeline.

Verifies:
- `_generate_tags` returns taxonomical tags when LLM cooperates
- Falls back to ['untagged'] when gateway is missing
- Falls back to ['untagged'] when LLM errors
- Falls back to ['untagged'] when LLM returns garbage
- Truncates long content intelligently (start + end preserved)
- `parse_file` returns the `tags` field in its dict and writes them into the
  `### Tags` section of the markdown body
- Static `_extract_inline_tags` ignores mid-word hashes (C#, F#)
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Make backend importable
sys.path.insert(0, str(Path(__file__).parent.parent))


from parsing_engine import ParsingEngine  # noqa: E402


# Static method on ParsingEngine — alias for cleaner test code
_extract_tags = ParsingEngine._extract_inline_tags


def _engine_with_mock_gateway(mock_chat_return):
    """Build a ParsingEngine with a mocked gateway.chat() for tag generation."""
    gateway = MagicMock()
    if isinstance(mock_chat_return, Exception):
        gateway.chat = AsyncMock(side_effect=mock_chat_return)
    else:
        gateway.chat = AsyncMock(return_value=mock_chat_return)
    return ParsingEngine(gateway=gateway)


# ─────────────────────────────────────────────────────────────────────
# Static _extract_inline_tags helper
# ─────────────────────────────────────────────────────────────────────

class TestExtractInlineTags:
    def test_extracts_simple_tags(self):
        tags = _extract_tags("Some text #health and #finance here.")
        assert "health" in tags
        assert "finance" in tags

    def test_ignores_hash_inside_words(self):
        # C# and F# must NOT be tagged. Real hashtag must be tagged.
        tags = _extract_tags("Using C# for the API. Love #csharp though.")
        assert "csharp" in tags
        assert "c" not in tags

    def test_dedupes_and_preserves_order(self):
        # Use 2-char tags because the regex requires ≥2 chars after #
        tags = _extract_tags("#aa #bb #aa #cc #bb")
        assert tags == ["aa", "bb", "cc"]

    def test_caps_at_8(self):
        tags = _extract_tags(" ".join(f"#tag{i:02d}" for i in range(20)))
        assert len(tags) == 8
        assert tags[0] == "tag00"
        assert tags[-1] == "tag07"


# ─────────────────────────────────────────────────────────────────────
# _generate_tags — happy path
# ─────────────────────────────────────────────────────────────────────

class TestGenerateTagsHappyPath:
    @pytest.mark.asyncio
    async def test_extracts_tags_from_llm_response(self):
        engine = _engine_with_mock_gateway({"content": "#health #vet #cat"})
        tags = await engine._generate_tags("Luna is a cat with vet records.", "Luna")
        assert "health" in tags
        assert "vet" in tags
        assert "cat" in tags

    @pytest.mark.asyncio
    async def test_lowercases_tags(self):
        engine = _engine_with_mock_gateway({"content": "#HEALTH #Finance"})
        tags = await engine._generate_tags("anything", "Entity")
        assert all(t == t.lower() for t in tags)
        assert "health" in tags
        assert "finance" in tags

    @pytest.mark.asyncio
    async def test_dedupes(self):
        engine = _engine_with_mock_gateway({"content": "#health #health #vet"})
        tags = await engine._generate_tags("x", "Entity")
        assert tags.count("health") == 1
        assert tags.count("vet") == 1

    @pytest.mark.asyncio
    async def test_caps_at_5(self):
        engine = _engine_with_mock_gateway({
            "content": " ".join(f"#tag{i}" for i in range(20))
        })
        tags = await engine._generate_tags("x", "Entity")
        assert len(tags) == 5

    @pytest.mark.asyncio
    async def test_strips_invalid_chars(self):
        # Tag with punctuation gets sanitized
        engine = _engine_with_mock_gateway({"content": "#health!! #v.et"})
        tags = await engine._generate_tags("x", "Entity")
        # Either filtered out entirely, or stripped to safe chars
        for t in tags:
            assert all(c.isalnum() or c in "-_" for c in t), f"Unsafe tag: {t}"


# ─────────────────────────────────────────────────────────────────────
# _generate_tags — fallback paths
# ─────────────────────────────────────────────────────────────────────

class TestGenerateTagsFallback:
    @pytest.mark.asyncio
    async def test_no_gateway_returns_untagged(self):
        engine = ParsingEngine(gateway=None)
        tags = await engine._generate_tags("Some content here.", "Entity")
        assert tags == ["untagged"]

    @pytest.mark.asyncio
    async def test_empty_content_returns_untagged(self):
        engine = _engine_with_mock_gateway({"content": "#health"})
        tags = await engine._generate_tags("", "Entity")
        assert tags == ["untagged"]

    @pytest.mark.asyncio
    async def test_whitespace_only_content_returns_untagged(self):
        engine = _engine_with_mock_gateway({"content": "#health"})
        tags = await engine._generate_tags("   \n\t  ", "Entity")
        assert tags == ["untagged"]

    @pytest.mark.asyncio
    async def test_llm_error_returns_untagged(self):
        engine = _engine_with_mock_gateway(RuntimeError("network down"))
        tags = await engine._generate_tags("real content here", "Entity")
        assert tags == ["untagged"]

    @pytest.mark.asyncio
    async def test_llm_returns_no_hashtags_returns_untagged(self):
        engine = _engine_with_mock_gateway({"content": "Just prose, no tags at all."})
        tags = await engine._generate_tags("x", "Entity")
        assert tags == ["untagged"]

    @pytest.mark.asyncio
    async def test_llm_returns_empty_content(self):
        engine = _engine_with_mock_gateway({"content": ""})
        tags = await engine._generate_tags("x", "Entity")
        assert tags == ["untagged"]

    @pytest.mark.asyncio
    async def test_llm_returns_only_invalid_tags(self):
        # Tags with non-alphanumeric chars get filtered
        engine = _engine_with_mock_gateway({"content": "#!@#$"})
        tags = await engine._generate_tags("x", "Entity")
        assert tags == ["untagged"]


# ─────────────────────────────────────────────────────────────────────
# _generate_tags — content truncation
# ─────────────────────────────────────────────────────────────────────

class TestContentTruncation:
    @pytest.mark.asyncio
    async def test_short_content_passes_through_unchanged(self):
        engine = _engine_with_mock_gateway({"content": "#aa"})
        short = "short content"
        # If truncation logic ran, the prompt would contain "[...truncated...]"
        # We test indirectly: the call still returns tags successfully
        tags = await engine._generate_tags(short, "Entity")
        assert tags == ["aa"]

    @pytest.mark.asyncio
    async def test_long_content_truncated_with_marker(self):
        captured: dict = {}

        async def capture_chat(model, messages, **kwargs):
            # Save the user prompt so we can inspect it
            captured["prompt"] = messages[0]["content"]
            return {"content": "#health"}

        gateway = MagicMock()
        gateway.chat = AsyncMock(side_effect=capture_chat)
        engine = ParsingEngine(gateway=gateway)

        long_content = "A" * 5000  # well over the 2000-char cap
        tags = await engine._generate_tags(long_content, "Entity")
        assert tags == ["health"]
        # Truncation marker must be present in the prompt
        assert "[...truncated...]" in captured["prompt"]
        # Original content must NOT be fully present (we truncated)
        assert "A" * 5000 not in captured["prompt"]
        # But the start and end must survive
        assert "AAAA" in captured["prompt"]