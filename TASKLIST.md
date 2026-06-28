---
# TANGLE Tasklist — shared source of truth for humans + agents
# Format: markdown with checkboxes. Other harnesses can parse this directly.
# Update freely: add an idea, move a checkbox, drop a "human sloth brain" note.
# Status icons: 🚧 in progress · 📋 queued · ✅ done · 💡 idea · ⚠️ blocker · 🧠 human note
project: tangle
version: 1.0.0
last_updated: 2026-06-27
sync_targets:
  - mavis_plans
  - human_review
  - kanban_store
---

# TANGLE — TASKLIST

> **Phase 0: The Skeleton** · Pipeline runs end-to-end. Currently verifying with smoke test.
>
> **Mantra:** *The world is tangled. Information is tangled. Problems are tangled. We exist to untangle.*

---

## 🚧 IN PROGRESS

- [ ] **Phase 0 live verification** — user runs `python scripts/smoke_test.py` against a fresh venv; report any failures back here · owner: human · started: 2026-06-27
- [ ] **Commit current state** — ~55 changed files (archive + rename + version bumps + new docs + smoke test) ready for one or two atomic commits · owner: mavis · blocked-on: user go-ahead

---

## 📋 QUEUED — Phase 0.1 (small polish before Phase 1)

- [ ] **Real markdown rendering in report panel** — current side-panel just shows `whiteSpace: 'pre-wrap'`. Add `react-markdown` + `remark-gfm` for proper headers/lists/code blocks.
- [ ] **Auto-tagging in wiki spec** — current `#untagged` placeholder. Use cheap LLM call to generate `#health #finance #legal #contact #risk` based on content.
- [ ] **Retry logic on orchestrator failures** — if `evaluate` gate fails, current code does one retry. Make it N retries with backoff (1s, 2s, 4s).
- [ ] **Replace DuckDuckGo with Jina AI or SerpAPI** — current HTML scrape is fragile + fallback hallucinates. Jina (r.jina.ai) is free + no key. SerpAPI has 100 free calls/day.
- [ ] **Image Analyst agent role** — wire `AGENT_DEFS["image_analyst"]` so image-only missions are first-class.
- [ ] **WebSocket localStorage persistence** — telemetry events lost on page refresh. Persist to localStorage and replay on reconnect, or rehydrate from SQLite.
- [x] **`.env.example`** — done (sub-agent created `/Users/perbrinell/Documents/DROPHELP/.env.example`)
- [ ] **Error boundaries in React** — current app would white-screen on any throw. Add ErrorBoundary around major panels.
- [ ] **Loading states polish** — spinner exists, but make it more informative (which step of the mission is running).
- [ ] **UI: render `[UNVERIFIED]` badge** when `mission.verified == false`. Currently backend returns the flag but frontend ignores it.
- [x] **Synthesizer output: emit BOTH report_markdown AND wiki_entry_markdown** — done (June 2026). `synthesize()` returns dict with both fields. Single LLM call uses `===TANGLE_REPORT_START===` / `===TANGLE_WIKI_START===` delimiters; Python splits + wraps wiki body with deterministic metadata (chunk_id, timestamp, confidence). Orchestrator re-ingests `wiki_entry_markdown` into the vector store (self-feeding knowledge base). Mission response exposes `report_markdown`, `wiki_entry_markdown`, `wiki_entry_chunk_id`.
- [x] **Per-mission cost tracking** — done (June 2026). `FreeGateway._mission_usage` accumulates tokens + cost per mission_id. Exposed via `/api/missions/{id}/cost` and `/api/health/usage`.
- [x] **Never silent safe-pass** — done (June 2026). Critic errors return `verified: false` with explicit `VERIFICATION FAILED` critique.
- [x] **pytest for parsing_engine** — done (sub-agent wrote `backend/tests/test_parsing_engine.py`, 13 tests, all pass)

### 🐛 Bugs found by sub-agent audit (in `parsing_engine.py`)

| # | Severity | Issue | Status |
|---|---|---|---|
| 1 | Medium | `datetime.utcnow()` is deprecated in Py 3.12+ | ✅ fixed (`datetime.now(timezone.utc)`) |
| 2 | Medium | Inconsistent fallback confidence (0.5 vs 0.4 depending on whether markitdown is installed) | ✅ fixed (unified to 0.5) |
| 3 | High | `_fallback_parse` silently extracts garbage text from binary files via `errors="ignore"` | 📋 queued (kept for Phase 0.1 — would require chardet/magic-bytes dependency) |
| 4 | Low | `confidence` not rounded in dict | ✅ fixed (`round(confidence, 2)` in return dict) |
| 5 | Low | Tags always `#untagged` — already tracked in "Auto-tagging" item above | ✅ duplicate |
| 6 | Low | `MARKITDOWN_AVAILABLE` + `self.mid` computed at `__init__` time | 📋 queued (low-impact, doc-only) |
| 7 | Medium | No `"error"` key in return dict when parse fails | ✅ fixed (`parse_error` field added) |

### 🔧 Other findings from sub-agent audit

