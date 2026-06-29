"""TANGLE structured error taxonomy."""

from typing import Optional, Dict, Any


class TangleError(Exception):
    """Base exception for all TANGLE errors.

    Attributes:
        message: Human-readable error description
        code: Machine-readable error code for programmatic handling
        retryable: Whether the operation can be safely retried
        context: Additional structured data for debugging
    """

    def __init__(
        self,
        message: str,
        code: str,
        retryable: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.retryable = retryable
        self.context = context or {}

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(code={self.code!r}, retryable={self.retryable}, context={self.context})"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API responses or logging."""
        return {
            "error_type": self.__class__.__name__,
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "context": self.context,
        }


class ProviderError(TangleError):
    """LLM provider failure (OpenRouter, Gemini, Ollama).

    Usually retryable — provider may recover or fallback chain continues.
    """

    def __init__(
        self,
        message: str,
        provider: str,
        model: str = "",
        status_code: int = 0,
        retryable: bool = True,
        context: Optional[Dict[str, Any]] = None,
    ):
        ctx = context or {}
        ctx.update({"provider": provider, "model": model, "status_code": status_code})
        super().__init__(message, "PROVIDER_ERROR", retryable=retryable, context=ctx)


class IngestionError(TangleError):
    """File parsing/ingestion failure.

    Usually NOT retryable — same file will fail the same way.
    """

    def __init__(
        self,
        message: str,
        filepath: str = "",
        file_type: str = "",
        retryable: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ):
        ctx = context or {}
        ctx.update({"filepath": filepath, "file_type": file_type})
        super().__init__(message, "INGESTION_ERROR", retryable=retryable, context=ctx)


class VectorStoreError(TangleError):
    """Vector store failure (Qdrant, Supabase, SQLite).

    Usually retryable — transient connection/availability issues.
    """

    def __init__(
        self,
        message: str,
        store: str = "",
        operation: str = "",
        retryable: bool = True,
        context: Optional[Dict[str, Any]] = None,
    ):
        ctx = context or {}
        ctx.update({"store": store, "operation": operation})
        super().__init__(message, "VECTOR_STORE_ERROR", retryable=retryable, context=ctx)


class EvaluationError(TangleError):
    """Critic evaluation gate failure.

    NOT retryable — fail-open design marks content as unverified instead.
    """

    def __init__(
        self,
        message: str,
        criteria: str = "",
        score: float = 0.0,
        retryable: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ):
        ctx = context or {}
        ctx.update({"criteria": criteria, "score": score})
        super().__init__(message, "EVALUATION_ERROR", retryable=retryable, context=ctx)


class ConfigurationError(TangleError):
    """Misconfiguration detected at startup or runtime.

    NOT retryable — requires human intervention.
    """

    def __init__(
        self,
        message: str,
        setting: str = "",
        expected: str = "",
        actual: str = "",
        retryable: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ):
        ctx = context or {}
        ctx.update({"setting": setting, "expected": expected, "actual": actual})
        super().__init__(message, "CONFIGURATION_ERROR", retryable=retryable, context=ctx)


class CircuitBreakerError(TangleError):
    """Circuit breaker is open — failing fast without calling downstream."""

    def __init__(
        self,
        message: str,
        provider: str = "",
        failure_count: int = 0,
        retryable: bool = True,
        context: Optional[Dict[str, Any]] = None,
    ):
        ctx = context or {}
        ctx.update({"provider": provider, "failure_count": failure_count})
        super().__init__(message, "CIRCUIT_BREAKER_OPEN", retryable=retryable, context=ctx)