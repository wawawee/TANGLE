"""Tests for AgentOrchestrator — focused on synthesizer dual-output contract.

These tests exercise the static helpers and the synthesize() method with a
mocked FreeGateway so we don't need LLM credentials to verify the contract.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Make backend importable
sys.path.insert(0, str(Path(__file__).parent.parent))


from agent_orchestrator import AgentOrchestrator  # noqa: E402


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _orchestrator_with_mock_gateway(mock_chat_return):
    """Build an AgentOrchestrator with a mocked FreeGateway.chat() method."""
    gateway = MagicMock()
    if isinstance(mock_chat_return, Exception):
        gateway.chat = AsyncMock(side_effect=mock_chat_return)
    else:
        gateway.chat = AsyncMock(return_value=mock_chat_return)
    # Methods called after synthesize() by run_mission(); not exercised here
    gateway.get_mission_usage = MagicMock(return_value={})
    return AgentOrchestrator(gateway=gateway)


# ─────────────────────────────────────────────────────────────────────
# Static helpers
# ─────────────────────────────────────────────────────────────────────

class TestSplitSynthResponse:
    """Regex split of dual-delimited LLM response into (report, wiki_body)."""

    def test_both_blocks_present(self):
        raw = """Some preamble.

===TANGLE_REPORT_START===
# Report

This is the human-readable report.

```json
{"nodes": [{"id": "n1", "label": "Test", "type": "info"}]}
```
===TANGLE_REPORT_END===

===TANGLE_WIKI_START===
Opening paragraph for entity Test.

## Findings
- finding one
- finding two

### Tags
- #test #fixture
===TANGLE_WIKI_END===

