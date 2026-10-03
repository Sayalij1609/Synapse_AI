import operator
from typing import TypedDict, List, Dict, Any, Optional, Annotated


class ResearchState(TypedDict, total=False):
    """
    Central LangGraph state passed through the research pipeline.
    Preserves all inputs, concurrent subtask outputs, aggregated evidence, and reports.
    """
    topic: str
    original_query: str
    plan: Dict[str, Any]
    plan_markdown: str
    subtasks: List[Dict[str, Any]]
    subtask_results: Annotated[List[Dict[str, Any]], operator.add]
    search_queries_used: List[str]
    search_results: str
    scraped_content: str
    session_id: str
    evidence_summary: Dict[str, Any]
    evidence_briefing: str
    retrieved_evidence: List[Dict[str, Any]]
    claims: List[Dict[str, Any]]
    sources: Dict[str, Dict[str, Any]]
    grounded_claims: List[Dict[str, Any]]
    unsupported_claims: List[Dict[str, Any]]
    citation_trace: Dict[str, Any]
    report: str
    feedback: str
    source_quality_profiles: List[Dict[str, Any]]
    verification_iteration: int
    verification_result: Dict[str, Any]
    verification_history: List[Dict[str, Any]]
    report_history: Annotated[List[Dict[str, Any]], operator.add]  # Per-cycle report snapshots
    additional_queries: List[str]
    unresolved_claims: List[Dict[str, Any]]
    errors: List[str]
    telemetry: Dict[str, Any]
    agent_runs: List[Dict[str, Any]]

