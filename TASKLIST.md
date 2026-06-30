---
# TANGLE Tasklist — shared source of truth for humans + agents
# Format: markdown with checkboxes. Other harnesses can parse this directly.
# Update freely: add an idea, move a checkbox, drop a "human sloth brain" note.
# Status icons: 🚧 in progress · 📋 queued · ✅ done · 💡 idea · ⚠️ blocker · 🧠 human note
project: tangle
version: 1.0.0
last_updated: 2026-06-29
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
- [ ] **Brutalist UI port from `finasteos/twisted/TWISTED-FRONTEND-NEW`** (started 2026-06-29) — Per confirmed UI on :3000 is "snyggaste UI jag sett någonsin". Replace TANGLE frontend (`src/App.tsx` + nodes + panels) with ported twisted-ref. Keep TANGLE backend (multi-provider routing, Qdrant, Supabase, parsing). Approach: copy `TWISTED-FRONTEND-NEW/{src,index.html,package.json,vite.config.ts,tsconfig.json}` → `TANGLE/frontend/`, drop `server.ts` (TANGLE Python backend replaces it), add Vite proxy `/api/*` → `:8000` and `/ws/*` → `:8000/ws/*`, map endpoints (WhoNode → /api/mission/start, DropNode → /api/upload, agent status via WS), replace twisted's 5 agent IDs with TANGLE's pipeline (planner/scout/librarian/critic/synthesizer). Accessibility-first by accident — works for Agda 86 + tech-savvy teenagers. Fix during port: remove chat bubble OR zoom buttons (currently overlap). Drop agent-config-editor for v1 (Phase 1+ candidate). ~4-6h focused work.

---

## 📋 QUEUED — Phase 0.1 (small polish before Phase 1)

- [ ] **Real markdown rendering in report panel** — current side-panel just shows `whiteSpace: 'pre-wrap'`. Add `react-markdown` + `remark-gfm` for proper headers/lists/code blocks.
- [ ] **Auto-tagging in wiki spec** — current `#untagged` placeholder. Use cheap LLM call to generate `#health #finance #legal #contact #risk` based on content.
- [ ] **Retry logic on orchestrator failures** — if `evaluate` gate fails, current code does one retry. Make it N retries with backoff (1s, 2s, 4s).
- [x] **Replace DuckDuckGo with Jina AI** — done (2026-06-28). `search()` in agent_orchestrator.py now uses Jina AI Reader (`s.jina.ai`) as primary search. Free tier (20 req/min without API key, 500 req/min with `JINA_API_KEY`). Returns clean Markdown instead of scraped HTML snippets. Fallback LLM search no longer hallucinates — now honestly reports "Web search unavailable" when uncertain.
   - [x] **Per-agent free-model routing** — added `AGENT_MODELS` tiered mapping in `agent_orchestrator.py`. Planner/synthesizer → Qwen3-Coder, Scout → Llama-3.3-70B, Librarian → GPT-OSS-120B, Critic → Hermes-3-405B, Image → Nemotron-VL. Single source of truth, gateway still handles retries.
   - [ ] **Role-aware model selection** — planner/synthesizer lean toward structured-output coders, critic toward instruction-followers, scout/librarian toward generalists, image_analyst toward vision. Each role has an ordered fallback chain.
