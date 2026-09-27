"""
SYNAPSE AI Observability & Structured Telemetry Engine
======================================================
Provides granular, non-blocking telemetry collection across all agent executions:
- Planner Agent
- Search Agent
- Reader Agent
- Retrieval Agent
- Writer Agent
- Verification Agent

Tracks:
- run_id, session_id, agent_name, start_time, end_time, duration
- status (running, completed, failed, degraded)
- retry_count, tool_calls, search_queries
- urls_discovered, urls_extracted, evidence_chunks_created
- model_used, token_usage, errors, iteration_number
- inputs & structured outputs

Guarantees:
- Structured hierarchical telemetry tree
- Strict masking of sensitive API keys, passwords, and tokens
- Microsecond execution overhead (non-blocking in-memory recording)
"""

import re
import time
import uuid
import threading
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from contextlib import contextmanager

# =====================================================================
# 1. Secret & Sensitive Data Masking
# =====================================================================

SECRET_PATTERNS = [
    (re.compile(r'gsk_[a-zA-Z0-9_\-]{16,}', re.IGNORECASE), "gsk_***MASKED_GROQ_KEY***"),
    (re.compile(r'sk-[a-zA-Z0-9_\-]{16,}', re.IGNORECASE), "sk-***MASKED_KEY***"),
    (re.compile(r'Bearer\s+[a-zA-Z0-9_\-\.]+', re.IGNORECASE), "Bearer ***MASKED_TOKEN***"),
    (re.compile(r'eyJ[a-zA-Z0-9_\-]{10,}\.[a-zA-Z0-9_\-]{10,}\.[a-zA-Z0-9_\-]+', re.IGNORECASE), "eyJ***MASKED_JWT***"),
    (re.compile(r'(api[-_]?key|password|secret|auth[-_]?token)\s*[:=]\s*["\']?([^"\'\s]+)["\']?', re.IGNORECASE), r'\1: "***MASKED***"'),
]

SENSITIVE_KEY_NAMES = {
    "api_key", "groq_api_key", "openai_api_key", "secret", "password",
    "access_token", "auth_token", "jwt", "bearer", "authorization",
    "secret_key", "private_key", "credential", "client_secret"
}

EXEMPT_METRIC_KEYS = {
    "token_usage", "prompt_tokens", "completion_tokens", "total_tokens",
    "tokens", "tokens_used", "total_token_count"
}


def sanitize_telemetry(obj: Any) -> Any:
    """
    Recursively sanitize objects to prevent accidental leaking of API keys,
    passwords, bearer tokens, or sensitive credentials in telemetry payloads.
    """
    if obj is None:
        return None

    if isinstance(obj, str):
        cleaned = obj
        for pattern, replacement in SECRET_PATTERNS:
            cleaned = pattern.sub(replacement, cleaned)
        return cleaned

    if isinstance(obj, dict):
        cleaned_dict = {}
        for k, v in obj.items():
            k_str = str(k).lower()
            if k_str in EXEMPT_METRIC_KEYS:
                cleaned_dict[k] = sanitize_telemetry(v)
            elif (
                k_str in SENSITIVE_KEY_NAMES
                or k_str == "token"
                or any(k_str.endswith(sfx) for sfx in ("_secret", "_key", "_password", "_auth", "_token"))
            ):
                cleaned_dict[k] = "***MASKED***"
            else:
                cleaned_dict[k] = sanitize_telemetry(v)
        return cleaned_dict

    if isinstance(obj, (list, tuple, set)):
        return [sanitize_telemetry(item) for item in obj]

    return obj


# =====================================================================
# 2. Agent Telemetry Record Data Model
# =====================================================================

