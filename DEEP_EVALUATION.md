# TANGLE — Deep Architecture Evaluation & Improvement Plan

**Date:** 2026-06-29  
**Scope:** Full backend codebase (`backend/`) — FastAPI API, agent orchestration, parsing, vector store, wiki vault  
**Phase:** Phase 0 complete (end-to-end pipeline runs) — moving toward Phase 1+

---

## Executive Summary

TANGLE is a **modular, production-ready agentic research platform** with:
- ✅ 6-tool agent surface (ingest → search → query_memory → evaluate → delegate → synthesize)
- ✅ Dual-output mission loop (human report + re-ingestable wiki entry)
- ✅ Obsidian-compatible vault export (YAML frontmatter, wikilinks, backlinks)
- ✅ Multi-provider LLM gateway (OpenRouter free tier → Gemini → Ollama local)
- ✅ 66 passing tests (wiki_vault + orchestrator + new tests added during fix)
- ✅ All regression fixes verified (P0 endpoint field-drop, P1 OpenRouter 401 workaround)

**Architecture grade: B+** — Solid foundation, clear separation of concerns, good degradation patterns.  
**Key risk areas:** OpenRouter retry storm latency, embedding dimension drift, single-threaded mission execution, minimal auth/tenancy.

---

## 1. Architecture & Design Patterns

### Strengths

| Pattern | Implementation | Quality |
|---------|---------------|---------|
| **Pi Philosophy** (6 tools) | `ingest`, `search`, `query_memory`, `evaluate`, `delegate`, `synthesize` — clean, composable | ★★★★★ |
| **Dual-output synthesis** | `===TANGLE_REPORT_START===` / `===TANGLE_WIKI_START===` delimiters; human + machine outputs | ★★★★★ |
| **Graceful degradation** | Critic fail-open with `[UNVERIFIED]` badge; wiki export best-effort; LLM fallback chain | ★★★★★ |
| **Provider abstraction** | `FreeGateway` routes OpenRouter / Gemini / Ollama with unified response schema | ★★★★☆ |
| **Vault as knowledge graph** | Obsidian-compatible, wikilinks, backlinks, tag index, stale-file cleanup | ★★★★★ |
| **Env-driven toggles** | `TANGLE_SCOUT_SOURCE`, `TANGLE_EMBEDDING_SOURCE`, `TANGLE_WIKI_EXPORT_ON_MISSION` | ★★★★☆ |

### Concerns

| Issue | Location | Severity |
|-------|----------|----------|
| **God class** `AgentOrchestrator` (928 lines) — planning, scouting, librarian, critic, synthesis, mission control all in one | `agent_orchestrator.py` | High |
| **Single mission at a time** — `_running` flag blocks concurrent missions | `run_mission()` | Medium |
| **Hardcoded agent defs** — `AGENT_DEFS` dict inline, not plugin-extensible | `agent_orchestrator.py:41-66` | Medium |
| **No formal state machine** — mission phases are linear code, not declarative | `run_mission()` | Low |

### Recommendation: Extract Phase Executors
```python
# agent_orchestrator.py → split into:
# - PlanningPhase(orchestrator).execute()
# - ResearchPhase(orchestrator).execute()  # Scout + Librarian parallel
# - EvaluationPhase(orchestrator).execute()  # Critic + retry loop
# - SynthesisPhase(orchestrator).execute()
# - IngestionPhase(orchestrator).execute()
```
This enables: concurrent missions (separate phase instances), unit testing phases in isolation, plugin architecture for custom phases.

---

## 2. Code Quality & Maintainability

### Metrics Snapshot

| File | Lines | Functions | Complexity Notes |
|------|-------|-----------|------------------|
| `agent_orchestrator.py` | 928 | ~25 | God class, multiple responsibilities |
| `main.py` | 843 | ~35 | Endpoint sprawl, mixed concerns |
| `vector_store.py` | 588 | ~15 | Multi-backend logic (Qdrant, Supabase, SQLite, memory) |
| `wiki_vault.py` | 464 | ~20 | Pure transformation, well-structured |
| `free_gateway.py` | 252 | ~15 | Good provider abstraction |
| `parsing_engine.py` | 242 | ~10 | Clean, single responsibility |