- ⚠️ **`langgraph_engine.py` had a broken import** (referenced `TOOLS` and `TOOL_SYSTEM` from `agent_orchestrator` — they didn't exist) → ✅ fixed by inlining both as module-level constants in langgraph_engine.py
- ⚠️ **Ollama host hardcoded to `http://localhost:11434` in `free_gateway.py:9`** — not env-driven despite AGENTS.md mentioning it. Documented in `.env.example` but consider making `OLLAMA_HOST` a real env var.

### 🧪 External review findings (Kimi, June 2026)

Strategic-doc review surfaced 8 corrections. Most accepted; one (Next.js 16) verified against npm registry as actually current. Status:

- ✅ **Safe pass removed** — critic errors now return `verified: false` + `[UNVERIFIED]` flag
- ✅ **Per-mission cost tracking** — done via `FreeGateway._mission_usage` + `/api/missions/{id}/cost`
- ✅ **SHA256 fallback documented as zero-semantic-search** — added warning note in section 4
- ✅ **Section 5 image-without-gateway message clarified** — `[AI Gateway not configured — image not analyzed]`
- ✅ **Mermaid sequence diagram now shows token-burn note** — `Note over O,OR: Tokens burned here`
- ✅ **Roadmap expanded with Supabase migration, Image Analyst, deferred agents**
- ✅ **Deferred agents section added** — Image Analyst, Agent Zero, OSINT Integrator, Open Source Integrator, browser-in-flow
- ✅ **Synthesizer dual output (report_markdown + wiki_entry_markdown)** — implemented (June 2026). One LLM call, two delimited blocks. Wiki entry is re-ingested into vector store.
- 📋 **WebSocket localStorage persistence** — documented, queued for Phase 0.1

---

## 🏗️ PHASE 1 CANDIDATES (deliberate, not by accident)

Each is a 2-4 hour architectural lift. Pick consciously.

- [ ] **Next.js 16.2.9 migration** — replace Vite with Next 16 App Router. Gives SSR, file-based routing, API routes for internal endpoints. Trade-off: rebuilds config, adds `'use client'` directives everywhere.
- [ ] **Tailwind CSS 4** — replace raw inline `style={}` props. Requires rewriting every component. Big visual style unification upside.
- [ ] **Supabase integration** — replace SQLite with Supabase Postgres. Enables real auth + multi-user + realtime.
- [ ] **Redis + Celery task queue** — for long-running missions, currently synchronous and blocking.
- [ ] **Multi-entity support** — current code assumes one entity at a time. Schema supports it, UI doesn't.
- [ ] **Web search deduplication** — scout currently returns first 5 snippets raw. Should dedupe + rank by relevance.
- [ ] **Vision pipeline cost controls** — dual-pass image parsing can be expensive. Add per-mission cap.

---

## 💡 IDEAS (brain-dump zone — anything goes)

> Drop loose ideas here. Even half-baked. Move to "Queued" when you decide to act on one.

- 💡 **Quick-recall sidebar** — last 5 entities you helped, click to re-run mission with new file
- 💡 **Entity type detection** — auto-categorize entity (person/cat/company/group) based on name + file content, drive icon in EntityNode
- 💡 **Voice input for entity name** — "Hey Tangle, help my cat Luna" — uses Web Speech API
- 💡 **Export report as PDF** — currently markdown only. pdfkit or react-pdf on backend.
- 💡 **Diff mode** — re-run mission on same entity, show what changed in recommendations
- 💡 **Confidence slider** — user can set min confidence threshold for what to include in report
- 💡 **Local-first mode** — entirely offline using Ollama only, no API keys needed
- 💡 **Mission replay** — re-watch a previous mission's telemetry event-by-event like a debugger
- 💡 **Multi-file drop** — currently one file at a time. Drag a folder, ingest all.
- 💡 **Auto-update TASKLIST from completed runs** — when a mission completes, mark items done via API

---

## 🧠 HUMAN NOTES (sloth brain drop-zone)

> Anything you want to remember, half-formed ideas, links to inspiration, names of people to credit, etc. Don't worry about formatting.

<!--
Examples:
- [2026-06-27] Saw a similar pattern in VR-SuperPowers — could share telemetry layer
- [date] TODO check what 'Anlagstavlan' was supposed to mean (Swedish?)
- [date] Note: user prefers warm brown UI not neon — applies to landing pages too
-->

---

## ✅ RECENTLY DONE

- ✅ Project renamed: sami/Aegis/ANLAGSTAVLAN → **TANGLE** (29 places: loggers, paths, UI, docstrings)
- ✅ All deps upgraded to latest (frontend 14 packages, backend 16 packages)
- ✅ Frontend build: tsc 6.0.3 + vite 8.1.0 + react 19.2.7 → 437 KB JS, 0 vulns
- ✅ Tags section added to wiki markdown spec (in `parsing_engine.py`)
- ✅ Foundation docs: `README.md` + `AGENTS.md` (TANGLE-flavored, with Phase 1 candidates section)
- ✅ Archive of legacy: `.review-harness/`, `.archon/`, `.claude/`, `twisted-stacks-agentic-team/`, `backend/venv/`, etc. moved to `archive/`
- ✅ `scripts/smoke_test.py` — full pipeline exercise (file → mission → report → wiki nodes)
- ✅ Pre-existing TS errors fixed (added store fields, removed unused imports) so build is clean
- ✅ `.env.example` at repo root documenting all env vars
- ✅ `backend/tests/test_parsing_engine.py` — 13 pytest tests, all pass on Py 3.14
- ✅ `langgraph_engine.py` broken import fixed (was referencing non-existent `TOOLS`/`TOOL_SYSTEM`)
- ✅ 4 of 7 parsing_engine bug fixes applied (datetime, confidence consistency, float rounding, parse_error key)
- ✅ `docs/AGENT_COMMUNICATION.md` — strategic plan: agent landscape, message protocols, flow patterns, state mgmt, cost discipline, failure modes, Mermaid diagrams, roadmap
- ✅ **Synthesizer dual output (report_markdown + wiki_entry_markdown)** — single LLM call with explicit delimiters, deterministic metadata injection, re-ingestion into vector store for self-feeding knowledge base

---

## 🔌 EXTERNAL TOOL INTEGRATIONS (toggleable modules, not replacements)

Per Per's architecture rule (June 2026): **new tools integrate as toggleable background modules, not replacements** for existing ones. Each module runs in the background; visualization goes through existing React Flow (new node types only when needed). Nothing here ships until prioritized.

### Priority-ordered candidates

| Tool | Repo | What it does | TANGLE value | Integration | Phase |
|---|---|---|---|---|---|
| **headroom** | `chopratejas/headroom` | Context compression layer (60-95% token reduction) | Wraps `free_gateway.chat()` — every LLM call gets cheaper without changing call sites | Library mode (`from headroom import compress`) inserted into gateway. Toggle via env `TANGLE_HEADROOM_ENABLED=1`. Optional "compression-stats" node type in React Flow to visualize savings. | **0.1** — fits "kostnad är en feature" mantra directly |
| **last30days-skill** | `mvanhorn/last30days-skill` | Cross-platform trending research, 14 platforms last 30 days | Replaces broken DuckDuckGo scout (already flagged in Phase 0.1 queue) | Runs in background during scout step. Toggle `TANGLE_SCOUT_SOURCE=jina\|last30days\|duckduckgo`. Falls back through chain. | **0.1** — solves an open bug |
| **promptfoo** | `promptfoo/promptfoo` | LLM eval/red-team framework, test cases, regression catching | Upgrades our `review_harness.py` from 3 personas to declarative test cases. Catches orchestrator prompt regressions. | CLI tool, runs on demand (`promptfoo eval`). Writes results to `backend/eval_results/`. Toggle via CI step. | **0.2** — depends on having more prompts worth testing |
| **OpenViking** | `volcengine/OpenViking` | Context database w/ filesystem paradigm (`viking://`), L0/L1/L2 hierarchical loading | Augments `vector_store.py` with structured memory + self-iterating memory loop | Toggleable backend for `vector_store`. `TANGLE_MEMORY=qdrant\|openviking\|sqlite_fallback`. New "memory-layer" node type in React Flow to visualize L0/L1/L2. | **1.0** — needs multi-entity workloads to justify |
| **open-notebook** | `lfnovo/open-notebook` | Privacy-focused NotebookLM clone (Streamlit + SurrealDB + LangChain) | Optional ingestion alternative for users who want a richer notebook UI on top of TANGLE's wiki | Standalone service we can optionally point to. We **don't replace `parsing_engine.py`** — users get both. Optional integration via webhook. | **1.0+** — competes with our UI; deferred until we know if anyone wants both |
| **Heretic** | `p-e-w/heretic` | Removes safety alignment from open-weight LLMs without expensive post-training | **Legit use case:** TANGLE helps entities in rail-sensitive domains — true-crime book authoring, security research, trauma-informed therapy, legal cases, adult content creation. Default commercial rails get in the way of these legitimate uses. | Toggleable model modifier. `TANGLE_LLM_MODE=safe\|uncensored`. Default stays safe (commercial APIs with rails); opt-in flips to a Heretic-modified local model for missions where user explicitly marks the entity as rail-sensitive. Per-mission toggle, never global default. | **1.0** — needs careful UX (clear consent) and a local model deployment story |

### Architecture rules for new integrations

1. **Background-first.** New tools run as background workers (asyncio tasks, separate threads). No new UI per tool — if data is interesting, expose it as a new React Flow node type via `App.tsx NODE_TYPES` map.
2. **Toggleable, never replace.** Each module is feature-flagged via env var or config file. Existing tools stay until the new one proves clearly superior across the board.
3. **Discard if worthless.** If a module adds complexity without solving a real problem TANGLE has, remove it. Don't accumulate dead weight.
4. **Document here before implementing.** Add to this table with phase tag. Implementation only when phase is reached.

### Open questions for Per

- ❓ Should `headroom` integration also surface compression stats in the React Flow canvas (a "compression-stats" node type)?
- ❓ Should `last30days` be primary scout or kept as fallback (next to Jina/SerpAPI)?
- ❓ Order of phases above — happy with headroom → last30days → promptfoo → Heretic → OpenViking → open-notebook, or want different sequence?
