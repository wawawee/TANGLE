"""Prometheus metrics for TANGLE.

Provides observability for:
- Mission latency and success rates
- Provider call counts and latency
- Embedding generation performance
- Vault export statistics
- Active mission tracking

Usage:
    from metrics import MISSION_LATENCY, PROVIDER_CALLS, record_mission_latency

    # In a phase or orchestrator:
    with MISSION_LATENCY.time():
        result = await phase.execute(ctx)

    # Or manually:
    PROVIDER_CALLS.labels(provider="ollama", status="success").inc()
"""

import time
import logging
from typing import Optional
from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST

logger = logging.getLogger("tangle.metrics")

# ── Mission Metrics ──────────────────────────────────────────────

MISSION_LATENCY = Histogram(
    "tangle_mission_latency_seconds",
    "Mission execution duration in seconds",
    buckets=[10, 30, 60, 120, 180, 240, 300, 420, 600],
)

MISSION_TOTAL = Counter(
    "tangle_missions_total",
    "Total missions started",
    ["status"],  # success, failed, timeout
)

MISSION_ACTIVE = Gauge(
    "tangle_missions_active",
    "Currently running missions",
)

# ── Provider Metrics ─────────────────────────────────────────────

PROVIDER_CALLS = Counter(
    "tangle_provider_calls_total",
    "LLM provider calls",
    ["provider", "status"],  # provider: openrouter, gemini, ollama; status: success, error, timeout
)

PROVIDER_LATENCY = Histogram(
    "tangle_provider_latency_seconds",
    "LLM provider call latency",
    ["provider"],
    buckets=[0.5, 1, 2, 5, 10, 20, 30, 60],
)

# ── Embedding Metrics ────────────────────────────────────────────

EMBEDDING_LATENCY = Histogram(
    "tangle_embedding_latency_seconds",
    "Embedding generation latency",
    ["source"],  # source: ollama, openrouter, sha256
    buckets=[0.1, 0.25, 0.5, 1, 2, 5],
)

EMBEDDING_BATCH_SIZE = Histogram(
    "tangle_embedding_batch_size",
    "Number of texts per embedding batch",
    buckets=[1, 2, 5, 10, 20, 50],
)

# ── Vector Store Metrics ─────────────────────────────────────────

VECTOR_OPS = Counter(
    "tangle_vector_ops_total",
    "Vector store operations",
    ["backend", "operation", "status"],  # backend: qdrant, supabase, sqlite; operation: upsert, search
)

VECTOR_SEARCH_LATENCY = Histogram(
    "tangle_vector_search_latency_seconds",
    "Vector search latency",
    ["backend"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1],
)

# ── Vault Metrics ────────────────────────────────────────────────

VAULT_EXPORT = Counter(
    "tangle_vault_export_total",
    "Vault export operations",
    ["status"],  # status: success, error
)

VAULT_FILES = Gauge(
    "tangle_vault_files",
    "Number of files in vault",
)

# ── Parsing Metrics ──────────────────────────────────────────────

PARSING_OPS = Counter(
    "tangle_parsing_ops_total",
    "File parsing operations",
    ["file_type", "status"],  # file_type: pdf, docx, xlsx, txt, image; status: success, error
)

# ── Critic Metrics ───────────────────────────────────────────────

CRITIC_EVALUATIONS = Counter(
    "tangle_critic_evaluations_total",
    "Critic evaluation outcomes",
    ["passed", "verified"],  # passed: true, false; verified: true, false
)

CRITIC_SCORE = Histogram(
    "tangle_critic_score",
    "Critic evaluation scores",
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

# ── System Info ──────────────────────────────────────────────────

SYSTEM_INFO = Info(
    "tangle_system",
    "TANGLE system information",
)


def init_metrics():
    """Initialize system info metrics."""
    SYSTEM_INFO.info({
        "version": "0.1.0",
        "phase": "phase-0",
        "embedding_source": "ollama",
    })
    logger.info("Prometheus metrics initialized")


def get_metrics() -> str:
    """Generate Prometheus metrics output."""
    return generate_latest()


def get_metrics_content_type() -> str:
    """Return the content type for Prometheus metrics."""
    return CONTENT_TYPE_LATEST


# ── Helper Functions ─────────────────────────────────────────────

def record_mission_latency(duration: float, status: str = "success"):
    """Record mission latency and increment counter."""
    MISSION_LATENCY.observe(duration)
    MISSION_TOTAL.labels(status=status).inc()


def record_provider_call(provider: str, duration: float, status: str = "success"):
    """Record provider call metrics."""
    PROVIDER_CALLS.labels(provider=provider, status=status).inc()
    PROVIDER_LATENCY.labels(provider=provider).observe(duration)


def record_embedding_latency(source: str, duration: float, batch_size: int = 1):
    """Record embedding generation metrics."""
    EMBEDDING_LATENCY.labels(source=source).observe(duration)
    EMBEDDING_BATCH_SIZE.observe(batch_size)


def record_vector_op(backend: str, operation: str, status: str = "success", latency: float = 0):
    """Record vector store operation."""
    VECTOR_OPS.labels(backend=backend, operation=operation, status=status).inc()
    if latency > 0:
        VECTOR_SEARCH_LATENCY.labels(backend=backend).observe(latency)


def record_vault_export(status: str = "success", file_count: int = 0):
    """Record vault export metrics."""
    VAULT_EXPORT.labels(status=status).inc()
    if file_count > 0:
        VAULT_FILES.set(file_count)


def record_parsing(file_type: str, status: str = "success"):
    """Record file parsing operation."""
    PARSING_OPS.labels(file_type=file_type, status=status).inc()


def record_critic(score: float, passed: bool, verified: bool):
    """Record critic evaluation."""
    CRITIC_EVALUATIONS.labels(passed=str(passed).lower(), verified=str(verified).lower()).inc()
    CRITIC_SCORE.observe(score)


def increment_active_missions():
    """Increment active missions gauge."""
    MISSION_ACTIVE.inc()


def decrement_active_missions():
    """Decrement active missions gauge."""
    MISSION_ACTIVE.dec()