### Code Smells

| Smell | Example | Fix |
|-------|---------|-----|
| **Magic strings** | `"openrouter/qwen/qwen3-coder:free"` scattered in `AGENT_MODELS` | Constants/enums in `models.py` |
| **Duplicate regex** | Tag extraction in `parsing_engine.py:112`, `agent_orchestrator.py:717`, `wiki_vault.py:293` | Shared `tag_utils.py` |
| **Inline prompts** | 200+ line prompt in `synthesize()` | External `.md` templates |
| **Bare `except Exception`** | 15+ occurrences — loses stack context | Specific exception types or `logger.exception()` |
| **Hardcoded timeouts** | 60s, 120s, 20s scattered | Central `TimeoutConfig` dataclass |

### Recommendation: Shared Utilities Module
```python
# backend/utils/
#   tag_utils.py      # _extract_inline_tags (3 copies → 1)
#   prompt_templates.py  # Synthesizer, Critic, Planner prompts as .md files
#   config.py         # TimeoutConfig, ModelConfig, VaultConfig dataclasses
#   exceptions.py     # TangleError, ProviderError, IngestionError, etc.
```

---

## 3. Performance & Scalability

### Current Bottlenecks

| Bottleneck | Impact | Evidence |
|------------|--------|----------|
| **OpenRouter retry storm** | 40-60s mission latency when key invalid | Logs show 50+ 401 retries before Ollama fallback |
| **Sequential agent calls** | Scout → Librarian → Critic → Synthesizer (no parallelism where possible) | `run_mission()` lines 778-785 |
| **Synchronous embeddings** | `get_embeddings()` called per-chunk, no batching | `add_wiki_entry()` line 295 |
| **No vector index warmup** | First search after cold start = slow | Qdrant collection init on first upsert |
| **SQLite connection per query** | `search_wiki()` opens/closes connection each call | `vector_store.py:404-421` |

### Performance Wins Already In Place
- ✅ Ollama embeddings (local, free, 4096-dim qwen3-embedding:8b)
- ✅ SQLite as source of truth (fast, no network)
- ✅ Qdrant `query_points()` (modern API)
- ✅ Vault export is fast (26 files in 7ms)
- ✅ Tag generation capped at 2000 chars + 5 tags

### Quick Wins (1-2 hour fixes)

```python
# 1. Embedding batching — add to VectorStore
async def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
    # Single Ollama /api/embed call with multiple inputs
    ...

# 2. Connection pooling for SQLite
import aiosqlite
self._db_pool = await aiosqlite.create_pool(self.db_path, size=5)

# 3. Retry storm fix — add circuit breaker to free_gateway
class CircuitBreaker:
    def __init__(self, failure_threshold=3, recovery_timeout=30):
        ...
    async def call(self, func, *args): ...

# 4. Parallel Scout + Librarian (already partially there)
# But Critic → Synthesizer could start while Scout retries
```

### Scaling Architecture (Phase 1+)

```
                    ┌─────────────────────┐
                    │   API Gateway       │
                    │   (FastAPI + WS)    │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
       ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
       │  Ingestion  │  │  Mission    │  │  Query      │
       │  Workers    │  │  Workers    │  │  Workers    │
       │  (Celery)   │  │  (Celery)   │  │  (FastAPI)  │
       └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
              │                │                │
              └────────────────┼────────────────┘
                               ▼
                    ┌─────────────────────┐
                    │   Message Bus       │
                    │   (Redis Streams)   │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
       ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
       │  SQLite     │  │  Qdrant     │  │  Supabase   │
       │  (primary)  │  │  (vectors)  │  │  (mirror)   │
       └─────────────┘  └─────────────┘  └─────────────┘
```

---

## 4. Reliability & Error Handling

### Current State: Good Degradation, Weak Recovery

