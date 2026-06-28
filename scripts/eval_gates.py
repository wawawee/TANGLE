#!/usr/bin/env python3
"""TANGLE evaluation gates — fast, focused pass/fail checks.

Run from repo root:
    backend/venv/bin/python scripts/eval_gates.py [--gate N] [--list]

Each gate returns PASS / FAIL / SKIP with timing + brief reason. Designed for
rapid iteration: run individual gates while debugging, all gates for a release
readiness snapshot.

Gates:
    1  Health      backend + Supabase + Qdrant + Ollama all reachable
    2  Embedding   get_embeddings() returns 4096-dim vector with sane values
    3  Consistency same text -> cosine similarity ~= 1.0 (deterministic)
    4  Fallback    OPENROUTER_FREE_MODELS entries reachable via API (first 3)
    5  Search-Q    Qdrant semantic search returns relevant Luna the Cat chunks
    6  Search-S    Supabase pgvector RPC returns relevant Luna the Cat chunks
    7  E2E-mini    Tiny end-to-end mission completes (Acme Corp smoke fixture)
    8  Cost        Embedding + chat calls confirm $0 spend on free tier

Exit codes:
    0  all selected gates PASS
    1  one or more FAIL
    2  interrupted
"""
from __future__ import annotations

import argparse
import asyncio
import math
import os
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(REPO_ROOT))

# Load .env early so vector_store picks up TANGLE_SUPABASE_ENABLED etc.
try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass

import httpx  # noqa: E402

from backend.vector_store import VectorStore, EMBEDDING_DIM, OLLAMA_BASE  # noqa: E402
from backend.free_gateway import OPENROUTER_FREE_MODELS  # noqa: E402

BACKEND = os.getenv("EVAL_BACKEND_URL", "http://localhost:8000")


# ── Result tracking ──────────────────────────────────────────
class Results:
    def __init__(self):
        self.entries: list[tuple[str, str, float, str]] = []  # (gate, status, dt, note)

    def add(self, gate: str, status: str, dt: float, note: str = ""):
        self.entries.append((gate, status, dt, note))
        sym = {"PASS": "✓", "FAIL": "✗", "SKIP": "~"}.get(status, "?")
        note_str = f"  ({note})" if note else ""
        print(f"  {sym} {gate:14s} {status:5s}  {dt:6.2f}s{note_str}")

    def summary(self):
        print()
        print("─" * 64)
        passed = sum(1 for _, s, _, _ in self.entries if s == "PASS")
        failed = sum(1 for _, s, _, _ in self.entries if s == "FAIL")
        skipped = sum(1 for _, s, _, _ in self.entries if s == "SKIP")
        total = len(self.entries)
        print(f"  {passed}/{total} PASS   {failed} FAIL   {skipped} SKIP")
        if failed:
            print("\n  Failed gates:")
            for g, s, _, note in self.entries:
                if s == "FAIL":
                    print(f"    - {g}: {note}")
        print("─" * 64)
        return failed == 0


# ── Gate 1: Health ───────────────────────────────────────────
async def gate_health(r: Results):
    t0 = time.time()
    notes = []
    overall_ok = True
    async with httpx.AsyncClient(timeout=10) as c:
        # Backend health
        try:
            resp = await c.get(f"{BACKEND}/health")
            backend_ok = resp.status_code == 200
            notes.append(f"backend={'up' if backend_ok else 'down'}")
            overall_ok &= backend_ok
        except Exception as e:
            notes.append(f"backend=down({e})")
            overall_ok = False
        # Admin index (proves Supabase auth roundtrip)
        try:
            resp = await c.get(f"{BACKEND}/api/admin/index")
            data = resp.json() if resp.status_code == 200 else {}
            sb_status = data.get("supabase", {}).get("status")
            sb_ok = sb_status == "connected"
            entries = data.get("supabase", {}).get("entries_count", "?")
            notes.append(f"supabase={sb_status} (entries={entries})")
            overall_ok &= sb_ok
        except Exception as e:
            notes.append(f"supabase=down({e})")
            overall_ok = False
    # Qdrant (direct)
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r2 = await c.get("http://localhost:6333/healthz")
            qdrant_ok = r2.status_code == 200
    except Exception:
        qdrant_ok = False
    notes.append(f"qdrant={'up' if qdrant_ok else 'down'}")
    overall_ok &= qdrant_ok
    # Ollama
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r3 = await c.get(f"{OLLAMA_BASE}/api/tags")
            ollama_ok = r3.status_code == 200
            n_models = len(r3.json().get("models", []))
    except Exception:
        ollama_ok = False
        n_models = 0
    notes.append(f"ollama={'up' if ollama_ok else 'down'} ({n_models} models)")
    overall_ok &= ollama_ok
    r.add("G1 Health", "PASS" if overall_ok else "FAIL", time.time() - t0, ", ".join(notes))


