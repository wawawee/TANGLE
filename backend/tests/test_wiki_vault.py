"""Tests for WikiVault — Obsidian-style markdown exporter.

These tests use an isolated SQLite DB and a tempdir vault so they don't
touch real state. They exercise the full export contract:
- chunk files written with YAML frontmatter
- per-entity indexes with backlinks
- master INDEX, TAGS, _meta
- export_all returns a useful summary
- slug + short-id helpers behave
"""

import sys
import sqlite3
from pathlib import Path

import pytest

# Make backend importable
sys.path.insert(0, str(Path(__file__).parent.parent))


from wiki_vault import WikiVault, _slugify, _short_chunk_id  # noqa: E402


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def isolated_db(tmp_path: Path):
    """Create a fresh SQLite DB with the wiki_entries schema and seed 3 rows."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE wiki_entries (
            chunk_id TEXT PRIMARY KEY,
            entity_name TEXT,
            filename TEXT,
            filepath TEXT,
            raw_content TEXT,
            markdown TEXT,
            confidence REAL,
            timestamp TEXT
        )
        """
    )
    rows = [
        (
            "abc12345-1111-2222-3333-444444444444",
            "Luna the Cat",
            "vet_records.pdf",
            "/uploads/vet_records.pdf",
            "Luna had a checkup in September.",
            "# Entity: Luna the Cat\n## Source: vet_records.pdf\n### Confidence: 0.90\n### Tags\n- #health #vet",
            0.90,
            "2026-06-28T10:00:00Z",
        ),
        (
            "def67890-5555-6666-7777-888888888888",
            "Luna the Cat",
            "diet_log.md",
            "/uploads/diet_log.md",
            "Switched to high-protein food.",
            "# Entity: Luna the Cat\n## Source: diet_log.md\n### Confidence: 0.85\n### Tags\n- #diet #health",
            0.85,
            "2026-06-28T11:00:00Z",
        ),
        (
            "ghi11111-aaaa-bbbb-cccc-dddddddddddd",
            "Acme Corp",
            "q2_financials.xlsx",
            "/uploads/q2_financials.xlsx",
            "Q2 revenue up 12% YoY.",
            "# Entity: Acme Corp\n## Source: q2_financials.xlsx\n### Confidence: 0.92\n### Tags\n- #finance #quarterly",
            0.92,
            "2026-06-28T12:00:00Z",
        ),
    ]
    conn.executemany("INSERT INTO wiki_entries VALUES (?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def vault(isolated_db: Path, tmp_path: Path) -> WikiVault:
    """WikiVault pointed at the isolated DB and a fresh tempdir vault."""
    vault_root = tmp_path / "wiki"
    return WikiVault(db_path=isolated_db, vault_root=vault_root)


# ─────────────────────────────────────────────────────────────────────
# Helper tests
# ─────────────────────────────────────────────────────────────────────

class TestSlugAndShortId:
    def test_slugify_lowercases_and_dashes(self):
        assert _slugify("Luna the Cat") == "luna-the-cat"
        assert _slugify("  ACME  Corp!!  ") == "acme-corp"

    def test_slugify_strips_non_ascii(self):
        # Non-ascii chars get stripped by [^a-z0-9]+ → "r-ven-vargen"
        assert _slugify("Räven & Vargen") == "r-ven-vargen"

    def test_slugify_handles_pure_unicode(self):
        # Japanese-only entity name → empty after slugify → "unknown" fallback
        assert _slugify("日本語") == "unknown"

    def test_slugify_keeps_ascii_inside_unicode(self):
        # Mixed: "ñoño" → "o" runs survive as "o-o"
        assert _slugify("Ñoño") == "o-o"

    def test_slugify_handles_empty_and_punctuation_only(self):
        assert _slugify("") == "unknown"
        assert _slugify("---") == "unknown"

    def test_short_chunk_id_is_safe_and_short(self):
        assert _short_chunk_id("abc12345-1111-2222-3333-444444444444") == "abc12345-111"
        # Strips invalid chars and falls back to a placeholder
        assert _short_chunk_id("../etc/passwd") == "etcpasswd"
        assert _short_chunk_id("!!!!") == "unknown"
        assert _short_chunk_id("") == "unknown"


# ─────────────────────────────────────────────────────────────────────
# Export tests
# ─────────────────────────────────────────────────────────────────────

class TestExportAll:
    def test_returns_summary_with_expected_keys(self, vault: WikiVault):
        summary = vault.export_all()
        for key in ("success", "vault_root", "entities", "chunks", "entity_indexes", "duration_ms", "exported_at"):
            assert key in summary, f"Missing key: {key}"
        assert summary["success"] is True
        assert summary["chunks"] == 3
        assert summary["entities"] == 2  # Luna + Acme
        assert summary["entity_indexes"] == 2

    def test_creates_vault_directory_structure(self, vault: WikiVault):
        vault.export_all()
        assert vault.vault_root.exists()
        assert (vault.vault_root / "INDEX.md").exists()
        assert (vault.vault_root / "TAGS.md").exists()
        assert (vault.vault_root / "_meta.md").exists()
        assert (vault.vault_root / "entities" / "luna-the-cat" / "INDEX.md").exists()
        assert (vault.vault_root / "entities" / "acme-corp" / "INDEX.md").exists()

    def test_writes_one_chunk_file_per_db_row(self, vault: WikiVault):
        vault.export_all()
        luna_chunks = list(
            (vault.vault_root / "entities" / "luna-the-cat" / "chunks").glob("*.md")
        )
        acme_chunks = list(
            (vault.vault_root / "entities" / "acme-corp" / "chunks").glob("*.md")
        )
        assert len(luna_chunks) == 2
        assert len(acme_chunks) == 1

    def test_chunk_files_have_yaml_frontmatter(self, vault: WikiVault):
        vault.export_all()
        chunk_file = next(
            (vault.vault_root / "entities" / "luna-the-cat" / "chunks").glob("*.md")
        )
        content = chunk_file.read_text()
        assert content.startswith("---\n")
        assert "chunk_id:" in content
        assert "entity: \"Luna the Cat\"" in content
        assert "confidence: 0.90" in content
        # Tags from the body should appear in frontmatter
        assert "tags:" in content

    def test_chunk_files_have_obsidian_wikilinks(self, vault: WikiVault):
        vault.export_all()
        chunk_file = next(
            (vault.vault_root / "entities" / "luna-the-cat" / "chunks").glob("*.md")
        )
        content = chunk_file.read_text()
        # Obsidian backlink footer
        assert "[[luna-the-cat/INDEX" in content
        assert "## Backlinks" in content

    def test_per_entity_index_lists_all_chunks(self, vault: WikiVault):
        vault.export_all()
        idx = (vault.vault_root / "entities" / "luna-the-cat" / "INDEX.md").read_text()
        # Both Luna chunks should be linked
        assert idx.count("[[luna-the-cat/") == 2
        assert "## Chunks" in idx
        # Luna + Acme share no tags in this fixture, so Related Entities is omitted
        assert "## Related Entities" not in idx

    def test_related_entities_appear_when_tags_overlap(self, tmp_path: Path):
        """When two entities share tags, the per-entity index surfaces a Related section."""
        db_path = tmp_path / "tagged.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE wiki_entries (chunk_id TEXT PRIMARY KEY, entity_name TEXT, "
            "filename TEXT, filepath TEXT, raw_content TEXT, markdown TEXT, "
            "confidence REAL, timestamp TEXT)"
        )
        conn.executemany(
            "INSERT INTO wiki_entries VALUES (?,?,?,?,?,?,?,?)",
            [
                (
                    "11111111-aaaa-bbbb-cccc-111111111111",
                    "Luna",
                    "a.md",
                    "/a",
                    "x",
                    "# Entity: Luna\n### Tags\n- #health #vet",
                    0.9,
                    "2026-01-01T00:00:00Z",
                ),
                (
                    "22222222-aaaa-bbbb-cccc-222222222222",
                    "Milo",
                    "b.md",
                    "/b",
                    "y",
                    "# Entity: Milo\n### Tags\n- #health #play",
                    0.9,
                    "2026-01-01T00:00:00Z",
                ),
            ],
        )
        conn.commit()
        conn.close()
        v = WikiVault(db_path=db_path, vault_root=tmp_path / "vault")
        v.export_all()
        idx = (v.vault_root / "entities" / "luna" / "INDEX.md").read_text()
        assert "## Related Entities" in idx
        assert "Milo" in idx
        assert "1 shared chunk" in idx

    def test_master_index_lists_all_entities(self, vault: WikiVault):
        vault.export_all()
        idx = (vault.vault_root / "INDEX.md").read_text()
        assert "Luna the Cat" in idx
        assert "Acme Corp" in idx
        assert "[[luna-the-cat/INDEX" in idx
        assert "[[acme-corp/INDEX" in idx

    def test_tags_index_groups_chunks(self, vault: WikiVault):
        vault.export_all()
        tags = (vault.vault_root / "TAGS.md").read_text()
        assert "#health" in tags
        assert "#vet" in tags
        assert "#finance" in tags

    def test_meta_has_counters(self, vault: WikiVault):
        vault.export_all()
        meta = (vault.vault_root / "_meta.md").read_text()
        assert "chunks_total: 3" in meta
        assert "entities_total: 2" in meta

    def test_export_on_empty_db_succeeds(self, tmp_path: Path):
        """Exporting from an empty (missing) DB should produce a valid empty vault."""
        empty_db = tmp_path / "empty.db"
        # Don't create the file at all — export_all should handle gracefully
        v = WikiVault(db_path=empty_db, vault_root=tmp_path / "vault_empty")
        summary = v.export_all()
        assert summary["success"] is True
        assert summary["chunks"] == 0
        assert summary["entities"] == 0

    def test_export_is_idempotent(self, vault: WikiVault):
        """Re-running export produces the same files (full rebuild every time)."""
        first = vault.export_all()
        second = vault.export_all()
        assert first["chunks"] == second["chunks"]
        assert first["entities"] == second["entities"]
        # Same number of files on disk after both runs
        files_after_first = len(list(vault.vault_root.rglob("*.md")))
        second_again = vault.export_all()
        files_after_second = len(list(vault.vault_root.rglob("*.md")))
        assert files_after_first == files_after_second

    def test_cleanup_removes_stale_entity_directory(self, tmp_path: Path):
        """An entity directory on disk with no matching SQLite entry is removed on next export."""
        db_path = tmp_path / "stale.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE wiki_entries (chunk_id TEXT PRIMARY KEY, entity_name TEXT, "
            "filename TEXT, filepath TEXT, raw_content TEXT, markdown TEXT, "
            "confidence REAL, timestamp TEXT)"
        )
        conn.execute(
            "INSERT INTO wiki_entries VALUES (?,?,?,?,?,?,?,?)",
            (
                "11111111-aaaa-bbbb-cccc-111111111111",
                "Active",
                "a.md",
                "/a",
                "x",
                "# Entity: Active\n### Tags\n- #a",
                0.9,
                "2026-01-01T00:00:00Z",
            ),
        )
        conn.commit()
        conn.close()
        v = WikiVault(db_path=db_path, vault_root=tmp_path / "vault")
        v.export_all()
        # Active exists
        assert (v.vault_root / "entities" / "active").exists()

        # Now remove that entry from SQLite and re-export — stale dir must disappear
        conn = sqlite3.connect(str(db_path))
        conn.execute("DELETE FROM wiki_entries")
        conn.commit()
        conn.close()
        v.export_all()
        assert not (v.vault_root / "entities" / "active").exists()
        # Master INDEX shouldn't list it
        assert "Active" not in (v.vault_root / "INDEX.md").read_text()

    def test_cleanup_removes_stale_chunk_files(self, tmp_path: Path):
        """Stale chunk files under a still-existing entity dir are removed."""
        db_path = tmp_path / "mixed.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE wiki_entries (chunk_id TEXT PRIMARY KEY, entity_name TEXT, "
            "filename TEXT, filepath TEXT, raw_content TEXT, markdown TEXT, "
            "confidence REAL, timestamp TEXT)"
        )
        conn.executemany(
            "INSERT INTO wiki_entries VALUES (?,?,?,?,?,?,?,?)",
            [
                ("11111111-aaaa-bbbb-cccc-111111111111", "Acme", "a.md", "/a", "x", "# Entity: Acme", 0.9, "2026-01-01T00:00:00Z"),
                ("22222222-aaaa-bbbb-cccc-222222222222", "Acme", "b.md", "/b", "y", "# Entity: Acme", 0.9, "2026-01-01T00:00:00Z"),
            ],
        )
        conn.commit()
        conn.close()
        v = WikiVault(db_path=db_path, vault_root=tmp_path / "vault")
        v.export_all()
        chunks_dir = v.vault_root / "entities" / "acme" / "chunks"
        before = sorted(p.name for p in chunks_dir.glob("*.md"))
        assert len(before) == 2

        # Delete one entry, re-export, the corresponding chunk file should vanish
        conn = sqlite3.connect(str(db_path))
        conn.execute("DELETE FROM wiki_entries WHERE chunk_id = ?", ("11111111-aaaa-bbbb-cccc-111111111111",))
        conn.commit()
        conn.close()
        v.export_all()
        after = sorted(p.name for p in chunks_dir.glob("*.md"))
        assert len(after) == 1
        # The remaining one must be the surviving entry's short id (12 chars)
        assert "22222222-aaa" in after[0]