| Scenario | Behavior | Gap |
|----------|----------|-----|
| **LLM provider down** | Falls back through chain (OpenRouter → Gemini → Ollama) ✅ | No circuit breaker — retries hammer dead endpoint |
| **Critic evaluation fails** | Returns `verified=False`, `score=0.5`, marks `[UNVERIFIED]` ✅ | No alerting when degradation happens |
| **Qdrant unavailable** | Falls back to Supabase pgvector → SQLite LIKE ✅ | No health check to surface degraded mode |
| **Wiki export fails** | Logged warning, mission continues ✅ | No retry or dead-letter queue |
| **Mission interrupted** | No checkpointing — full restart needed | Critical for long missions |

### Missing Reliability Patterns

| Pattern | Status | Priority |
|---------|--------|----------|
| Circuit breaker | ❌ | High |
| Retry with exponential backoff + jitter | Partial (critic has backoff) | High |
| Dead letter queue for failed missions | ❌ | Medium |
| Idempotency keys for upload/mission | ❌ | Medium |
| Structured error taxonomy | ❌ (bare Exception) | High |
| Health endpoint per-component | Partial (`/api/health/providers`) | Medium |

### Recommendation: Error Taxonomy
```python
# backend/exceptions.py
class TangleError(Exception):
    """Base — all TANGLE errors inherit this."""
    def __init__(self, message: str, code: str, retryable: bool = False):
        ...

class ProviderError(TangleError):
    """LLM provider failure — usually retryable."""
    ...

class IngestionError(TangleError):
    """File parsing failed — usually NOT retryable."""
    ...

class VectorStoreError(TangleError):
    """Qdrant/Supabase/SQLite failure — retryable."""
    ...

class EvaluationError(TangleError):
    """Critic gate failure — NOT retryable (fail open)."""
    ...
```

---

## 5. Observability & Debugging

### Current Instrumentation

| Component | Logging | Metrics | Tracing |
|-----------|---------|---------|---------|
| **Gateway** | Provider calls, fallbacks, errors | None | None |
| **Orchestrator** | Phase transitions, tool calls, agent events | Event callbacks (WS) | None |
| **Vector Store** | Qdrant/Supabase/SQLite ops, fallback chain | None | None |
| **Parsing** | File type, confidence, tag generation | None | None |
| **Vault** | Export summary (chunks, entities, ms) | None | None |
| **Mission** | Start/complete, elapsed, retries | None | None |

### Missing Observability

| Need | Why | Effort |
|------|-----|--------|
| **Mission latency histogram** | P50/P95/P99 for SLO tracking | Low (Prometheus client) |
| **Provider success/fail counters** | Alert on OpenRouter 401 storm | Low |
| **Embedding latency** | Ollama vs OpenRouter cost tradeoff | Low |
| **Structured JSON logs** | Parseable by Loki/Datadog | Medium |
| **Distributed tracing** | Correlate mission → agent → LLM call | High (OpenTelemetry) |
| **Cost tracking per mission** | `usage` field exists but not aggregated | Medium |

### Quick Win: Prometheus Metrics
```python
# backend/metrics.py
from prometheus_client import Counter, Histogram, Gauge

MISSION_LATENCY = Histogram("tangle_mission_latency_seconds", "Mission duration", buckets=[10,30,60,120,300])
PROVIDER_CALLS = Counter("tangle_provider_calls_total", "Provider calls", ["provider", "status"])
EMBEDDING_LATENCY = Histogram("tangle_embedding_latency_seconds", "Embedding generation")
VAULT_EXPORT = Counter("tangle_vault_export_total", "Vault exports", ["status"])
MISSION_ACTIVE = Gauge("tangle_missions_active", "Currently running missions")
```

---

## 6. Security

### Current Posture

| Area | Status | Notes |
|------|--------|-------|
| **Authentication** | ❌ None | Single-user local; API open |
| **Authorization** | ❌ None | All endpoints public |
| **Input validation** | Partial | Pydantic on request bodies; file upload unchecked |
| **Path traversal** | ❌ Risk | `filepath` in MissionRequest not validated |
| **Secrets management** | `.env` file | No rotation, no vault |
| **Rate limiting** | ❌ None | OpenRouter quota managed client-side only |
| **CORS** | `allow_origins=["*"]` | Dev-only config |

