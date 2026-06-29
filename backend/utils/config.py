"""Centralized configuration dataclasses for TANGLE.

All timeout, model, and embedding settings in one place.
Environment variable fallbacks documented per-field.
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class TimeoutConfig:
    """Timeout settings for external calls.

    All values in seconds.
    """
    # LLM chat completion
    chat_default: int = int(os.getenv("TANGLE_TIMEOUT_CHAT", "60"))
    chat_long: int = int(os.getenv("TANGLE_TIMEOUT_CHAT_LONG", "120"))

    # Embedding generation
    embedding_default: int = int(os.getenv("TANGLE_TIMEOUT_EMBEDDING", "30"))
    embedding_batch: int = int(os.getenv("TANGLE_TIMEOUT_EMBEDDING_BATCH", "120"))

    # Web search
    jina_search: int = int(os.getenv("TANGLE_TIMEOUT_JINA", "15"))
    exa_search: int = int(os.getenv("TANGLE_TIMEOUT_EXA", "20"))
    crawl4ai_per_url: int = int(os.getenv("TANGLE_TIMEOUT_CRAWL4AI", "20"))

    # Mission-level
    mission_default: int = int(os.getenv("TANGLE_TIMEOUT_MISSION", "300"))
    mission_max_retries: int = int(os.getenv("TANGLE_ORCHESTRATOR_MAX_RETRIES", "3"))
    critic_backoff_base: int = 2  # 1s, 2s, 4s...

    # Provider health checks
    ollama_health: int = int(os.getenv("TANGLE_TIMEOUT_OLLAMA_HEALTH", "5"))


@dataclass(frozen=True)
class ModelConfig:
    """Model selection and fallback chains per agent role.

    Each role has an ordered list — first available model is used.
    """
    # High-reasoning / planning / synthesis → best structured-output models
    planner: List[str] = field(default_factory=lambda: [
        "openrouter/qwen/qwen3-coder:free",
        "openrouter/openai/gpt-oss-120b:free",
        "openrouter/meta-llama/llama-3.3-70b-instruct:free",
    ])
    synthesizer: List[str] = field(default_factory=lambda: [
        "openrouter/qwen/qwen3-coder:free",
        "openrouter/openai/gpt-oss-120b:free",
        "openrouter/meta-llama/llama-3.3-70b-instruct:free",
    ])

    # Scout (web search summarization) → solid all-rounder
    scout: List[str] = field(default_factory=lambda: [
        "openrouter/meta-llama/llama-3.3-70b-instruct:free",
        "openrouter/nousresearch/hermes-3-llama-3.1-405b:free",
        "openrouter/openai/gpt-oss-120b:free",
    ])

    # Librarian (internal wiki recall) → strong long-context summarizer
    librarian: List[str] = field(default_factory=lambda: [
        "openrouter/openai/gpt-oss-120b:free",
        "openrouter/meta-llama/llama-3.3-70b-instruct:free",
        "openrouter/nousresearch/hermes-3-llama-3.1-405b:free",
    ])

    # Critic (JSON eval gate) → disciplined instruction follower
    critic: List[str] = field(default_factory=lambda: [
        "openrouter/nousresearch/hermes-3-llama-3.1-405b:free",
        "openrouter/qwen/qwen3-coder:free",
        "openrouter/openai/gpt-oss-120b:free",
    ])

    # Image analyst → vision-capable
    image_analyst: List[str] = field(default_factory=lambda: [
        "openrouter/nvidia/nemotron-nano-12b-v2-vl:free",
        "openrouter/google/gemma-4-31b-it:free",
    ])

    # Generic / unknown agent
    default: List[str] = field(default_factory=lambda: [
        "openrouter/meta-llama/llama-3.3-70b-instruct:free",
        "openrouter/openai/gpt-oss-120b:free",
        "openrouter/nousresearch/hermes-3-llama-3.1-405b:free",
        "openrouter/meta-llama/llama-3.2-3b-instruct:free",
    ])

    # Ollama local models (fallback chain)
    ollama_chat: List[str] = field(default_factory=lambda: [
        "llama3.2:3b",
        "llama3.1:8b",
        "qwen3:8b",
        "llama3.2:1b",
        "phi4-mini:3.8b",
    ])

    # Tag generation — cheap vision model handles text too
    tag_generation: str = "openrouter/nvidia/nemotron-nano-12b-v2-vl:free"

    # Vision pass 1 (cheap) → pass 2 (premium)
    vision_cheap: str = "openrouter/nvidia/nemotron-nano-12b-v2-vl:free"
    vision_premium: str = "openrouter/anthropic/claude-3.5-sonnet"


@dataclass(frozen=True)
class VaultConfig:
    """Wiki vault export settings."""
    export settings."""
    export_on_mission: bool = os.getenv("TANGLE_WIKI_EXPORT_ON_MISSION", "1") not in ("0", "false", "False", "")
    vault_root: str = str(Path(__file__).parent.parent / "docs" / "wiki")
    db_path: str = str(Path(__file__).parent.parent / "tangle.db")


@dataclass(frozen=True)
class EmbeddingConfig:
    """Embedding generation settings."""
    source: str = os.getenv("TANGLE_EMBEDDING_SOURCE", "ollama").strip().lower()
    ollama_model: str = os.getenv("TANGLE_OLLAMA_EMBED_MODEL", "qwen3-embedding:8b")
    ollama_base: str = "http://localhost:11434"
    openrouter_model: str = "openai/text-embedding-3-small"
    openrouter_dim: int = 1536
    ollama_dim: int = 4096
    sha256_fallback: bool = True

    @property
    def dimension(self) -> int:
        if self.source == "openrouter":
            return self.openrouter_dim
        return self.ollama_dim


@dataclass(frozen=True)
class ScoutConfig:
    """Scout web search configuration."""
    source: str = os.getenv("TANGLE_SCOUT_SOURCE", "jina").strip().lower()
    exa_api_key: str = os.getenv("EXA_API_KEY", "")
    jina_api_key: str = os.getenv("JINA_API_KEY", "")
    crawl4ai_available: bool = False  # Set at runtime


@dataclass(frozen=True)
class CircuitBreakerConfig:
    """Circuit breaker settings for provider resilience."""
    failure_threshold: int = int(os.getenv("TANGLE_CB_FAILURE_THRESHOLD", "3"))
    recovery_timeout: int = int(os.getenv("TANGLE_CB_RECOVERY_TIMEOUT", "30"))  # seconds
    half_open_max_calls: int = int(os.getenv("TANGLE_CB_HALF_OPEN_MAX", "1"))


# Global config instance (lazy init)
_config: Optional["TangleConfig"] = None


@dataclass
class TangleConfig:
    """Aggregate configuration."""
    timeout: TimeoutConfig = field(default_factory=TimeoutConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    vault: VaultConfig = field(default_factory=VaultConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    scout: ScoutConfig = field(default_factory=ScoutConfig)
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)

    # Provider API keys
    openrouter_key: str = os.getenv("OPENROUTER_API_KEY", "")
    gemini_key: str = os.getenv("GEMINI_API_KEY", "")

    # Supabase
    supabase_enabled: bool = os.getenv("TANGLE_SUPABASE_ENABLED", "").strip() in ("1", "true", "True")
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv("SUPABASE_ANON_KEY", "")

    # Qdrant
    qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_key: str = os.getenv("QDRANT_API_KEY", "")


def get_config() -> TangleConfig:
    """Get global config instance (singleton)."""
    global _config
    if _config is None:
        _config = TangleConfig()
    return _config


# Import Path for VaultConfig
from pathlib import Path