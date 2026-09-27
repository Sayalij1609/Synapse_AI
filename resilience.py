"""
SYNAPSE AI — Production-Grade Fault Tolerance & Resilience Engine.

Provides:
1. Structured error taxonomy with retryability and target tracking
2. Exponential backoff retry with random jitter
3. Per-operation cross-platform execution timeouts
4. Circuit breaker protection (service-level and per-domain)
5. Graceful degradation mechanisms for Search, Scraping, Vector Retrieval, LLMs, and Database
6. Persistent error and degradation auditing
"""

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime
from enum import Enum
import logging
import random
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

logger = logging.getLogger("synapse.resilience")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# =====================================================================
# 1. Structured Error Taxonomy
# =====================================================================

class SynapseBaseError(Exception):
    """Base exception for all SYNAPSE operational and agent failures."""

    def __init__(
        self,
        message: str,
        operation: str = "general",
        target: Optional[str] = None,
        retryable: bool = False,
        error_code: str = "SYNAPSE_INTERNAL_ERROR",
        original_exception: Optional[Exception] = None,
        user_message: Optional[str] = None,
        domain: Optional[str] = None,
        status_code: Optional[int] = None,
        code: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(message)
        self.message = message
        self.operation = operation
        self.target = target
        self.retryable = retryable
        self.code = code or error_code
        self.error_code = self.code
        self.original_exception = original_exception
        self.domain = domain
        self.status_code = status_code
        self.user_message = user_message or self._build_user_message()
        self.timestamp = datetime.now().isoformat()
        self.extra = kwargs

    def _build_user_message(self) -> str:
        return f"Operation encountered an issue ({self.code}): {self.message}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "error_code": self.error_code,
            "message": self.message,
            "operation": self.operation,
            "target": self.target,
            "retryable": self.retryable,
            "status_code": self.status_code,
            "domain": self.domain,
            "user_message": self.user_message,
            "timestamp": self.timestamp,
            "original_exception": str(self.original_exception) if self.original_exception else None,
        }


# ── Search Errors ─────────────────────────────────────────────

class SearchError(SynapseBaseError):
    def __init__(self, message: str, target: Optional[str] = None, retryable: bool = True, error_code: str = "SEARCH_ERROR", **kwargs):
        err_code = kwargs.pop("code", None) or kwargs.pop("error_code", None) or error_code
        super().__init__(message, operation="search", target=target, retryable=retryable, error_code=err_code, **kwargs)


class SearchTimeoutError(SearchError):
    def __init__(self, message: str, target: Optional[str] = None, **kwargs):
        super().__init__(message, target=target, retryable=True, error_code="SEARCH_TIMEOUT", **kwargs)


class SearchRateLimitError(SearchError):
    def __init__(self, message: str, target: Optional[str] = None, **kwargs):
        super().__init__(message, target=target, retryable=True, error_code="SEARCH_RATE_LIMIT", **kwargs)


class SearchEmptyError(SearchError):
    def __init__(self, message: str, target: Optional[str] = None, **kwargs):
        super().__init__(message, target=target, retryable=False, error_code="SEARCH_EMPTY_RESULTS", **kwargs)


# ── Scraping & HTTP Errors ────────────────────────────────────

class ScrapingError(SynapseBaseError):
    def __init__(self, message: str, target: Optional[str] = None, retryable: bool = False, error_code: str = "SCRAPE_ERROR", **kwargs):
        err_code = kwargs.pop("code", None) or kwargs.pop("error_code", None) or error_code
        super().__init__(message, operation="scraping", target=target, retryable=retryable, error_code=err_code, **kwargs)


class HttpScrapeError(ScrapingError):
    def __init__(self, message: str, status_code: int = 500, target: Optional[str] = None, domain: Optional[str] = None, **kwargs):
        retryable = kwargs.pop("retryable", status_code in (429, 500, 502, 503, 504))
        err_code = kwargs.pop("code", None) or kwargs.pop("error_code", None) or f"HTTP_{status_code}"
        super().__init__(message, target=target, retryable=retryable, error_code=err_code, domain=domain, status_code=status_code, **kwargs)
        self.status_code = status_code


class ScrapeTimeoutError(ScrapingError):
    def __init__(self, message: str, target: Optional[str] = None, **kwargs):
        super().__init__(message, target=target, retryable=True, error_code="SCRAPE_TIMEOUT", **kwargs)


class MalformedContentError(ScrapingError):
    def __init__(self, message: str, target: Optional[str] = None, **kwargs):
        super().__init__(message, target=target, retryable=False, error_code="MALFORMED_CONTENT", **kwargs)


# ── LLM Errors ────────────────────────────────────────────────