Some trailing text."""

        report, wiki = AgentOrchestrator._split_synth_response(raw)

        assert "# Report" in report
        assert "This is the human-readable report." in report
        assert '{"nodes"' in report  # the wiki-nodes JSON block survives
        assert "Opening paragraph" in wiki
        assert "## Findings" in wiki
        assert "#test #fixture" in wiki
        assert "Some preamble" not in report
        assert "Some trailing text" not in report

    def test_no_delimiters_returns_empty(self):
        raw = "Just plain text without any delimiters whatsoever."
        report, wiki = AgentOrchestrator._split_synth_response(raw)
        assert report == ""
        assert wiki == ""

    def test_only_report_block(self):
        raw = "===TANGLE_REPORT_START===\nJust the report.\n===TANGLE_REPORT_END==="
        report, wiki = AgentOrchestrator._split_synth_response(raw)
        assert "Just the report" in report
        assert wiki == ""

    def test_only_wiki_block(self):
        raw = "===TANGLE_WIKI_START===\nJust the wiki.\n===TANGLE_WIKI_END==="
        report, wiki = AgentOrchestrator._split_synth_response(raw)
        assert report == ""
        assert "Just the wiki" in wiki

    def test_empty_string(self):
        assert AgentOrchestrator._split_synth_response("") == ("", "")

    def test_whitespace_around_delimiters_tolerated(self):
        raw = (
            "===TANGLE_REPORT_START===\n\n  Report body  \n\n"
            "===TANGLE_REPORT_END===\n\n"
            "===TANGLE_WIKI_START===\n\n  Wiki body  \n\n"
            "===TANGLE_WIKI_END==="
        )
        report, wiki = AgentOrchestrator._split_synth_response(raw)
        assert report == "Report body"
        assert wiki == "Wiki body"


class TestAssembleWikiEntry:
    """Wraps LLM-produced wiki body with deterministic metadata headers."""

    def test_metadata_headers_match_spec(self):
        entry = AgentOrchestrator._assemble_wiki_entry(
            entity_name="Test Cat",
            source_filename="tangle-synthesis-test-cat-2026-06-28.md",
            timestamp="2026-06-28T15:00:00Z",
            confidence=0.85,
            chunk_id="abc-123-uuid",
            body="Opening paragraph.\n\n## Findings\n- thing",
        )

        # Wiki spec (per AGENTS.md):
        # # Entity: [Name]
        # ## Source: [Filename]
        # ### Extracted: [ISO Timestamp]
        # ### Confidence: [0.00–1.00]
        # ### Chunk ID: [uuid]
        assert entry.startswith("# Entity: Test Cat\n")
        assert "## Source: tangle-synthesis-test-cat-2026-06-28.md" in entry
        assert "### Extracted: 2026-06-28T15:00:00Z" in entry
        assert "### Confidence: 0.85" in entry
        assert "### Chunk ID: abc-123-uuid" in entry
        # Body and tags sections preserved
        assert "Opening paragraph." in entry
        assert "## Findings" in entry
        assert "### Related Chunks" in entry
        assert "[[source-file:tangle-synthesis-test-cat-2026-06-28.md]]" in entry
        assert "#synthesized" in entry

    def test_confidence_rounded_to_two_decimals(self):
        entry = AgentOrchestrator._assemble_wiki_entry(
            entity_name="X",
            source_filename="x.md",
            timestamp="2026-06-28T00:00:00Z",
            confidence=0.85123,  # should round to 0.85
            chunk_id="uuid-x",
            body="body",
        )
        assert "### Confidence: 0.85" in entry


class TestConfidenceFromCritic:
    """Maps critic outcome to wiki-entry confidence score."""

    def test_passed_gate_uses_critic_score(self):
        # critic verified + score >= 0.7 → use critic score
        assert AgentOrchestrator._confidence_from_critic(0.85, True) == 0.85
        assert AgentOrchestrator._confidence_from_critic(0.95, True) == 0.95

    def test_failed_verified_gate_returns_half(self):
        # critic verified but score < 0.7 → 0.5 (gate failed but content exists)
        assert AgentOrchestrator._confidence_from_critic(0.5, True) == 0.5
        assert AgentOrchestrator._confidence_from_critic(0.3, True) == 0.5

    def test_unverified_returns_half(self):
        # critic errored → 0.5
        assert AgentOrchestrator._confidence_from_critic(0.85, False) == 0.5
        assert AgentOrchestrator._confidence_from_critic(0.3, False) == 0.5

    def test_no_score_returns_half(self):
        # critic never returned a score → 0.5
        assert AgentOrchestrator._confidence_from_critic(None, True) == 0.5
        assert AgentOrchestrator._confidence_from_critic(None, False) == 0.5


# ─────────────────────────────────────────────────────────────────────
# synthesize() — mocked gateway
# ─────────────────────────────────────────────────────────────────────

class TestSynthesizeDualOutput:
    """Verifies the synthesize() method returns dual output and that
    wiki metadata is deterministic."""

    def _dual_llm_response(self) -> str:
        """Build a realistic-looking LLM response honoring both delimiters."""
        return """I have compiled the findings below.

===TANGLE_REPORT_START===
# Mission Report: Luna the Cat

Luna is a 3-year-old rescue cat with mild dental issues.

## Recommended actions
- Schedule dental cleaning
- Switch to dental diet kibble

```json
{"nodes": [
  {"id": "node_1", "label": "Dental cleaning", "type": "warning", "details": "Schedule vet visit"},
  {"id": "node_2", "label": "Dental diet", "type": "info", "details": "Switch kibble"}
]}
```
===TANGLE_REPORT_END===

===TANGLE_WIKI_START===
Luna is a 3-year-old rescue cat with mild dental issues requiring attention.

## Findings
**(Scout)** Common dental issues in young rescue cats include gingivitis (mild).

**(Librarian)** Uploaded vet records from 2026-04 confirm tartar buildup.

## Recommended Actions
1. Schedule professional dental cleaning
2. Switch to dental-specific kibble

## Open Questions
- Does Luna have any allergies to dental diet ingredients?