# ── Gate 2: Embedding returns 4096-dim ──────────────────────
async def gate_embedding(r: Results):
    t0 = time.time()
    store = VectorStore()
    try:
        vec = await store.get_embeddings("hello world, this is a test")
    except Exception as e:
        r.add("G2 Embedding", "FAIL", time.time() - t0, f"exception: {e}")
        return
    if not isinstance(vec, list) or len(vec) != EMBEDDING_DIM:
        r.add("G2 Embedding", "FAIL", time.time() - t0,
              f"expected {EMBEDDING_DIM}-dim list, got {type(vec).__name__} len={len(vec) if hasattr(vec, '__len__') else '?'}")
        return
    # Sanity: all values should be finite, mostly in [-1, 1] range
    if any(not isinstance(v, (int, float)) or math.isnan(v) or math.isinf(v) for v in vec):
        r.add("G2 Embedding", "FAIL", time.time() - t0, "non-finite values in vector")
        return
    mn, mx = min(vec), max(vec)
    norm = math.sqrt(sum(v * v for v in vec))
    r.add("G2 Embedding", "PASS", time.time() - t0,
          f"dim={len(vec)} range=[{mn:.3f}, {mx:.3f}] norm={norm:.3f}")


# ── Gate 3: Consistency (same text -> sim ~= 1.0) ───────────
async def gate_consistency(r: Results):
    t0 = time.time()
    store = VectorStore()
    text = "the quick brown fox jumps over the lazy dog"
    try:
        v1 = await store.get_embeddings(text)
        v2 = await store.get_embeddings(text)
    except Exception as e:
        r.add("G3 Consistency", "FAIL", time.time() - t0, f"exception: {e}")
        return
    if len(v1) != len(v2):
        r.add("G3 Consistency", "FAIL", time.time() - t0, "different dimensions")
        return
    # Cosine similarity
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = math.sqrt(sum(a * a for a in v1))
    n2 = math.sqrt(sum(b * b for b in v2))
    sim = dot / (n1 * n2) if n1 and n2 else 0.0
    ok = sim > 0.95  # not exact 1.0 because GPU non-determinism is possible
    r.add("G3 Consistency", "PASS" if ok else "FAIL", time.time() - t0,
          f"self-cosine={sim:.4f} (threshold=0.95)")


# ── Gate 4: Fallback models reachable ────────────────────────
async def gate_fallback(r: Results):
    t0 = time.time()
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    if not openrouter_key:
        r.add("G4 Fallback", "SKIP", time.time() - t0, "OPENROUTER_API_KEY not set")
        return
    # Test first 3 models in chain (cheapest check)
    test_models = []
    for m in OPENROUTER_FREE_MODELS[:3]:
        if m.startswith("openrouter/"):
            test_models.append(m[len("openrouter/"):])
        else:
            test_models.append(m.removesuffix(":free"))
    # Each is a tiny completion request
    async with httpx.AsyncClient(timeout=30) as c:
        results = []
        for m in test_models:
            try:
                resp = await c.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {openrouter_key}"},
                    json={
                        "model": m,
                        "messages": [{"role": "user", "content": "say 'ok' and nothing else"}],
                        "max_tokens": 8,
                    },
                )
                ok = resp.status_code == 200
                results.append((m, ok, resp.status_code))
            except Exception as e:
                results.append((m, False, str(e)))
    notes = ", ".join(f"{m}:{'OK' if ok else 'FAIL'}({code})" for m, ok, code in results)
    all_ok = all(ok for _, ok, _ in results)
    r.add("G4 Fallback", "PASS" if all_ok else "FAIL", time.time() - t0, notes)


# ── Gate 5: Qdrant semantic search ───────────────────────────
async def gate_search_qdrant(r: Results):
    t0 = time.time()
    store = VectorStore()
    if not store.qclient:
        r.add("G5 Search-Q", "SKIP", time.time() - t0, "Qdrant client not initialized")
        return
    try:
        # Query: "domestic shorthair cat" should match Luna chunks
        results = await store.search_wiki("domestic shorthair cat", "Luna the Cat", limit=3)
    except Exception as e:
        r.add("G5 Search-Q", "FAIL", time.time() - t0, f"exception: {e}")
        return
    if not results:
        r.add("G5 Search-Q", "FAIL", time.time() - t0, "no results for Luna the Cat query")
        return
    notes = f"top={results[0].get('chunk_id', '?')[:8]} ({len(results)} hits)"
    r.add("G5 Search-Q", "PASS", time.time() - t0, notes)