class LLMError(SynapseBaseError):
    def __init__(self, message: str, target: Optional[str] = None, retryable: bool = True, error_code: str = "LLM_ERROR", **kwargs):
        err_code = kwargs.pop("code", None) or kwargs.pop("error_code", None) or error_code
        super().__init__(message, operation="llm", target=target, retryable=retryable, error_code=err_code, **kwargs)


class LLMRateLimitError(LLMError):
    def __init__(self, message: str, target: Optional[str] = None, **kwargs):
        super().__init__(message, target=target, retryable=True, error_code="LLM_RATE_LIMIT", **kwargs)


class LLMTimeoutError(LLMError):
    def __init__(self, message: str, target: Optional[str] = None, **kwargs):
        super().__init__(message, target=target, retryable=True, error_code="LLM_TIMEOUT", **kwargs)


class LLMOutputFormatError(LLMError):
    def __init__(self, message: str, target: Optional[str] = None, **kwargs):
        super().__init__(message, target=target, retryable=False, error_code="LLM_OUTPUT_FORMAT_ERROR", **kwargs)


class LLMUnavailableError(LLMError):
    def __init__(self, message: str, target: Optional[str] = None, **kwargs):
        super().__init__(message, target=target, retryable=True, error_code="LLM_UNAVAILABLE", **kwargs)


# ── Vector Store & Embedding Errors ───────────────────────────

class EmbeddingError(SynapseBaseError):
    def __init__(self, message: str, target: Optional[str] = None, retryable: bool = False, **kwargs):
        super().__init__(message, operation="embedding", target=target, retryable=retryable, error_code="EMBEDDING_ERROR", **kwargs)


class VectorStoreError(SynapseBaseError):
    def __init__(self, message: str, target: Optional[str] = None, retryable: bool = False, **kwargs):
        super().__init__(message, operation="vector_store", target=target, retryable=retryable, error_code="VECTOR_STORE_ERROR", **kwargs)


# ── Database Errors ───────────────────────────────────────────

class DatabaseError(SynapseBaseError):
    def __init__(self, message: str, target: Optional[str] = None, retryable: bool = True, **kwargs):
        super().__init__(message, operation="database", target=target, retryable=retryable, error_code="DATABASE_ERROR", **kwargs)


# ── Circuit Breaker Error ─────────────────────────────────────

class CircuitBreakerOpenError(SynapseBaseError):
    def __init__(self, message: str, target: Optional[str] = None, **kwargs):
        super().__init__(message, operation="circuit_breaker", target=target, retryable=False, error_code="CIRCUIT_BREAKER_OPEN", **kwargs)


# =====================================================================
# 2. Circuit Breaker Implementation
# =====================================================================

class CircuitState(Enum):
    CLOSED = "CLOSED"      # Normal operation: all calls allowed
    OPEN = "OPEN"          # Tripped: fast-fail calls without network invocation
    HALF_OPEN = "HALF_OPEN"# Canary probe: allow single test request to check recovery

CircuitBreakerState = CircuitState


class CircuitBreaker:
    """
    Standard Circuit Breaker to prevent thundering herd against broken or
    hostile remote endpoints (search APIs, paywalled or slow domains, LLMs).
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_time: float = 30.0,
        expected_exceptions: Tuple[Type[Exception], ...] = (Exception,),
        recovery_timeout: Optional[float] = None,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_timeout if recovery_timeout is not None else recovery_time
        self.expected_exceptions = expected_exceptions

        self._lock = threading.Lock()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_state_change = time.time()
        self._last_failure_time = 0.0

    @property
    def state(self) -> CircuitState:
        with self._lock:
            # Check for recovery timeout when in OPEN state
            if self._state == CircuitState.OPEN:
                if (time.time() - self._last_state_change) >= self.recovery_time:
                    self._state = CircuitState.HALF_OPEN
                    self._last_state_change = time.time()
                    logger.info("CircuitBreaker [%s] transitioned to HALF_OPEN (probing recovery)", self.name)
            return self._state

    def allow_request(self) -> bool:
        """Return True if request is permitted to proceed, False if circuit is OPEN."""
        current_state = self.state
        if current_state == CircuitState.CLOSED:
            return True
        elif current_state == CircuitState.HALF_OPEN:
            return True
        return False

    def record_success(self):
        """Record successful invocation. Resets failure counters and closes circuit."""
        with self._lock:
            if self._state != CircuitState.CLOSED:
                logger.info("CircuitBreaker [%s] recovered! State reset to CLOSED.", self.name)
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_state_change = time.time()

    def record_failure(self, exception: Optional[Exception] = None):
        """Record failed invocation. Trips to OPEN when failure threshold is reached."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            logger.warning(
                "CircuitBreaker [%s] recorded failure %d/%d (%s)",
                self.name, self._failure_count, self.failure_threshold, str(exception)
            )

            if self._state == CircuitState.HALF_OPEN or self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._last_state_change = time.time()
                logger.error(
                    "CircuitBreaker [%s] TRIPPED to OPEN state! Blocking requests for %.1fs",
                    self.name, self.recovery_time
                )

    def execute(self, fn: Callable[..., Any], *args, **kwargs) -> Any:
        """Wrap callable execution inside circuit breaker protection."""
        if not self.allow_request():
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is currently OPEN. Requests temporarily halted for recovery.",
                target=self.name
            )

        try:
            result = fn(*args, **kwargs)
            self.record_success()
            return result
        except self.expected_exceptions as e:
            self.record_failure(e)
            raise


