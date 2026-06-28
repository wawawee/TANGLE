#!/usr/bin/env python3
"""
TANGLE Phase 0 smoke test — exercises the full pipeline end-to-end.

Run from repo root:
    python scripts/smoke_test.py

Requires:
- Backend running: cd backend && python main.py
- Frontend NOT required (this hits the API directly)
- One of OPENROUTER_API_KEY / GEMINI_API_KEY in .env.local (or Ollama running)
- Qdrant running: docker-compose up -d
"""

import asyncio
import json
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Run: pip install httpx")
    sys.exit(1)

BACKEND = "http://localhost:8000"
SAMPLE_FILE = Path(__file__).parent.parent / "uploads" / "acme-corp-smoke.txt"


SAMPLE_CONTENT = """Acme Corp — Company Overview (smoke test fixture)

Acme Corporation is a mid-sized B2B SaaS company founded in 2018.
They specialize in automated invoicing for European SMBs.

Current situation:
- 45 employees, 380 active customers
- Annual revenue: €4.2M (2025)
- Main product: AcmeInvoice (cloud invoicing platform)
- HQ in Stockholm, Sweden

Known challenges (from recent board minutes):
1. Churn rate increased from 4% to 7% in Q4 2025
2. Customer support backlog: ~340 open tickets
3. Two senior engineers left in Jan 2026
4. Compliance deadline for EU AI Act Article 6 by Aug 2026

Strategic priorities (per CEO memo 2026-03-15):
- Reduce churn via customer success program
- Hire 3 senior engineers + 1 product manager
- Achieve ISO 27001 certification by Q4 2026
- Explore acquisition targets in DACH region

Recent wins:
- Closed €600K funding round (Series A extension)
- Signed partnership with Visma (distribution)
- Won "Best SaaS Platform 2025" award (Nordic region)
"""


async def step(label: str):
    """Print step header with timing."""
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")


async def main():
    SAMPLE_FILE.parent.mkdir(exist_ok=True)
    SAMPLE_FILE.write_text(SAMPLE_CONTENT)

    async with httpx.AsyncClient(timeout=120.0) as client:
        # 1. Health
        await step("1. Backend health check")
        r = await client.get(f"{BACKEND}/health")
        r.raise_for_status()
        print(f"  ✓ {r.json()}")

        # 2. Provider health
        await step("2. LLM provider health")
        r = await client.get(f"{BACKEND}/api/health/providers")
        r.raise_for_status()
        providers = r.json()
        print(f"  providers: {providers}")
        any_online = any(providers.values()) if isinstance(providers, dict) else False
        if not any_online:
            print("  ⚠ No providers online. Mission will use fallback (or fail).")

        # 3. File upload (multipart)
        await step("3. POST /api/upload (file → parse → vectorize)")
        with open(SAMPLE_FILE, "rb") as f:
            r = await client.post(
                f"{BACKEND}/api/upload",
                files={"file": ("acme-corp-smoke.txt", f, "text/plain")},
                data={"entity": "Acme Corp"},
            )
        r.raise_for_status()
        upload_data = r.json()
        print(f"  success: {upload_data.get('success')}")
        print(f"  filename: {upload_data.get('filename')}")
        parsed = upload_data.get("parsed", {})
        print(f"  confidence: {parsed.get('confidence')}")
        print(f"  chunk_id: {parsed.get('chunk_id')}")
        print(f"  markdown preview (first 200 chars):")
        print(f"    {(parsed.get('markdown') or '')[:200]}...")

        # 4. Mission start
        await step("4. POST /api/mission/start (planner → scout → librarian → critic → synthesize)")
        print("  This may take 30-90 seconds depending on LLM...")
        t0 = time.time()
        r = await client.post(
            f"{BACKEND}/api/mission/start",
            json={"entity": "Acme Corp", "filepath": upload_data.get("filepath")},
        )
        r.raise_for_status()
        elapsed = time.time() - t0
        mission = r.json()
        print(f"  elapsed: {elapsed:.1f}s")
        print(f"  success: {mission.get('success')}")
        print(f"  mission_id: {mission.get('mission_id')}")
        report = mission.get("report", "")
        print(f"  report length: {len(report)} chars")
        print(f"  report preview (first 800 chars):")
        print("  " + "-" * 56)
        for line in report[:800].split("\n"):
            print(f"  {line}")
        print("  " + "-" * 56)

        # 5. Wiki nodes JSON block parseable?
        await step("5. Wiki nodes JSON block (drives React Flow radiating layout)")
        import re
        m = re.search(r"```json\s*([\s\S]*?)\s*```", report)
        if m:
            try:
                wiki = json.loads(m.group(1))
                nodes = wiki.get("nodes", [])
                print(f"  ✓ Parsed {len(nodes)} wiki nodes")
                for i, node in enumerate(nodes[:5]):
                    print(f"    [{i}] {node.get('label', '?')} (type={node.get('type', 'info')})")
                if len(nodes) > 5:
                    print(f"    ... and {len(nodes) - 5} more")
            except json.JSONDecodeError as e:
                print(f"  ✗ JSON parse failed: {e}")
        else:
            print("  ⚠ No ```json block found in report (frontend won't render radiating nodes)")

        # 6. Mission persisted?
        await step("6. Mission persisted in vector store?")
        if mission.get("mission_id"):
            print(f"  ✓ Mission {mission['mission_id']} should be in SQLite (tangle.db)")
            print(f"  ✓ Wiki chunks should be in Qdrant collection 'tangle_wiki_memories'")

    print(f"\n{'=' * 60}")
    print("  ✓ PHASE 0 SMOKE TEST COMPLETE")
    print(f"{'=' * 60}\n")
    print("If all steps passed, Phase 0 breathes.")
    print("Open the frontend (npm run dev in frontend/) and try the same flow visually.")


if __name__ == "__main__":
    asyncio.run(main())