@dataclass
class AgentTelemetryRecord:
    """Structured execution record for a single agent run."""
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = "session_default"
    agent_name: str = "Agent"  # Planner | Search | Reader | Retrieval | Writer | Verification
    start_time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    end_time: Optional[str] = None
    duration: float = 0.0
    status: str = "running"  # running | completed | failed | degraded | skipped
    retry_count: int = 0
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    search_queries: List[str] = field(default_factory=list)
    urls_discovered: List[str] = field(default_factory=list)
    urls_extracted: List[str] = field(default_factory=list)
    evidence_chunks_created: int = 0
    model_used: Optional[str] = None
    token_usage: Optional[Dict[str, Any]] = None
    errors: List[str] = field(default_factory=list)
    iteration_number: int = 0
    input_payload: Optional[Dict[str, Any]] = None
    output_payload: Optional[Dict[str, Any]] = None
    metrics: Dict[str, Any] = field(default_factory=dict)

    # Internal wall-clock counter for microsecond-precision duration
    _t0: float = field(default_factory=time.perf_counter, repr=False)

    def finish(
        self,
        status: str = "completed",
        output_payload: Optional[Any] = None,
        error: Optional[str] = None
    ) -> "AgentTelemetryRecord":
        """Complete the agent execution record and compute duration."""
        self.end_time = datetime.now(timezone.utc).isoformat()
        self.duration = round(max(0.001, time.perf_counter() - self._t0), 3)
        self.status = status
        if output_payload is not None:
            self.output_payload = sanitize_telemetry(output_payload)
        if error:
            self.errors.append(str(error))
            if self.status not in ("degraded", "completed"):
                self.status = "failed"
        return self

    def record_tool_call(
        self,
        tool_name: str,
        arguments: Optional[Any] = None,
        result_summary: Optional[str] = None,
        duration: float = 0.0,
        error: Optional[str] = None
    ):
        """Record an individual tool execution within this agent span."""
        tc = {
            "tool_name": tool_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "arguments": sanitize_telemetry(arguments),
            "result_summary": sanitize_telemetry(result_summary),
            "duration": round(duration, 3),
            "error": sanitize_telemetry(error) if error else None,
        }
        self.tool_calls.append(tc)

    def record_search_queries(self, queries: List[str]):
        """Record search queries submitted by this agent."""
        for q in queries:
            if q and q not in self.search_queries:
                self.search_queries.append(q)

    def record_urls_discovered(self, urls: List[str]):
        """Record URLs discovered by search."""
        for u in urls:
            if u and u not in self.urls_discovered:
                self.urls_discovered.append(u)

    def record_urls_extracted(self, urls: List[str]):
        """Record URLs successfully scraped/extracted."""
        for u in urls:
            if u and u not in self.urls_extracted:
                self.urls_extracted.append(u)

    def record_evidence_chunks(self, count: int):
        """Record number of evidence chunks created/indexed."""
        self.evidence_chunks_created += count

    def record_token_usage(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: Optional[int] = None
    ):
        """Record token usage metrics if returned by LLM provider."""
        tot = total_tokens if total_tokens is not None else (prompt_tokens + completion_tokens)
        self.token_usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": tot,
        }

    def record_retry(self, reason: Optional[str] = None):
        """Increment retry count and note reason."""
        self.retry_count += 1
        if reason:
            self.errors.append(f"Retry {self.retry_count}: {reason}")

    def record_error(self, error: str):
        """Add error message."""
        if error and error not in self.errors:
            self.errors.append(str(error))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to sanitized dictionary representation."""
        data = {
            "run_id": self.run_id,
            "id": self.run_id,
            "session_id": self.session_id,
            "agent_name": self.agent_name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "status": self.status,
            "retry_count": self.retry_count,
            "tool_calls": self.tool_calls,
            "search_queries": self.search_queries,
            "urls_discovered": self.urls_discovered,
            "urls_extracted": self.urls_extracted,
            "evidence_chunks_created": self.evidence_chunks_created,
            "model_used": self.model_used,
            "token_usage": self.token_usage,
            "errors": self.errors,
            "iteration_number": self.iteration_number,
            "input_payload": self.input_payload,
            "output_payload": self.output_payload,
            "metrics": {
                **self.metrics,
                "tool_calls_count": len(self.tool_calls),
                "search_queries_count": len(self.search_queries),
                "urls_discovered_count": len(self.urls_discovered),
                "urls_extracted_count": len(self.urls_extracted),
                "evidence_chunks_created": self.evidence_chunks_created,
                "errors_count": len(self.errors),
                "retry_count": self.retry_count,
            }
        }
        return sanitize_telemetry(data)


# =====================================================================
# 3. Session Telemetry Collector
# =====================================================================

class SessionTelemetryCollector:
    """
    Thread-safe in-memory telemetry collector for a specific research session.
    Organizes agent runs into the canonical research tree:
    Research Session
     ├── Planner
     ├── Search
     ├── Reader
     ├── Retrieval
     ├── Writer
     └── Verification
    """

    CANONICAL_AGENTS = ["Planner", "Search", "Reader", "Retrieval", "Writer", "Verification"]

    def __init__(self, session_id: str, topic: str = ""):
        self.session_id = session_id
        self.topic = topic
        self.start_time = datetime.now(timezone.utc).isoformat()
        self._t0 = time.perf_counter()
        self._lock = threading.Lock()
        self._runs: List[AgentTelemetryRecord] = []

    def start_agent_run(
        self,
        agent_name: str,
        iteration_number: int = 0,
        input_payload: Optional[Any] = None,
        model_used: Optional[str] = None
    ) -> AgentTelemetryRecord:
        """Start a new agent execution telemetry record."""
        normalized_name = self._normalize_agent_name(agent_name)
        record = AgentTelemetryRecord(
            run_id=str(uuid.uuid4()),
            session_id=self.session_id,
            agent_name=normalized_name,
            iteration_number=iteration_number,
            input_payload=sanitize_telemetry(input_payload),
            model_used=model_used,
            status="running"
        )
        with self._lock:
            self._runs.append(record)
        return record

    def finish_agent_run(
        self,
        run_id_or_name: str,
        status: str = "completed",
        output_payload: Optional[Any] = None,
        error: Optional[str] = None
    ) -> Optional[AgentTelemetryRecord]:
        """Finish an agent execution record by run_id or agent_name."""
        with self._lock:
            target = None
            # Try by run_id first
            for r in reversed(self._runs):
                if r.run_id == run_id_or_name:
                    target = r
                    break
            # Try by normalized agent name
            if not target:
                norm = self._normalize_agent_name(run_id_or_name)
                for r in reversed(self._runs):
                    if r.agent_name == norm and r.status == "running":
                        target = r
                        break
            if target:
                target.finish(status=status, output_payload=output_payload, error=error)
                return target
        return None

    @contextmanager
    def span(
        self,
        agent_name: str,
        iteration_number: int = 0,
        input_payload: Optional[Any] = None,
        model_used: Optional[str] = None
    ):
        """Context manager for automatic non-blocking timing and exception capture."""
        record = self.start_agent_run(
            agent_name=agent_name,
            iteration_number=iteration_number,
            input_payload=input_payload,
            model_used=model_used
        )
        try:
            yield record
            if record.status == "running":
                record.finish(status="completed")
        except Exception as e:
            record.finish(status="failed", error=str(e))
            raise

    def get_runs(self) -> List[AgentTelemetryRecord]:
        """Return all recorded agent runs."""
        with self._lock:
            return list(self._runs)

    def get_agent_record(self, agent_name: str, iteration: Optional[int] = None) -> Optional[AgentTelemetryRecord]:
        """Retrieve most recent record for a canonical agent."""
        norm = self._normalize_agent_name(agent_name)
        with self._lock:
            for r in reversed(self._runs):
                if r.agent_name == norm:
                    if iteration is None or r.iteration_number == iteration:
                        return r
        return None

    def to_tree(self) -> Dict[str, Any]:
        """
        Produce structured hierarchical telemetry tree matching specification:
        Research Session
         ├── Planner
         ├── Search
         ├── Reader
         ├── Retrieval
         ├── Writer
         └── Verification
        """
        with self._lock:
            runs_snapshot = [r.to_dict() for r in self._runs]

        total_duration = round(max(0.001, time.perf_counter() - self._t0), 3)

        agent_groups: Dict[str, List[Dict[str, Any]]] = {
            agent: [] for agent in self.CANONICAL_AGENTS
        }

        for r in runs_snapshot:
            name = r.get("agent_name", "Unknown")
            norm = self._normalize_agent_name(name)
            if norm in agent_groups:
                agent_groups[norm].append(r)
            else:
                agent_groups.setdefault(norm, []).append(r)

        nodes = []
        overall_status = "completed"

        for agent in self.CANONICAL_AGENTS:
            agent_runs = agent_groups.get(agent, [])
            if not agent_runs:
                nodes.append({
                    "agent_name": agent,
                    "status": "idle",
                    "duration": 0.0,
                    "retries": 0,
                    "outputs": None,
                    "errors": [],
                    "model_used": None,
                    "token_usage": None,
                    "runs_count": 0,
                    "details": None,
                })
                continue

            latest = agent_runs[-1]
            total_agent_duration = round(sum(r.get("duration", 0.0) for r in agent_runs), 3)
            all_errors = []
            for r in agent_runs:
                all_errors.extend(r.get("errors", []))
            total_retries = sum(r.get("retry_count", 0) for r in agent_runs)

            agent_status = latest.get("status", "completed")
            if any(r.get("status") == "failed" for r in agent_runs):
                agent_status = "failed"
                overall_status = "failed"
            elif any(r.get("status") == "degraded" for r in agent_runs):
                agent_status = "degraded"
                if overall_status == "completed":
                    overall_status = "degraded"

            node = {
                "agent_name": agent,
                "status": agent_status,
                "duration": total_agent_duration,
                "retries": total_retries,
                "outputs": latest.get("output_payload"),
                "errors": all_errors,
                "model_used": latest.get("model_used"),
                "token_usage": latest.get("token_usage"),
                "search_queries": latest.get("search_queries", []),
                "urls_discovered": latest.get("urls_discovered", []),
                "urls_extracted": latest.get("urls_extracted", []),
                "evidence_chunks_created": latest.get("evidence_chunks_created", 0),
                "tool_calls": latest.get("tool_calls", []),
                "runs_count": len(agent_runs),
                "runs": agent_runs,
                "details": latest,
            }
            nodes.append(node)

        tree = {
            "session_id": self.session_id,
            "topic": self.topic,
            "start_time": self.start_time,
            "duration": total_duration,
            "status": overall_status,
            "tree": {
                "root": "Research Session",
                "nodes": nodes,
            },
            "agents": runs_snapshot,
            "summary": {
                "total_agents_run": len(runs_snapshot),
                "total_duration_seconds": total_duration,
                "total_retries": sum(n["retries"] for n in nodes),
                "total_errors": sum(len(n["errors"]) for n in nodes),
            }
        }
        return sanitize_telemetry(tree)

    def _normalize_agent_name(self, name: str) -> str:
        """Map raw agent names to Canonical Agent Name."""
        n = name.strip().lower()
        if "plan" in n:
            return "Planner"
        if "search" in n:
            return "Search"
        if "read" in n or "scrape" in n:
            return "Reader"
        if "retriev" in n or "index" in n or "vector" in n:
            return "Retrieval"
        if "writ" in n:
            return "Writer"
        if "verif" in n or "critic" in n:
            return "Verification"
        return name.capitalize()


# =====================================================================
# 4. Global Collector Registry
# =====================================================================

_SESSION_COLLECTORS: Dict[str, SessionTelemetryCollector] = {}
_REGISTRY_LOCK = threading.Lock()


def get_session_telemetry(session_id: str, topic: str = "") -> SessionTelemetryCollector:
    """Retrieve or create the telemetry collector for a research session."""
    with _REGISTRY_LOCK:
        if session_id not in _SESSION_COLLECTORS:
            _SESSION_COLLECTORS[session_id] = SessionTelemetryCollector(session_id, topic=topic)
        collector = _SESSION_COLLECTORS[session_id]
        if topic and not collector.topic:
            collector.topic = topic
        return collector


def clear_session_telemetry(session_id: str):
    """Remove session collector to prevent memory growth."""
    with _REGISTRY_LOCK:
        _SESSION_COLLECTORS.pop(session_id, None)