- [ ] **WebSocket localStorage persistence** — telemetry events lost on page refresh. Persist to localStorage and replay on reconnect, or rehydrate from SQLite.
- [x] **`.env.example`** — done (sub-agent created `/Users/perbrinell/Documents/DROPHELP/.env.example`)
- [ ] **Error boundaries in React** — current app would white-screen on any throw. Add ErrorBoundary around major panels.
- [ ] **Loading states polish** — spinner exists, but make it more informative (which step of the mission is running).
- [ ] **UI: render `[UNVERIFIED]` badge** when `mission.verified == false`. Currently backend returns the flag but frontend ignores it.
- [x] **Synthesizer output: emit BOTH report_markdown AND wiki_entry_markdown** — done (June 2026). `synthesize()` returns dict with both fields. Single LLM call uses `===TANGLE_REPORT_START===` / `===TANGLE_WIKI_START===` delimiters; Python splits + wraps wiki body with deterministic metadata (chunk_id, timestamp, confidence). Orchestrator re-ingests `wiki_entry_markdown` into the vector store (self-feeding knowledge base). Mission response exposes `report_markdown`, `wiki_entry_markdown`, `wiki_entry_chunk_id`.
- [x] **Per-mission cost tracking** — done (June 2026). `FreeGateway._mission_usage` accumulates tokens + cost per mission_id. Exposed via `/api/missions/{id}/cost` and `/api/health/usage`.
- [x] **Never silent safe-pass** — done (June 2026). Critic errors return `verified: false` with explicit `VERIFICATION FAILED` critique.
- [x] **pytest for parsing_engine** — done (sub-agent wrote `backend/tests/test_parsing_engine.py`, 13 tests, all pass)
- [x] **Memory index endpoint + Obsidian wiki vault** — done (2026-06-28). `GET /api/admin/index` returns live snapshot of SQLite (counts, per-entity breakdown, oldest/newest entries), Qdrant (reachable, collection exists, points), Supabase (status, Phase 1+ note if not connected), filesystem wiki vault + uploads. `POST /api/admin/export-wiki` rebuilds the Obsidian-compatible vault at `docs/wiki/` with YAML frontmatter, [[wikilinks]], per-entity indexes, master INDEX/TAGS/_meta. Auto-fires on mission completion (toggle via `TANGLE_WIKI_EXPORT_ON_MISSION=0`). New frontend `IndexPanel.tsx` shows all of this as a toggleable side panel; new `INDEX` button next to `CLI`/`LOGS`. `backend/wiki_vault.py` + 26 pytest tests in `tests/test_wiki_vault.py`, all green.
- [x] **Fix pre-existing TypeScript build errors** — done (2026-06-28). Removed unused `EVENT_ICONS` from AgentVerbosePanel.tsx, unused `sc` destructured from AgentNode.tsx, added missing `let ws: WebSocket | null = null;` declaration in agentStore.ts and typed the `ev: MessageEvent` parameter. Frontend now builds clean (`tsc -b && vite build` → 1.5MB JS, 17KB CSS, 0 errors).
- [x] **Fix pre-existing backend bug: missing `datetime` import in vector_store.py** — done (2026-06-28). `save_mission()` used `datetime.utcnow()` without importing it. Would have crashed any mission save. Migrated to `datetime.now(timezone.utc).isoformat()` (deprecated `utcnow` replaced).
- [x] **Fix UI: ANLAGSTAVLAN header → TANGLE** — done (2026-06-28). Brand text in App.tsx header was the legacy Swedish name. TASKLIST rename was complete but the UI lagged. Subtitle updated from "Tactical Strategy Engine" to "Untangle the world".
- [x] **Auto-tagging in wiki spec** — done (2026-06-28). Replaced `#untagged` placeholder with cheap-LLM-generated 3-5 #tags per chunk. New `_generate_tags()` in `parsing_engine.py` uses nemotron-nano vision model (same cost-discipline as vision pipeline). Content capped at 2000 chars (start+end preserved via smart truncation). Falls back to `['untagged']` on any failure (no gateway, LLM error, malformed output, empty content). Result exposed in `parse_file()['tags']` AND in the markdown body's `### Tags` section so the wiki vault frontmatter picks them up automatically. Synthesizer wiki entries extract tags from the LLM output (via `_extract_tags_from_body`) instead of hardcoded `#synthesized`. New `_extract_inline_tags` static method shared between parsing_engine and orchestrator. 18 new tests in `tests/test_parsing_engine.py` (extraction + happy path + fallback + truncation), all green. Total: 66 tests pass.
- [x] **Fix P0 regression in /api/mission/start** — done (2026-06-28). Caught by test-runner subagent. The endpoint was whitelisting only 5 fields (`mission_id`, `entity_name`, `report`, `wiki_entry`, `success`) and dropping everything else (`report_markdown`, `wiki_entry_markdown`, `wiki_entry_chunk_id`, `verified`, `critic_score`, `critic_critique`, `usage`, `wiki_export`). Refactored to forward-keys pattern: explicit set of allowed keys, future orchestrator additions reach the frontend without endpoint edits. Backwards-compat aliases (`entity_name` → `entity`, `report` → kept) preserved.
- [x] **Code-review fixes from coder subagent (P1 #1-3, P2 #4-6)** — done (2026-06-28). Stale-dir cleanup added to `export_all()` — any entity dir on disk with no matching SQLite entry is removed; any chunk file under a surviving entity dir with no matching short-id is removed. `count()['last_modified']` returns `None` for empty vault (was `0`, indistinguishable from epoch zero). Public `preview_export()` method extracted (endpoint no longer reaches into private `_read_all_entries`). Removed dead `_wikilink_target` helper. Trimmed misleading `_resolve_source_file_links` docstring. Moved `sqlite3`/`httpx` imports to top of main.py. 5 new tests covering stale-cleanup paths.
- [x] **Frontend-review fixes from general subagent** — done (2026-06-28). All P1 findings applied by parallel session: ANLAGSTAVLAN rename sweep (ChatBox.tsx, Experience3D.tsx), AbortController plumbing through IndexPanel fetches, Supabase card uses `data.supabase.configured` instead of hardcoded `ok={false}`, hardcoded cyan `#06b6d4` replaced with `var(--cyan)` (color-mix for tints), status dots use `var(--emerald)` / `var(--red)`, error state moved into main render so auto-refresh recovers on transient failures.

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
- 💡 **Admin Mode overlay** (ported from `finasteos/twisted` admin panel, 2026-06-29) — HSL color sliders for live UI tweaking + markdown editor for agent system prompts + temperature per agent. Take only what adds value: SKIP vector memory panel (IndexPanel covers it), SKIP SwiftUI code (we're React), KEEP HSL sliders + agent prompt editor. Build when UI is "börjar nöjda" — Per's strategic view is React-first for design iteration, native (Swift/MacOS/iOS) port later once UI is frozen. ~3h lift.
- 💡 **Brutalist design accents** (ported from `finasteos/twisted/TWISTED-FRONTEND-NEW` vite app, 2026-06-29) — hard `border-4` + offset `shadow-[8px_8px_0px]` skuggor + monospace. Per's "happy with the UI"-stil från förra projektet. Fuska in selektivt på admin mode + settings + knappar, INTE globalt. Krockar med dagens glassmorphism-tone så kräver varsamhet. ~2h för POC på en knapp.
- 💡 **Token Usage panel** (ported from same vite app) — visar prompt/completion/total tokens per agent + swarm total, live via WebSocket. TANGLE saknar detta. Passar "kostnad är en feature" perfekt. ~1-2h.
- 💡 **Admin Mode hotkey toggle** (ported from same) — hovra settings-ikonen + tryck `T` → togglar admin. ~30min.

---

## 🧠 HUMAN NOTES (sloth brain drop-zone)

> Anything you want to remember, half-formed ideas, links to inspiration, names of people to credit, etc. Don't worry about formatting.

<!--
Examples:
- [2026-06-27] Saw a similar pattern in VR-SuperPowers — could share telemetry layer
- [date] TODO check what 'Anlagstavlan' was supposed to mean (Swedish?)
- [date] Note: user prefers warm brown UI not neon — applies to landing pages too
-->

- [2026-06-29] **Cross-project vault leak lesson.** When TANGLE ingests source files from another project (e.g. SKATTEREVISION-REBOOT docs), the generated wiki entries do NOT belong in DROPHELP's vault — they belong in that project's vault. The 2026-06-29 R3 incident shows that even with `.tangle/vault/` gitignored, accidental ingestion still pollutes this DB+vector store. Future fix: route mission output by `source_file_root` — if a mission's uploads come from outside DROPHELP, the wiki_entry goes to whichever project's vault the source root lives in. Until that lands, **no TANGLE mission should ingest files from `/Users/perbrinell/a0/usr/projects/<other_project>/`** without explicit per-mission opt-in.
- [2026-06-29] README + AGENTS.md still reference the old `docs/wiki/` path. Update in same PR if wiki path migration gets touched again.
- [2026-06-29] Obsidian compatibility: previously the vault lived at `docs/wiki/`; Per may have Obsidian pointing there. If he wants live-sync after this migration, either symlink `.tangle/vault/` to the Obsidian vault path or set `TANGLE_VAULT_ROOT` to the Obsidian-include path.

---

## ✅ RECENTLY DONE

- ✅ **Wiki vault → `.tangle/vault/` migration** — 2026-06-29. Vault export was writing to `docs/wiki/` inside the repo, which created a cross-project data-leak path (R3 / SKATTEREVISION-REBOOT entity got committed in 7e40755 before anyone noticed). New default lives outside git (`TANGLE_VAULT_ROOT` env override supported for Obsidian live-sync). Committed: `a168847`.
- ✅ **R3 leak incident handled** — 2026-06-29. Three SKATTEREVISION-REBOOT entities (brev-till-skatteverket..., skatterevision, skatterevision-system) caught in commit `7e40755`, reverted in `1ee1ce7`, files moved to `SKATTEREVISION-REBOOT/_inbox_from_tangle_2026-06-29/wiki-entities/` for Per to triage. Branch never pushed — leak averted. Lesson: any time TANGLE ingests from another project, the wiki output belongs in THAT project's vault, not DROPHELP's. See Human Notes below.
- ✅ **`.gitignore` reset** — 2026-06-29. Six untracked legacy dirs (`.archon/`, `.claude/`, `.review-harness/`, `twisted-stacks-agentic-team/`, `uploads/`, `.sami-agent-prompt.md`) now properly excluded. Committed: `c2f17fa`.
- ✅ **Phase 0.1 batch commits** — 2026-06-29. Three commits staged: `a329d11` vault cleanup of stale smoke-test entities, `1ee1ce7` DEEP_EVALUATION + Phase 0.1 fixtures, `a168847` wiki vault path migration. Branch is 4 commits ahead of origin/master (not pushed).
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
| **headroom** | `chopratejas/headroom` | Context compression layer (60-95% token reduction) | Wraps `free_gateway.chat()` — every LLM call gets cheaper without changing call sites | Library mode inserted into gateway. Toggle via env `TANGLE_HEADROOM_ENABLED=1`. | **0.1** — fits "kostnad är en feature" mantra directly |
| **last30days-skill** | `mvanhorn/last30days-skill` | Cross-platform trending research, 14 platforms last 30 days | Replaces broken DuckDuckGo scout (already flagged in Phase 0.1 queue) | Runs in background during scout step. Toggle `TANGLE_SCOUT_SOURCE=jina\|last30days\|duckduckgo`. Falls back through chain. | **0.1** — solves an open bug |
| **promptfoo** | `promptfoo/promptfoo` | LLM eval/red-team framework, test cases, regression catching | Upgrades our `review_harness.py` from 3 personas to declarative test cases. Catches orchestrator prompt regressions. | CLI tool, runs on demand (`promptfoo eval`). Writes results to `backend/eval_results/`. Toggle via CI step. | **0.2** — depends on having more prompts worth testing |
| **OpenViking** | `volcengine/OpenViking` | Context database w/ filesystem paradigm (`viking://`), L0/L1/L2 hierarchical loading | Augments `vector_store.py` with structured memory + self-iterating memory loop | Toggleable backend for `vector_store`. `TANGLE_MEMORY=qdrant\|openviking\|sqlite_fallback`. New "memory-layer" node type in React Flow to visualize L0/L1/L2. | **1.0** — needs multi-entity workloads to justify |
| **chonkie** | `chonkie/chonkie` | Smart text chunking for RAG (token/sentence/recursive/semantic/late) | Could replace our naive chunking in `parsing_engine.py` with semantically-aware splits. | Toggleable chunking backend. `TANGLE_CHUNKER=chonkie|native`. | **0.1** — good fit, but 129MB model download on first run is heavy for Phase 0; evaluate in Phase 1 |
| **Heretic** | `p-e-w/heretic` | Removes safety alignment from open-weight LLMs without expensive post-training | **Legit use case:** TANGLE helps entities in rail-sensitive domains — true-crime book authoring, security research, trauma-informed therapy, legal cases, adult content creation. Default commercial rails get in the way of these legitimate uses. | Toggleable model modifier. `TANGLE_LLM_MODE=safe\|uncensored`. Default stays safe (commercial APIs with rails); opt-in flips to a Heretic-modified local model for missions where user explicitly marks the entity as rail-sensitive. Per-mission toggle, never global default. | **1.0** — needs careful UX (clear consent) and a local model deployment story |

### Ins Hetvalda Open-Source-Modeller som TANGLE nu använder (via OpenRouter :free)

Per senaste OpenRouter-modellgenomgång (2026-06-29):

- **Planner/Synthesizer**: `qwen/qwen3-coder:free` (1M ctx, Apache 2.0) — bäst för struktur och kod-output.
- **Scout**: `meta-llama/llama-3.3-70b-instruct:free` (131K ctx) — stabil allrounder, default tidigare.
- **Librarian**: `openai/gpt-oss-120b:free` (131K ctx) — stark kontext-hantering.
- **Critic**: `nousresearch/hermes-3-llama-3.1-405b:free` (131K ctx) — disciplined JSON-utdata.
- **Image Analyst**: `nvidia/nemotron-nano-12b-v2-vl:free` (128K ctx, multimodal) — ersätter tidigare vision-default.
- **Global Fallback**: Llama-3.2-3B → snabb och lätt.

### Architecture rules for new integrations

1. **Background-first.** New tools run as background workers (asyncio tasks, separate threads). No new UI per tool — if data is interesting, expose it as a new React Flow node type via `App.tsx NODE_TYPES` map.
2. **Toggleable, never replace.** Each module is feature-flagged via env var or config file. Existing tools stay until the new one proves clearly superior across the board.
3. **Discard if worthless.** If a module adds complexity without solving a real problem TANGLE has, remove it. Don't accumulate dead weight.
4. **Document here before implementing.** Add to this table with phase tag. Implementation only when phase is reached.

### Open questions for Per

- ❓ Should `headroom` integration also surface compression stats in the React Flow canvas (a "compression-stats" node type)?
- ❓ Should `last30days` be primary scout or kept as fallback (next to Jina/SerpAPI)?
- ❓ Order of phases above — happy with headroom → last30days → promptfoo → Heretic → OpenViking → open-notebook, or want different sequence?