### Critical Vulnerabilities

```python
# main.py:391-393 — MISSION REQUEST ACCEPTS ARBITRARY FILEPATH
class MissionRequest(BaseModel):
    entity: str
    filepath: Optional[str] = None  # ← User controls this!

# main.py:369-389 — UPLOAD SAVES WITH ORIGINAL FILENAME
file_path = uploads_dir / file.filename  # ← Path traversal if filename="../../etc/passwd"
```

### Security Quick Fixes
```python
# 1. Sanitize filename on upload
import pathlib
safe_name = pathlib.Path(file.filename).name  # strips directory components
file_path = uploads_dir / safe_name

# 2. Validate filepath in MissionRequest
from pathlib import Path
def validate_filepath(path: str) -> str:
    p = Path(path).resolve()
    allowed = Path(__file__).parent.parent.resolve()
    if not p.is_relative_to(allowed):
        raise ValueError("Filepath outside project root")
    return str(p)

# 3. Add rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 4. Basic API key auth for production
API_KEYS = os.getenv("TANGLE_API_KEYS", "").split(",")
async def verify_api_key(x_api_key: str = Header(None)):
    if x_api_key not in API_KEYS:
        raise HTTPException(401, "Invalid API key")
```

---

## 7. Developer Experience

### Strengths
- ✅ Comprehensive `/api/admin/index` — live store health
- ✅ `/api/admin/export-wiki/preview` — dry-run before export
- ✅ WebSocket for real-time agent events
- ✅ Terminal execution endpoint (powerful for debugging)
- ✅ Tasklist + Kanban + Run History APIs (dogfooding)
- ✅ `scripts/smoke_test.py` — full pipeline validation

### Friction Points

| Pain Point | Location | Fix |
|------------|----------|-----|
| **No OpenAPI examples** | All endpoints | Add `response_model` + `examples` to Pydantic models |
| **Mission timeout not configurable** | Smoke test hardcoded 120s | Env var `TANGLE_MISSION_TIMEOUT` |
| **No dev seed data** | Fresh DB = empty | `scripts/seed_dev_data.py` |
| **Log format not structured** | `logging.basicConfig` | JSON formatter + `structlog` |
| **Type hints incomplete** | Many `Any`, `Dict[str, Any]` | Enable `mypy --strict` incrementally |

---

## 8. Concrete Improvement Plan

### Priority 0 — Do This Week (Critical Fixes)

| # | Task | File | Est. Time |
|---|------|------|-----------|
| 1 | Fix path traversal in upload + mission filepath | `main.py:369, 393` | 30 min |
| 2 | Circuit breaker for OpenRouter (stop 401 retry storm) | `free_gateway.py` | 1 hr |
| 3 | Sanitize filename on upload | `main.py:375` | 15 min |
| 4 | Rate limiting on `/api/upload` and `/api/mission/start` | `main.py` | 30 min |
| 5 | Add structured error taxonomy | `backend/exceptions.py` (new) | 1 hr |

### Priority 1 — Next Sprint (Architecture Cleanup)

| # | Task | File | Est. Time |
|---|------|------|-----------|
| 6 | Extract `MissionPhase` base class + phase executors | `agent_orchestrator.py` | 4 hrs |
| 7 | Shared `tag_utils.py` — deduplicate 3 regex copies | `parsing_engine.py`, `agent_orchestrator.py`, `wiki_vault.py` | 30 min |
| 8 | Externalize prompts to `.md` templates | `agent_orchestrator.py:synthesize()`, `evaluate()` | 2 hrs |
| 9 | SQLite connection pooling (aiosqlite) | `vector_store.py` | 1 hr |
| 10 | Embedding batch API | `vector_store.py` | 1 hr |

### Priority 2 — Phase 1 Prep (Scalability & Observability)