class DomainCircuitRegistry:
    """
    Thread-safe registry of domain-specific circuit breakers.
    Prevents repetitive 10s timeout stalls against unreachable or paywalled hosts.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_time: float = 60.0,
        recovery_timeout: Optional[float] = None,
    ):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_timeout if recovery_timeout is not None else recovery_time

    def get_breaker(self, domain: str) -> CircuitBreaker:
        clean_domain = (domain or "unknown").strip().lower()
        with self._lock:
            if clean_domain not in self._breakers:
                self._breakers[clean_domain] = CircuitBreaker(
                    name=f"domain:{clean_domain}",
                    failure_threshold=self.failure_threshold,
                    recovery_time=self.recovery_time,
                )
            return self._breakers[clean_domain]

    def is_domain_open(self, domain: str) -> bool:
        clean_domain = (domain or "unknown").strip().lower()
        with self._lock:
            breaker = self._breakers.get(clean_domain)
            if not breaker:
                return False
            return breaker.state == CircuitState.OPEN

    def can_attempt(self, domain: str) -> bool:
        return self.get_breaker(domain).allow_request()

    def record_failure(self, domain: str, error_message: Optional[str] = None):
        self.get_breaker(domain).record_failure(ValueError(error_message) if error_message else None)

    def record_success(self, domain: str):
        self.get_breaker(domain).record_success()

    def execute(self, domain: str, func, *args, **kwargs):
        return self.get_breaker(domain).execute(func, *args, **kwargs)


# Global registries
_domain_registry = DomainCircuitRegistry(failure_threshold=2, recovery_time=45.0)
_search_circuit_breaker = CircuitBreaker("duckduckgo_search", failure_threshold=4, recovery_time=30.0)
_llm_circuit_breaker = CircuitBreaker("groq_llm", failure_threshold=4, recovery_time=25.0)


def get_domain_circuit_registry() -> DomainCircuitRegistry:
    return _domain_registry


def get_search_circuit_breaker() -> CircuitBreaker:
    return _search_circuit_breaker


def get_llm_circuit_breaker() -> CircuitBreaker:
    return _llm_circuit_breaker


# =====================================================================
# 3. Exponential Backoff with Jitter
# =====================================================================

def execute_with_retry(
    fn: Callable[..., Any],
    *args,
    max_retries: int = 3,
    initial_delay: float = 0.5,
    backoff_factor: float = 2.0,
    max_delay: float = 8.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    retry_condition: Optional[Callable[[Exception], bool]] = None,
    operation_name: str = "Operation",
    **kwargs
) -> Any:
    """
    Executes callable with exponential backoff, maximum retries, and randomized jitter.
    """
    last_err: Optional[Exception] = None
    delay = initial_delay

    for attempt in range(1, max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except retryable_exceptions as e:
            last_err = e

            # Check if exception has retryable attribute marked false
            if hasattr(e, "retryable") and not e.retryable:
                logger.info("[%s] Exception marked as non-retryable: %s", operation_name, str(e))
                raise

            # Check custom retry condition if supplied
            if retry_condition and not retry_condition(e):
                logger.info("[%s] Exception not retryable according to condition: %s", operation_name, str(e))
                raise

            if attempt == max_retries:
                logger.error(
                    "[%s] All %d retry attempts failed: %s",
                    operation_name, max_retries, str(e)
                )
                break

            # Calculate delay with jitter
            jitter = random.uniform(0, 0.25 * delay)
            sleep_duration = min(max_delay, delay + jitter)
            logger.warning(
                "[%s] Attempt %d/%d failed: %s. Retrying in %.2fs...",
                operation_name, attempt, max_retries, str(e), sleep_duration
            )
            time.sleep(sleep_duration)
            delay = min(max_delay, delay * backoff_factor)

    if last_err:
        raise last_err
    raise SynapseBaseError(f"[{operation_name}] Execution failed after {max_retries} attempts.")


# =====================================================================
# 4. Per-Operation Execution Timeout (Cross-Platform)
# =====================================================================

def execute_with_timeout(
    fn: Callable[..., Any],
    *args,
    timeout_seconds: float = 10.0,
    operation_name: str = "Operation",
    timeout_exception_cls: Type[SynapseBaseError] = SynapseBaseError,
    target: Optional[str] = None,
    **kwargs
) -> Any:
    """
    Executes a callable with a strict cross-platform timeout using ThreadPoolExecutor.
    Guarantees operations (e.g. external network requests, embeddings, LLMs) never hang.
    """
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"synapse-timeout-{operation_name}")
    future = executor.submit(fn, *args, **kwargs)
    try:
        return future.result(timeout=timeout_seconds)
    except FutureTimeoutError as e:
        logger.error(
            "[%s] Timed out after %.1f seconds (target=%s)",
            operation_name, timeout_seconds, target
        )
        msg = f"{operation_name} exceeded timeout limit of {timeout_seconds}s."
        try:
            raise timeout_exception_cls(
                msg,
                target=target,
                original_exception=e
            )
        except TypeError:
            raise timeout_exception_cls(msg)
    finally:
        # Don't wait for hung worker thread to finish; let it background or terminate
        executor.shutdown(wait=False)


# =====================================================================
# 5. Persistent Error & Degradation Auditor
# =====================================================================

class ErrorAuditor:
    """
    Central thread-safe audit log for tracking errors, degraded states,
    failed URLs, and fallback actions across a research session.
    """

    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or "session_default"
        self._lock = threading.Lock()
        self._errors: List[Dict[str, Any]] = []
        self._failed_sources: List[Dict[str, Any]] = []
        self._degraded_modes: List[str] = []
        self._warnings: List[str] = []

    def record_error(
        self,
        operation: str,
        message: str,
        target: Optional[str] = None,
        error_code: str = "ERROR",
        retryable: bool = False,
        original_exception: Optional[Exception] = None,
        fallback_action: Optional[str] = None,
    ):
        with self._lock:
            record = {
                "operation": operation,
                "message": message,
                "target": target,
                "error_code": error_code,
                "retryable": retryable,
                "fallback_action": fallback_action,
                "timestamp": datetime.now().isoformat(),
            }
            self._errors.append(record)
            logger.warning(
                "Audit recorded [%s] on '%s': %s (fallback: %s)",
                operation, target or "none", message, fallback_action or "none"
            )

    def record_failed_source(
        self,
        url: str,
        reason: Optional[str] = None,
        subtask_id: str = "general",
        status_code: Optional[int] = None,
        error: Optional[str] = None,
        domain: Optional[str] = None,
    ):
        """
        Explicitly record a failed web source.
        NEVER hide failed sources from audit logs or users.
        """
        fail_reason = error or reason or "Unknown failure"
        with self._lock:
            source_rec = {
                "url": url,
                "reason": fail_reason,
                "error": fail_reason,
                "subtask_id": subtask_id,
                "status_code": status_code,
                "domain": domain or (url.split("//")[-1].split("/")[0] if url else "unknown"),
                "timestamp": datetime.now().isoformat(),
            }
            if not any(fs["url"] == url for fs in self._failed_sources):
                self._failed_sources.append(source_rec)
            logger.info("Recorded failed source [%s]: %s", url, fail_reason)

    def record_degradation(self, mode_name: str, explanation: str = ""):
        """Record when the system has entered a degraded mode."""
        with self._lock:
            if mode_name not in self._degraded_modes:
                self._degraded_modes.append(mode_name)
            if explanation:
                self._warnings.append(explanation)
            logger.warning("System degradation [%s]: %s", mode_name, explanation)

    def record_degraded_mode(self, mode_name: str, reason: str = "", session_id: Optional[str] = None):
        self.record_degradation(mode_name, reason)

    def record_warning(self, warning: str, session_id: Optional[str] = None):
        with self._lock:
            self._warnings.append(warning)

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "session_id": self.session_id,
                "error_count": len(self._errors),
                "errors": list(self._errors),
                "failed_sources_count": len(self._failed_sources),
                "failed_sources": list(self._failed_sources),
                "degraded_modes": list(self._degraded_modes),
                "warnings": list(self._warnings),
            }

    def get_session_summary(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        return self.get_summary()


_global_auditor = ErrorAuditor("global")


def get_error_auditor(session_id: Optional[str] = None) -> ErrorAuditor:
    """Return an ErrorAuditor instance."""
    if session_id:
        return ErrorAuditor(session_id)
    return _global_auditor