### Tags
- #health #dental #urgent #cat #rescue
===TANGLE_WIKI_END===
"""

    @pytest.mark.asyncio
    async def test_returns_dict_with_three_fields(self):
        orch = _orchestrator_with_mock_gateway(
            {"content": self._dual_llm_response(), "usage": {}}
        )
        result = await orch.synthesize(
            findings=["scout finding", "librarian finding"],
            entity_name="Luna the Cat",
        )

        assert isinstance(result, dict)
        assert "report_markdown" in result
        assert "wiki_entry_markdown" in result
        assert "wiki_entry_chunk_id" in result

    @pytest.mark.asyncio
    async def test_report_markdown_preserves_json_block(self):
        orch = _orchestrator_with_mock_gateway(
            {"content": self._dual_llm_response(), "usage": {}}
        )
        result = await orch.synthesize(findings=["x"], entity_name="Luna")

        # The frontend reads this block via /```json\s*([\s\S]*?)\s*```/ — must parse
        import re
        m = re.search(r"```json\s*([\s\S]*?)\s*```", result["report_markdown"])
        assert m is not None, "report_markdown lost the ```json wiki-nodes block"
        import json
        parsed = json.loads(m.group(1))
        assert "nodes" in parsed
        assert len(parsed["nodes"]) == 2

    @pytest.mark.asyncio
    async def test_wiki_entry_has_all_spec_headers(self):
        orch = _orchestrator_with_mock_gateway(
            {"content": self._dual_llm_response(), "usage": {}}
        )
        result = await orch.synthesize(
            findings=["x"], entity_name="Luna the Cat",
            critic_score=0.85, verified=True,
        )
        wiki = result["wiki_entry_markdown"]

        assert wiki.startswith("# Entity: Luna the Cat\n")
        assert "## Source:" in wiki
        assert "tangle-synthesis-luna-the-cat" in wiki
        assert "### Extracted:" in wiki
        assert "### Confidence: 0.85" in wiki
        assert "### Chunk ID:" in wiki
        assert result["wiki_entry_chunk_id"] in wiki  # chunk_id is in the entry

    @pytest.mark.asyncio
    async def test_chunk_id_is_uuid_string(self):
        orch = _orchestrator_with_mock_gateway(
            {"content": self._dual_llm_response(), "usage": {}}
        )
        result = await orch.synthesize(findings=["x"], entity_name="X")
        import uuid as uuid_mod
        # Should parse as a valid UUID
        uuid_mod.UUID(result["wiki_entry_chunk_id"])

    @pytest.mark.asyncio
    async def test_confidence_uses_critic_when_verified(self):
        orch = _orchestrator_with_mock_gateway(
            {"content": self._dual_llm_response(), "usage": {}}
        )
        result = await orch.synthesize(
            findings=["x"], entity_name="X",
            critic_score=0.92, verified=True,
        )
        assert "### Confidence: 0.92" in result["wiki_entry_markdown"]

    @pytest.mark.asyncio
    async def test_confidence_drops_to_half_when_unverified(self):
        orch = _orchestrator_with_mock_gateway(
            {"content": self._dual_llm_response(), "usage": {}}
        )
        result = await orch.synthesize(
            findings=["x"], entity_name="X",
            critic_score=0.92, verified=False,
        )
        assert "### Confidence: 0.50" in result["wiki_entry_markdown"]

    @pytest.mark.asyncio
    async def test_llm_failure_returns_stub_not_crash(self):
        orch = _orchestrator_with_mock_gateway(
            RuntimeError("LLM provider offline")
        )
        result = await orch.synthesize(findings=["x"], entity_name="X")

        assert "Synthesis failed" in result["report_markdown"]
        assert result["wiki_entry_markdown"] == ""
        assert result["wiki_entry_chunk_id"]  # still has a chunk_id for tracking

    @pytest.mark.asyncio
    async def test_missing_delimiters_uses_raw_content(self):
        """If LLM ignores the delimiters, fall back to raw content (with warning).

        The wiki_entry_markdown is ALWAYS wrapped with metadata headers so it
        remains wiki-spec compliant, even on degraded path.
        """
        orch = _orchestrator_with_mock_gateway(
            {"content": "Just some text without any markers.", "usage": {}}
        )
        result = await orch.synthesize(findings=["x"], entity_name="X")

        # report_markdown is just the raw content
        assert result["report_markdown"] == "Just some text without any markers."
        # wiki_entry_markdown is the raw content WRAPPED with metadata
        assert "# Entity: X" in result["wiki_entry_markdown"]
        assert "Just some text without any markers." in result["wiki_entry_markdown"]
        assert "### Confidence: 0.50" in result["wiki_entry_markdown"]


# ─────────────────────────────────────────────────────────────────────
# end-to-end: dual output flows through run_mission return payload
# ─────────────────────────────────────────────────────────────────────

class TestMissionResponseShape:
    """Verifies run_mission() re-ingests the wiki entry and returns new fields."""

    @pytest.mark.asyncio
    async def test_synth_result_is_re_ingested_into_vector_store(self):
        gateway = MagicMock()
        call_count = {"n": 0}

        async def fake_chat(model, messages, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                # planner
                return {"content": "Plan: research X", "usage": {}}
            # synthesizer (every subsequent call)
            return {
                "content": (
                    "===TANGLE_REPORT_START===\n"
                    "# Report\n\nThis is the report.\n\n"
                    "```json\n{\"nodes\": []}\n```\n"
                    "===TANGLE_REPORT_END===\n\n"
                    "===TANGLE_WIKI_START===\n"
                    "Wiki body content here.\n\n### Tags\n- #test\n"
                    "===TANGLE_WIKI_END==="
                ),
                "usage": {},
            }
        gateway.chat = AsyncMock(side_effect=fake_chat)
        gateway.get_mission_usage = MagicMock(return_value={})

        orch = AgentOrchestrator(gateway=gateway)
        added_entries = []

        async def fake_add(parsed, entity):
            added_entries.append({"parsed": parsed, "entity": entity})

        orch.vector_store.add_wiki_entry = fake_add
        orch.vector_store.save_mission = MagicMock()
        orch.vector_store.search_wiki = AsyncMock(return_value=[])

        result = await orch.run_mission(entity_name="TestCat")

        # No file uploaded for this test, so only the synthesized entry should be added
        assert len(added_entries) == 1, f"Expected 1 re-ingestion, got {len(added_entries)}"
        entry = added_entries[0]
        assert entry["entity"] == "TestCat"
        assert entry["parsed"]["markdown"].startswith("# Entity: TestCat\n")
        assert "Wiki body content here." in entry["parsed"]["markdown"]
        assert entry["parsed"]["is_image"] is False
        assert entry["parsed"]["chunk_id"] == result["wiki_entry_chunk_id"]

    @pytest.mark.asyncio
    async def test_run_mission_returns_dual_output_fields(self):
        """Mission response exposes report_markdown + wiki_entry_markdown."""
        gateway = MagicMock()

        async def fake_chat(model, messages, **kwargs):
            return {
                "content": (
                    "===TANGLE_REPORT_START===\n# Report\n\n"
                    "Body.\n\n```json\n{\"nodes\": []}\n```\n"
                    "===TANGLE_REPORT_END===\n\n"
                    "===TANGLE_WIKI_START===\nWiki body.\n\n### Tags\n- #x\n"
                    "===TANGLE_WIKI_END==="
                ),
                "usage": {},
            }
        gateway.chat = AsyncMock(side_effect=fake_chat)
        gateway.get_mission_usage = MagicMock(return_value={})

        orch = AgentOrchestrator(gateway=gateway)
        orch.vector_store.add_wiki_entry = AsyncMock()
        orch.vector_store.save_mission = MagicMock()
        orch.vector_store.search_wiki = AsyncMock(return_value=[])

        result = await orch.run_mission(entity_name="X")

        # New dual-output fields exposed
        assert "report_markdown" in result
        assert "wiki_entry_markdown" in result
        assert "wiki_entry_chunk_id" in result
        # Backwards compat: data.report still works for frontend
        assert result["report"] == result["report_markdown"]
        # Wiki entry is wiki-spec compliant
        assert result["wiki_entry_markdown"].startswith("# Entity: X\n")
        assert "Wiki body." in result["wiki_entry_markdown"]