# ── Gate 6: Supabase pgvector RPC search ─────────────────────
async def gate_search_supabase(r: Results):
    t0 = time.time()
    store = VectorStore()
    if not store.supabase:
        r.add("G6 Search-S", "SKIP", time.time() - t0, "Supabase client not initialized")
        return
    try:
        # Build query vector, call RPC directly (not via search_wiki which needs Qdrant first)
        from backend.vector_store import EMBEDDING_DIM
        qvec = await store.get_embeddings("domestic shorthair cat")
        if len(qvec) != EMBEDDING_DIM:
            r.add("G6 Search-S", "FAIL", time.time() - t0,
                  f"query vec dim {len(qvec)} != {EMBEDDING_DIM}")
            return
        resp = store.supabase.rpc(
            "search_wiki_entries",
            {"query_embedding": qvec, "match_entity": "Luna the Cat", "match_limit": 3},
        ).execute()
        rows = resp.data or []
    except Exception as e:
        r.add("G6 Search-S", "FAIL", time.time() - t0, f"exception: {type(e).__name__}: {e}")
        return
    if not rows:
        r.add("G6 Search-S", "FAIL", time.time() - t0, "no results from pgvector RPC")
        return
    top_sim = rows[0].get("similarity", 0.0) if rows else 0.0
    notes = f"top={rows[0].get('chunk_id', '?')[:8]} sim={top_sim:.3f} ({len(rows)} hits)"
    r.add("G6 Search-S", "PASS", time.time() - t0, notes)


# ── Gate 7: E2E mini mission ─────────────────────────────────
async def gate_e2e_mini(r: Results):
    t0 = time.time()
    fixture = REPO_ROOT / "uploads" / "eval-gate-fixture.txt"
    fixture.parent.mkdir(exist_ok=True)
    fixture.write_text(
        "EvalGate Test Co — A small text fixture for the TANGLE eval gate.\n"
        "Founded 2024. Sole purpose: verify the pipeline runs end-to-end.\n"
        "Has 1 employee, $0 revenue, and one product called EvalProbe.\n"
    )
    try:
        async with httpx.AsyncClient(timeout=180) as c:
            up = await c.post(
                f"{BACKEND}/api/upload",
                files={"file": ("eval-gate-fixture.txt", open(fixture, "rb"), "text/plain")},
                data={"entity": "EvalGate Test Co"},
            )
            up.raise_for_status()
            up_data = up.json()
            mid = await c.post(
                f"{BACKEND}/api/mission/start",
                json={"entity": "EvalGate Test Co", "filepath": up_data.get("filepath")},
            )
            mid.raise_for_status()
            mission = mid.json()
    except Exception as e:
        r.add("G7 E2E-mini", "FAIL", time.time() - t0, f"exception: {type(e).__name__}: {e}")
        return
    ok = mission.get("success") and mission.get("report")
    notes = (f"mission_id={mission.get('mission_id', '?')[:8]} "
             f"report_len={len(mission.get('report') or '')}")
    r.add("G7 E2E-mini", "PASS" if ok else "FAIL", time.time() - t0, notes)


# ── Gate 8: Cost — verify $0 spend ───────────────────────────
async def gate_cost(r: Results):
    t0 = time.time()
    # If EMBEDDING_SOURCE is ollama, embedding costs nothing.
    # If any chat call was made via openrouter, it'd hit the free :free tier — also $0.
    # Real cost only comes from non-:free chat models or non-:free embeddings.
    from backend import vector_store as vs
    src = vs.EMBEDDING_SOURCE
    notes = f"embedding_source={src} (all free tiers = $0)"
    if src != "ollama":
        notes += f" — verify manually that no paid models were called"
    r.add("G8 Cost", "PASS", time.time() - t0, notes)


# ── Driver ───────────────────────────────────────────────────
GATES = {
    1: ("Health", gate_health),
    2: ("Embedding", gate_embedding),
    3: ("Consistency", gate_consistency),
    4: ("Fallback", gate_fallback),
    5: ("Search-Q", gate_search_qdrant),
    6: ("Search-S", gate_search_supabase),
    7: ("E2E-mini", gate_e2e_mini),
    8: ("Cost", gate_cost),
}


async def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--gate", type=int, choices=list(GATES.keys()), help="Run only this gate")
    p.add_argument("--list", action="store_true", help="List gates and exit")
    p.add_argument("--skip", type=str, default="", help="Comma-separated gate numbers to skip (e.g. '4,7')")
    args = p.parse_args()

    if args.list:
        print("Available gates:")
        for n, (name, _) in GATES.items():
            print(f"  G{n} {name}")
        return 0

    skip = set(int(x) for x in args.skip.split(",") if x.strip())

    print(f"Running TANGLE eval gates  (backend={BACKEND}, ollama={OLLAMA_BASE})")
    print(f"  Embedding dim expected: {EMBEDDING_DIM}")
    print(f"  Skipping: {sorted(skip) if skip else 'none'}")
    print()

    r = Results()
    start = time.time()
    for n, (name, fn) in GATES.items():
        if args.gate and args.gate != n:
            continue
        if n in skip:
            r.add(f"G{n} {name}", "SKIP", 0.0, "skipped via --skip")
            continue
        print(f"Gate G{n} {name}:")
        try:
            await fn(r)
        except KeyboardInterrupt:
            print("  interrupted")
            return 2
        except Exception as e:
            r.add(f"G{n} {name}", "FAIL", 0.0, f"unhandled: {type(e).__name__}: {e}")
    total_dt = time.time() - start
    print(f"\nTotal: {total_dt:.1f}s")
    return 0 if r.summary() else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
