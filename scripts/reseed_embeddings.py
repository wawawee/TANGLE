#!/usr/bin/env python3
"""Re-seed TANGLE wiki embeddings with the current EMBEDDING_SOURCE.

Drops the existing Qdrant collection (its vector dim is likely wrong from the
previous OpenRouter text-embedding-3-small / 1536-dim setup), then re-embeds
every wiki entry from SQLite via the active embedding source (default: local
Ollama qwen3-embedding:8b @ 4096 dim) and re-upserts into Qdrant + Supabase.

SQLite stays the source of truth — we only rewrite the vector mirrors.

Usage:
    python scripts/reseed_embeddings.py [--dry-run] [--entity NAME]

Options:
    --dry-run       Read SQLite, show what would be re-embedded, but skip writes
    --entity NAME   Only re-seed entries for the given entity_name
    --skip-qdrant   Skip Qdrant re-upsert (e.g. for Supabase-only debugging)
    --skip-supabase Skip Supabase re-upsert

Env vars read:
    TANGLE_EMBEDDING_SOURCE    ollama (default) | openrouter | sha256
    TANGLE_OLLAMA_EMBED_MODEL  default: qwen3-embedding:8b
    OLLAMA_NUM_GPU             cap GPU layers during run (Per uses 50 to share with browser)

Exit codes:
    0  success
    1  preflight failure (Ollama down, model missing, Qdrant unreachable, etc.)
    2  partial failure (some entries failed; details printed)
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sqlite3
import sys
import time
from pathlib import Path

# Make backend package importable
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent / "backend"
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO_ROOT))  # so `backend.vector_store` resolves

# Load .env from repo root BEFORE importing vector_store (which reads env at module load).
# The backend main.py does this via python-dotenv too; we replicate here so the script
# works when run standalone (not via uvicorn).
try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass  # python-dotenv not installed; rely on existing env vars

from backend.vector_store import VectorStore, EMBEDDING_DIM, OLLAMA_BASE  # noqa: E402
from backend import vector_store as vs_module  # noqa: E402

DB_PATH = BACKEND_DIR / "tangle.db"
COLLECTION_NAME = "tangle_wiki_memories"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true", help="Read SQLite, show plan, skip writes")
    p.add_argument("--entity", type=str, default=None, help="Only re-seed entries for this entity_name")
    p.add_argument("--skip-qdrant", action="store_true", help="Skip Qdrant re-upsert")
    p.add_argument("--skip-supabase", action="store_true", help="Skip Supabase re-upsert")
    return p.parse_args()


def load_entries(db_path: Path, entity_filter: str | None) -> list[dict]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    if entity_filter:
        cur.execute("SELECT * FROM wiki_entries WHERE entity_name = ? ORDER BY timestamp", (entity_filter,))
    else:
        cur.execute("SELECT * FROM wiki_entries ORDER BY entity_name, timestamp")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def preflight(store: VectorStore) -> list[str]:
    """Return list of human-readable warnings. Empty list = all OK."""
    warnings: list[str] = []
    source = vs_module.EMBEDDING_SOURCE
    model = vs_module.EMBEDDING_MODEL
    print(f"  embedding source : {source}")
    print(f"  embedding model  : {model}")
    print(f"  embedding dim    : {EMBEDDING_DIM}")

    if source == "ollama":
        # Check Ollama reachable + model present
        import httpx
        try:
            r = httpx.get(f"{OLLAMA_BASE}/api/tags", timeout=5)
            if r.status_code != 200:
                warnings.append(f"Ollama at {OLLAMA_BASE} returned {r.status_code}")
            else:
                models = [m["name"] for m in r.json().get("models", [])]
                if model not in models and f"{model}:latest" not in models:
                    warnings.append(
                        f"Ollama model '{model}' not pulled. "
                        f"Run: ollama pull {model}"
                    )
                else:
                    print(f"  ollama reachable : yes ({len(models)} models)")
        except Exception as e:
            warnings.append(f"Ollama unreachable at {OLLAMA_BASE}: {e}")
    elif source == "openrouter":
        if not store.openrouter_key:
            warnings.append("TANGLE_EMBEDDING_SOURCE=openrouter but OPENROUTER_API_KEY not set")
        else:
            print(f"  openrouter key   : set ({'*' * 8}{store.openrouter_key[-4:]})")
    print()
    return warnings


def drop_qdrant_collection(store: VectorStore) -> bool:
    if not store.qclient:
        print("  [qdrant] not configured — skipping collection drop")
        return True
    try:
        store.qclient.delete_collection(collection_name=COLLECTION_NAME)
        print(f"  [qdrant] dropped collection {COLLECTION_NAME!r}")
        return True
    except Exception as e:
        # If collection didn't exist, that's fine
        if "not found" in str(e).lower() or "doesn't exist" in str(e).lower():
            print(f"  [qdrant] collection {COLLECTION_NAME!r} did not exist (ok)")
            return True
        print(f"  [qdrant] drop failed: {e}")
        return False


async def reseed_one(store: VectorStore, entry: dict, args: argparse.Namespace) -> tuple[bool, str]:
    """Re-embed one wiki entry and push to Qdrant + Supabase. Returns (ok, msg)."""
    parsed = {
        "chunk_id": entry["chunk_id"],
        "filename": entry["filename"] or "",
        "filepath": entry["filepath"] or "",
        "raw_content": entry["raw_content"] or "",
        "markdown": entry["markdown"] or "",
        "confidence": entry["confidence"] or 0.0,
        "timestamp": entry["timestamp"] or "",
    }
    try:
        await store.add_wiki_entry(parsed, entity_name=entry["entity_name"])
        return True, "ok"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


async def main_async(args: argparse.Namespace) -> int:
    print(f"DB: {DB_PATH}")
    entries = load_entries(DB_PATH, args.entity)
    print(f"Loaded {len(entries)} wiki entries from SQLite" + (f" (entity={args.entity})" if args.entity else ""))
    print()

    store = VectorStore()
    warnings = preflight(store)

    if warnings:
        print("PREFLIGHT WARNINGS:")
        for w in warnings:
            print(f"  ! {w}")
        if any("unreachable" in w.lower() or "not pulled" in w.lower() or "not set" in w.lower() for w in warnings):
            print("\nAborting — fix warnings above and retry.")
            return 1

    if args.dry_run:
        print("DRY RUN — not writing anything. First 3 entries that would be re-embedded:")
        for e in entries[:3]:
            preview = (e.get("raw_content") or "")[:80].replace("\n", " ")
            print(f"  - {e['entity_name']:25s} {e['chunk_id'][:8]}  {preview!r}")
        if len(entries) > 3:
            print(f"  ... and {len(entries) - 3} more")
        return 0

    # Drop Qdrant collection (skippable)
    if not args.skip_qdrant:
        print("--- Preparing Qdrant collection ---")
        drop_qdrant_collection(store)

    # Re-seed
    print(f"\n--- Re-seeding {len(entries)} entries ---")
    ok_count = 0
    fail_count = 0
    failures: list[tuple[str, str, str]] = []
    start = time.time()

    for i, entry in enumerate(entries, 1):
        ok, msg = await reseed_one(store, entry, args)
        elapsed = time.time() - start
        rate = elapsed / i
        eta = rate * (len(entries) - i)
        status = "OK " if ok else "FAIL"
        print(f"  [{i:3d}/{len(entries)}] {status}  {entry['entity_name']:25s} {entry['chunk_id'][:8]}  ({elapsed:.1f}s, ETA {eta:.0f}s)")
        if ok:
            ok_count += 1
        else:
            fail_count += 1
            failures.append((entry["entity_name"], entry["chunk_id"], msg))

    elapsed = time.time() - start
    print(f"\n=== Done in {elapsed:.1f}s ===")
    print(f"OK: {ok_count} / FAIL: {fail_count}")
    if failures:
        print("\nFailures:")
        for en, cid, msg in failures:
            print(f"  - {en} / {cid[:8]}: {msg}")
        return 2
    return 0


def main() -> int:
    args = parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
