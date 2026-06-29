"""TANGLE Wiki Vault — Obsidian-compatible markdown exporter.

Reads the canonical wiki_entries from SQLite and writes a browsable vault
to .tangle/vault/ (or whatever TANGLE_VAULT_ROOT points to). Designed so
the user can open the directory in Obsidian (or any markdown editor) and
navigate the knowledge graph via wikilinks.

The vault path is gitignored on purpose — wiki content is generated,
not authored. If you want Obsidian to read it live, point Obsidian at
the vault path (or symlink it). A previously-committed docs/wiki/ tree
can stay as historical reference, but live exports go to the gitignored
location so accidentally-leaked cross-project content can't end up in
git by accident.

Vault layout (created on first export, refreshed on every call):

    <vault_root>/
    ├── _meta.md                     # vault metadata, last export time, counts
    ├── INDEX.md                     # master entity index (alphabetical)
    ├── TAGS.md                      # tag → chunk cross-reference
    └── entities/
        └── {entity_slug}/
            ├── INDEX.md             # per-entity chunk list + backlinks
            └── chunks/
                └── {chunk_short}.md # one file per chunk

Each chunk file has:
- YAML frontmatter (Obsidian-readable metadata)
- The full TANGLE wiki-spec body
- Resolved [[wikilinks]] (chunk-id references + source-file references)

Toggle: set env TANGLE_WIKI_EXPORT_ON_MISSION=0 to disable auto-export
on mission completion (manual /api/admin/export-wiki still works).

Override default path: export TANGLE_VAULT_ROOT=/some/path/vault
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("tangle.wiki")

# Vault lives at the repo root (parent of backend/), same convention as TASKLIST.md.
# Path is gitignored by design — wiki content is generated, not authored, so it
# shouldn't accidentally end up in version control. Override via TANGLE_VAULT_ROOT
# if you want Obsidian to read it live (e.g. TANGLE_VAULT_ROOT=~/Documents/tangle-vault).
def _resolve_default_vault_root() -> Path:
    env_root = os.getenv("TANGLE_VAULT_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    return Path(__file__).parent.parent / ".tangle" / "vault"

DEFAULT_VAULT_ROOT = _resolve_default_vault_root()
DEFAULT_DB_PATH = Path(__file__).parent / "tangle.db"


def _slugify(value: str) -> str:
    """Filesystem-safe slug from an entity name. Lowercase, ascii-ish."""
    s = value.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s or "unknown"


def _short_chunk_id(chunk_id: str) -> str:
    """Short, filesystem-safe chunk identifier. First 12 valid chars of the UUID
    is plenty for Obsidian link resolution within a single vault.
    Returns 'unknown' if the input has no usable characters."""
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "", chunk_id)[:12]
    return cleaned or "unknown"


class WikiVault:
    """Reads SQLite wiki_entries and writes an Obsidian-compatible vault."""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        vault_root: Optional[Path] = None,
    ):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.vault_root = vault_root or DEFAULT_VAULT_ROOT

    # ─────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────

    def export_all(self) -> Dict[str, Any]:
        """Rebuild the entire vault from SQLite. Returns a summary dict
        suitable for an API response or a CLI log line.

        Cleans stale files first: any entity dir or chunk file on disk that
        doesn't correspond to a current SQLite entry is removed. This keeps
        the vault in sync with whatever's in the DB after deletions.
        """
        started = datetime.now(timezone.utc)
        entries = self._read_all_entries()
        self.vault_root.mkdir(parents=True, exist_ok=True)

        # Group entries by entity for per-entity indexes
        by_entity: Dict[str, List[Dict[str, Any]]] = {}
        for entry in entries:
            entity = entry.get("entity_name") or "unknown"
            by_entity.setdefault(entity, []).append(entry)

        # Compute the set of entity slugs and chunk short-ids that should exist.
        # Anything else on disk is stale and gets removed before we write fresh.
        expected_entity_slugs = {_slugify(e) for e in by_entity.keys()}
        expected_chunk_shorts: Dict[str, set] = {}
        for entity, ents in by_entity.items():
            slug = _slugify(entity)
            expected_chunk_shorts[slug] = {_short_chunk_id(e["chunk_id"]) for e in ents}
        self._cleanup_stale(expected_entity_slugs, expected_chunk_shorts)

        # 1. Per-chunk files
        chunk_files_written = 0
        for entry in entries:
            self._write_chunk_file(entry)
            chunk_files_written += 1

        # 2. Per-entity indexes (also accumulates backlink data per entity)
        entity_indexes_written = 0
        for entity, ents in by_entity.items():
            self._write_entity_index(entity, ents, by_entity)
            entity_indexes_written += 1

        # 3. Master INDEX, TAGS, _meta
        self._write_master_index(by_entity)
        self._write_tags_index(by_entity)
        self._write_meta(entries, started)

        duration_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        summary = {
            "success": True,
            "vault_root": str(self.vault_root),
            "entities": len(by_entity),
            "chunks": chunk_files_written,
            "entity_indexes": entity_indexes_written,
            "duration_ms": duration_ms,
            "exported_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        logger.info(
            f"WikiVault export: {chunk_files_written} chunks across "
            f"{len(by_entity)} entities in {duration_ms}ms → {self.vault_root}"
        )
        return summary

    def count(self) -> Dict[str, Any]:
        """Cheap disk-level counts for the index endpoint. Doesn't read SQLite.
        Returns last_modified=None for an empty vault so callers can distinguish
        'never exported' from 'exported at epoch zero'."""
        if not self.vault_root.exists():
            return {"files": 0, "entities": 0, "exists": False, "last_modified": None}

        all_md = list(self.vault_root.rglob("*.md"))
        entity_dirs = list((self.vault_root / "entities").glob("*")) if (self.vault_root / "entities").exists() else []
        last_modified_ts = max((p.stat().st_mtime for p in all_md), default=None)
        return {
            "files": len(all_md),
            "entities": len([d for d in entity_dirs if d.is_dir()]),
            "exists": True,
            "last_modified": (
                datetime.fromtimestamp(last_modified_ts, tz=timezone.utc)
                    .isoformat().replace("+00:00", "Z")
                if last_modified_ts is not None else None
            ),
        }

    def preview_export(self) -> Dict[str, Any]:
        """Public method: shows what export_all() would write without touching disk.
        Used by the GET /api/admin/export-wiki/preview endpoint."""
        entries = self._read_all_entries()
        by_entity: Dict[str, int] = {}
        for e in entries:
            ent = e.get("entity_name") or "unknown"
            by_entity[ent] = by_entity.get(ent, 0) + 1
        return {
            "would_write": len(entries) + len(by_entity) + 3,  # chunks + per-entity idx + master
            "vault_root": str(self.vault_root),
            "by_entity": dict(sorted(by_entity.items(), key=lambda kv: kv[0].lower())),
            "dry_run": True,
        }

    def _cleanup_stale(
        self,
        expected_entity_slugs: set,
        expected_chunk_shorts: Dict[str, set],
    ) -> None:
        """Remove stale entity dirs and chunk files that no longer correspond
        to anything in SQLite. Idempotent — safe to call on a fresh vault."""
        if not self.vault_root.exists():
            return
        entities_dir = self.vault_root / "entities"
        if not entities_dir.exists():
            return
        for slug_dir in entities_dir.iterdir():
            if not slug_dir.is_dir():
                continue
            slug = slug_dir.name
            if slug not in expected_entity_slugs:
                # Entire entity removed from SQLite — drop the directory
                shutil.rmtree(slug_dir, ignore_errors=True)
                continue
            # Entity still exists — clean stale chunk files under chunks/
            chunks_dir = slug_dir / "chunks"
            if not chunks_dir.exists():
                continue
            keep = expected_chunk_shorts.get(slug, set())
            for chunk_file in chunks_dir.glob("*.md"):
                if chunk_file.stem not in keep:
                    chunk_file.unlink(missing_ok=True)

    # ─────────────────────────────────────────────────────────────
    # Internals
    # ─────────────────────────────────────────────────────────────

    def _read_all_entries(self) -> List[Dict[str, Any]]:
        if not self.db_path.exists():
            logger.warning(f"WikiVault: SQLite db missing at {self.db_path}")
            return []
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT chunk_id, entity_name, filename, filepath, "
                "raw_content, markdown, confidence, timestamp "
                "FROM wiki_entries ORDER BY entity_name ASC, timestamp ASC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def _write_chunk_file(self, entry: Dict[str, Any]) -> Path:
        """Write one chunk as a vault file with YAML frontmatter."""
        chunk_id = entry["chunk_id"]
        entity = entry.get("entity_name") or "unknown"
        slug = _slugify(entity)
        chunk_short = _short_chunk_id(chunk_id)

        chunk_dir = self.vault_root / "entities" / slug / "chunks"
        chunk_dir.mkdir(parents=True, exist_ok=True)
        chunk_file = chunk_dir / f"{chunk_short}.md"

        body = entry.get("markdown") or ""
        # If the markdown body doesn't already start with the wiki spec, prepend it
        body = self._ensure_wiki_headers(body, entry)
        # Resolve [[source-file:X]] → real Obsidian path link
        body = self._resolve_source_file_links(body, entity)
        # Add a backlink footer for Obsidian graph view
        body = self._append_backlink_footer(body, slug, chunk_short, entity)

        frontmatter = self._build_frontmatter(entry)
        chunk_file.write_text(f"{frontmatter}\n\n{body.strip()}\n", encoding="utf-8")
        return chunk_file

    def _ensure_wiki_headers(self, body: str, entry: Dict[str, Any]) -> str:
        """If body is just raw content (no TANGLE wiki headers), inject them.
        This keeps every chunk file self-describing in the vault."""
        if "# Entity:" in body[:200]:
            return body
        timestamp = entry.get("timestamp") or ""
        confidence = entry.get("confidence")
        chunk_id = entry.get("chunk_id", "")
        filename = entry.get("filename", "")
        entity = entry.get("entity_name") or "unknown"
        return (
            f"# Entity: {entity}\n"
            f"## Source: {filename}\n"
            f"### Extracted: {timestamp}\n"
            f"### Confidence: {confidence:.2f}\n"
            f"### Chunk ID: {chunk_id}\n\n"
            f"{body.strip()}\n"
        )

    def _build_frontmatter(self, entry: Dict[str, Any]) -> str:
        """Build Obsidian-style YAML frontmatter with safe quoting."""
        chunk_id = entry.get("chunk_id", "")
        entity = entry.get("entity_name") or "unknown"
        filename = entry.get("filename") or ""
        confidence = entry.get("confidence")
        timestamp = entry.get("timestamp") or ""
        tags = self._extract_inline_tags(entry.get("markdown") or "")

        lines = [
            "---",
            f'chunk_id: "{chunk_id}"',
            f'entity: "{entity.replace(chr(34), chr(92)+chr(34))}"',
            f'source_filename: "{filename.replace(chr(34), chr(92)+chr(34))}"',
        ]
        if confidence is not None:
            lines.append(f"confidence: {float(confidence):.2f}")
        if timestamp:
            lines.append(f'timestamp: "{timestamp}"')
        if tags:
            # YAML inline-list form
            tag_list = ", ".join(f'"{t}"' for t in sorted(tags))
            lines.append(f"tags: [{tag_list}]")
        lines.append("---")
        return "\n".join(lines)

    @staticmethod
    def _extract_inline_tags(markdown: str) -> List[str]:
        """Pull #tags from the body. Hash inside words (e.g. C#) is ignored."""
        return sorted(set(re.findall(r"(?:^|\s)#([a-z0-9][a-z0-9_-]*)", markdown)))

    def _resolve_source_file_links(self, body: str, entity: str) -> str:
        """Intentional no-op: source-file: links pass through unchanged for now."""
        return body

    def _append_backlink_footer(self, body: str, slug: str, chunk_short: str, entity: str) -> str:
        """Add a Backlinks section so Obsidian's graph view picks up the file."""
        footer = (
            f"\n\n---\n\n"
            f"## Backlinks\n\n"
            f"_This chunk is part of the **{entity}** vault._ "
            f"See [[{slug}/INDEX|{entity} index]] for the full set of chunks for this entity.\n"
        )
        if "## Backlinks" not in body:
            body = body.rstrip() + footer
        return body

    def _write_entity_index(
        self,
        entity: str,
        entries: List[Dict[str, Any]],
        all_by_entity: Dict[str, List[Dict[str, Any]]],
    ) -> Path:
        slug = _slugify(entity)
        entity_dir = self.vault_root / "entities" / slug
        entity_dir.mkdir(parents=True, exist_ok=True)
        index_file = entity_dir / "INDEX.md"

        # Build reverse links: which other entities mention this entity or share tags?
        related = self._find_related_entities(entity, entries, all_by_entity)

        lines = [
            f"# {entity}",
            "",
            f"> Wiki index for entity **{entity}** — {len(entries)} chunk(s).",
            "",
            "## Chunks",
            "",
        ]
        for e in entries:
            short = _short_chunk_id(e["chunk_id"])
            ts = (e.get("timestamp") or "")[:10]
            conf = e.get("confidence")
            conf_str = f"{conf:.2f}" if conf is not None else "?"
            filename = e.get("filename") or "?"
            lines.append(
                f"- [[{slug}/{short}|{ts} · {filename} · conf {conf_str}]]"
            )

        if related:
            lines.extend(["", "## Related Entities", ""])
            for rel_entity, shared_count in related[:10]:
                rel_slug = _slugify(rel_entity)
                lines.append(
                    f"- [[{rel_slug}/INDEX|{rel_entity}]] — {shared_count} shared chunk(s)"
                )

        lines.extend(["", "---", "", f"_Generated by TANGLE WikiVault._"])
        index_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return index_file

    def _find_related_entities(
        self,
        entity: str,
        entries: List[Dict[str, Any]],
        all_by_entity: Dict[str, List[Dict[str, Any]]],
    ) -> List[tuple[str, int]]:
        """Rank other entities by tag overlap. Simple co-occurrence, no embeddings."""
        this_tags = set()
        for e in entries:
            this_tags.update(self._extract_inline_tags(e.get("markdown") or ""))

        scored: List[tuple[str, int]] = []
        for other_entity, other_entries in all_by_entity.items():
            if other_entity == entity:
                continue
            other_tags = set()
            for e in other_entries:
                other_tags.update(self._extract_inline_tags(e.get("markdown") or ""))
            overlap = len(this_tags & other_tags)
            if overlap > 0:
                scored.append((other_entity, overlap))
        scored.sort(key=lambda x: (-x[1], x[0].lower()))
        return scored

    def _write_master_index(self, by_entity: Dict[str, List[Dict[str, Any]]]) -> Path:
        index_file = self.vault_root / "INDEX.md"
        total_chunks = sum(len(v) for v in by_entity.values())

        lines = [
            "# TANGLE Wiki Vault — INDEX",
            "",
            f"> {len(by_entity)} entities · {total_chunks} chunks. "
            f"Open this folder in [Obsidian](https://obsidian.md/) for a navigable graph view.",
            "",
            "## Entities",
            "",
        ]
        for entity in sorted(by_entity.keys(), key=str.lower):
            slug = _slugify(entity)
            count = len(by_entity[entity])
            lines.append(f"- [[{slug}/INDEX|{entity}]] ({count} chunk{'s' if count != 1 else ''})")

        lines.extend(
            [
                "",
                "## Cross-References",
                "",
                "- [[TAGS|All tags]]",
                "- [[_meta|Vault metadata]]",
                "",
                "---",
                "",
                "_Generated by TANGLE WikiVault._",
            ]
        )
        index_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return index_file

    def _write_tags_index(self, by_entity: Dict[str, List[Dict[str, Any]]]) -> Path:
        tags_file = self.vault_root / "TAGS.md"
        tag_to_chunks: Dict[str, List[tuple[str, str]]] = {}
        for entity, entries in by_entity.items():
            slug = _slugify(entity)
            for e in entries:
                for tag in self._extract_inline_tags(e.get("markdown") or ""):
                    tag_to_chunks.setdefault(tag, []).append(
                        (slug, _short_chunk_id(e["chunk_id"]))
                    )

        lines = [
            "# TANGLE Wiki Vault — Tags",
            "",
            f"> {len(tag_to_chunks)} distinct tag(s) across all chunks.",
            "",
        ]
        for tag in sorted(tag_to_chunks.keys()):
            chunk_list = tag_to_chunks[tag]
            lines.append(f"## #{tag} ({len(chunk_list)})")
            lines.append("")
            for slug, short in chunk_list:
                lines.append(f"- [[{slug}/{short}]]")
            lines.append("")

        tags_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return tags_file

    def _write_meta(self, entries: List[Dict[str, Any]], started: datetime) -> Path:
        meta_file = self.vault_root / "_meta.md"
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        body = (
            "---\n"
            f'generated_at: "{now}"\n'
            f"chunks_total: {len(entries)}\n"
            f"entities_total: {len(set(e.get('entity_name') for e in entries))}\n"
            "---\n\n"
            "# TANGLE Wiki Vault — Metadata\n\n"
            f"- **Generated at:** {now}\n"
            f"- **Source DB:** `{self.db_path}`\n"
            f"- **Vault root:** `{self.vault_root}`\n"
            f"- **Total chunks:** {len(entries)}\n"
            f"- **Total entities:** {len(set(e.get('entity_name') for e in entries))}\n\n"
            "This vault is auto-generated. Re-run the export to refresh.\n"
        )
        meta_file.write_text(body, encoding="utf-8")
        return meta_file


def export_on_mission_enabled() -> bool:
    """Env toggle: set TANGLE_WIKI_EXPORT_ON_MISSION=0 to disable auto-export."""
    return os.getenv("TANGLE_WIKI_EXPORT_ON_MISSION", "1") not in ("0", "false", "False", "")