class TestCount:
    def test_count_returns_zero_for_missing_vault(self, tmp_path: Path):
        v = WikiVault(db_path=tmp_path / "x.db", vault_root=tmp_path / "no_such_vault")
        c = v.count()
        assert c["exists"] is False
        assert c["files"] == 0
        assert c["entities"] == 0
        assert c["last_modified"] is None  # explicitly None, not 0

    def test_count_after_export(self, vault: WikiVault):
        vault.export_all()
        c = vault.count()
        assert c["exists"] is True
        assert c["files"] == 8  # 3 chunks + 2 entity idx + INDEX + TAGS + _meta
        assert c["entities"] == 2
        assert c["last_modified"] is not None
        assert c["last_modified"].endswith("Z")  # ISO timestamp


class TestPreviewExport:
    def test_preview_does_not_write_files(self, vault: WikiVault):
        """preview_export() must be a true dry-run."""
        before = len(list(vault.vault_root.rglob("*.md"))) if vault.vault_root.exists() else 0
        preview = vault.preview_export()
        after = len(list(vault.vault_root.rglob("*.md"))) if vault.vault_root.exists() else 0
        assert before == after, "preview_export must not write files"
        assert preview["dry_run"] is True
        assert preview["would_write"] == 8  # 3 chunks + 2 entity idx + INDEX + TAGS + _meta
        assert preview["vault_root"] == str(vault.vault_root)
        assert "Luna the Cat" in preview["by_entity"]
        assert "Acme Corp" in preview["by_entity"]

    def test_preview_on_empty_db(self, tmp_path: Path):
        v = WikiVault(db_path=tmp_path / "empty.db", vault_root=tmp_path / "vault")
        preview = v.preview_export()
        assert preview["would_write"] == 3  # 0 chunks + 0 entity idx + INDEX/TAGS/_meta
        assert preview["by_entity"] == {}


class TestInlineTagExtraction:
    def test_extracts_simple_tags(self, vault: WikiVault):
        tags = vault._extract_inline_tags("#health #vet #cute-cat")
        assert "health" in tags
        assert "vet" in tags
        assert "cute-cat" in tags

    def test_ignores_hash_inside_words(self, vault: WikiVault):
        # C# should not be tagged, but #csharp should
        tags = vault._extract_inline_tags("Using C# for the API. Love #csharp.")
        assert "csharp" in tags
        assert "c" not in tags  # single-letter C is not a tag