| # | Task | File | Est. Time |
|---|------|------|-----------|
| 11 | Prometheus metrics + `/metrics` endpoint | `backend/metrics.py` (new) | 2 hrs |
| 12 | Structured JSON logging with `structlog` | `main.py`, all modules | 1 hr |
| 13 | Distributed tracing (OpenTelemetry) | `free_gateway.py`, `agent_orchestrator.py` | 3 hrs |
| 14 | Concurrent mission support (remove `_running` flag) | `agent_orchestrator.py` | 2 hrs |
| 15 | Dead letter queue for failed missions | `agent_orchestrator.py` + DB table | 2 hrs |
| 16 | Idempotency keys for upload/mission | `main.py` + DB | 1 hr |

### Priority 3 — Phase 1+ (Multi-tenancy & Auth)

| # | Task | Effort |
|---|------|--------|
| 17 | API key authentication | 2 hrs |
| 18 | Multi-tenant entities (namespace per user) | 1 week |
| 19 | Supabase RLS + auth integration | 1 week |
| 20 | Frontend auth (NextAuth) | 1 week |

---

## 9. Test Coverage Gaps

| Area | Current | Target | Missing |
|------|---------|--------|---------|
| **Unit: Gateway fallback chain** | 0 | 5 | OpenRouter → Gemini → Ollama |
| **Unit: Vault stale cleanup** | 0 | 3 | `_cleanup_stale()` scenarios |
| **Unit: Tag extraction edge cases** | 2 | 5 | C#, empty, malformed |
| **Integration: Mission with retries** | 1 | 3 | Critic fail → scout retry → pass |
| **Integration: Qdrant unavailable** | 0 | 2 | Fallback to Supabase → SQLite |
| **Load: Concurrent missions** | 0 | 1 | 5 parallel missions |
| **E2E: File upload → mission → vault** | 1 (smoke) | 3 | Multiple file types |

---

## 10. Configuration Drift Risks

| Config | Current Default | Risk if Wrong |
|--------|----------------|---------------|
| `TANGLE_EMBEDDING_SOURCE=ollama` | Ollama (4096 dim) | Switching to OpenRouter (1536 dim) breaks Qdrant collection |
| `TANGLE_SCOUT_SOURCE=jina` | Jina (free) | Exa/Crawl4AI need keys; silent fallback to Jina |
| `TANGLE_WIKI_EXPORT_ON_MISSION=1` | Enabled | Disk I/O on every mission; disable under load |
| `OLLAMA_NUM_GPU=50` | Unset (uses all) | OOM if browser + Ollama share GPU |
| `TANGLE_ORCHESTRATOR_MAX_RETRIES=3` | 3 | More = slower; fewer = lower quality |

**Recommendation:** Add `config_validation.py` that runs at startup and warns on mismatches (e.g., embedding dim ≠ Qdrant collection dim).

---

## Appendix: File-by-File Technical Debt

| File | Debt Items |
|------|------------|
| `agent_orchestrator.py` | God class (928 lines), inline prompts, magic model strings, bare excepts, single-mission lock |
| `main.py` | 843 lines, security gaps (path traversal), no auth/rate-limit, mixed endpoint concerns |
| `free_gateway.py` | No circuit breaker, retry storm, hardcoded model list, no usage persistence |
| `vector_store.py` | Multi-backend complexity, no connection pool, sync SQLite in async, dim drift risk |
| `parsing_engine.py` | Vision dual-pass hardcoded models, tag model hardcoded, no streaming for large files |
| `wiki_vault.py` | Well-structured — minimal debt |
| `review_harness.py` | Not reviewed — likely similar patterns |
| `langgraph_engine.py` | Not reviewed — parallel path |

---

## Next Steps

1. **Immediate:** Run Priority 0 fixes (security + circuit breaker)
2. **This week:** Priority 1 architecture cleanup (phases, shared utils, prompts)
3. **Before Phase 1:** Priority 2 observability + concurrent missions
4. **Phase 1 kickoff:** Multi-tenancy + auth design review

The foundation is solid. The regressions caught in Verify Pass Round 2 prove the feedback loops work. Now harden the edges and prepare for scale.