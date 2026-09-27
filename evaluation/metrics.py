"""
SYNAPSE AI — Evaluation Metrics Calculation Engine
===================================================
Rigorous, non-fabricated mathematical calculation of:
1. Retrieval Metrics: Precision@K, Recall@K, MRR (Mean Reciprocal Rank)
2. Citation Metrics: Citation Coverage, Citation Correctness, Source Traceability
3. Generation Metrics: Faithfulness, Answer Relevance, Unsupported Claim Rate
4. System Metrics: End-to-end Latency, Search Latency, Agent Execution Breakdown, Failure Rate, Retry Rate, Token Usage
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


# =====================================================================
# 1. Retrieval Metrics
# =====================================================================

def compute_precision_at_k(
    retrieved_items: List[str],
    relevant_identifiers: Set[str],
    k: int = 5
) -> float:
    """
    Precision@K: Fraction of top-K retrieved items that are relevant.
    Precision@K = |Retrieved[:K] ∩ Relevant| / K
    """
    if k <= 0:
        return 0.0
    if not retrieved_items:
        return 0.0

    top_k = retrieved_items[:k]
    relevant_count = sum(1 for item in top_k if item in relevant_identifiers)
    return round(relevant_count / k, 4)


def compute_recall_at_k(
    retrieved_items: List[str],
    relevant_identifiers: Set[str],
    k: int = 5
) -> float:
    """
    Recall@K: Fraction of total relevant items retrieved in top-K.
    Recall@K = |Retrieved[:K] ∩ Relevant| / |Relevant|
    """
    if not relevant_identifiers:
        return 1.0 if not retrieved_items else 0.0
    if k <= 0 or not retrieved_items:
        return 0.0

    top_k = retrieved_items[:k]
    relevant_count = sum(1 for item in top_k if item in relevant_identifiers)
    return round(relevant_count / len(relevant_identifiers), 4)


def compute_mrr(
    retrieved_items: List[str],
    relevant_identifiers: Set[str]
) -> float:
    """
    Reciprocal Rank (RR): 1 / rank of first relevant item in retrieved list.
    Returns 0.0 if no relevant items are found.
    """
    if not retrieved_items or not relevant_identifiers:
        return 0.0

    for rank, item in enumerate(retrieved_items, start=1):
        if item in relevant_identifiers:
            return round(1.0 / rank, 4)
    return 0.0


@dataclass
class RetrievalMetrics:
    precision_at_k: float = 0.0
    recall_at_k: float = 0.0
    mrr: float = 0.0
    k: int = 5
    retrieved_count: int = 0
    relevant_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "precision_at_k": self.precision_at_k,
            f"precision@{self.k}": self.precision_at_k,
            "recall_at_k": self.recall_at_k,
            f"recall@{self.k}": self.recall_at_k,
            "mrr": self.mrr,
            "k": self.k,
            "retrieved_count": self.retrieved_count,
            "relevant_count": self.relevant_count,
        }


# =====================================================================
# 2. Citation Metrics
# =====================================================================

def compute_citation_coverage(claims: List[Any]) -> float:
    """
    Citation Coverage: Fraction of claims that possess at least one citation.
    Coverage = |Claims with citations| / |Total Claims|
    """
    if not claims:
        return 0.0

    cited_count = 0
    for c in claims:
        # Support dict and Claim object
        src_ids = getattr(c, "supporting_source_ids", None)
        chunk_ids = getattr(c, "evidence_chunk_ids", None)
        text = getattr(c, "text", "")

        if isinstance(c, dict):
            src_ids = c.get("supporting_source_ids", [])
            chunk_ids = c.get("evidence_chunk_ids", [])
            text = c.get("text", "")

        has_tags = bool(re.search(r"\[(?:Source\s*)?\d+(?:,\s*\d+)*\]", text))
        if (src_ids and len(src_ids) > 0) or (chunk_ids and len(chunk_ids) > 0) or has_tags:
            cited_count += 1

    return round(cited_count / len(claims), 4)


def compute_citation_correctness(
    claims: List[Any],
    sources: Dict[str, Any],
    evidence_chunks: Dict[str, Any]
) -> float:
    """
    Citation Correctness: Fraction of cited claims that are verified and grounded
    in the registered evidence without hallucinated sources.
    Correctness = |Grounded Cited Claims| / |Total Cited Claims|
    """
    if not claims:
        return 0.0

    cited_claims = []
    grounded_count = 0

    for c in claims:
        src_ids = getattr(c, "supporting_source_ids", None) or []
        chunk_ids = getattr(c, "evidence_chunk_ids", None) or []
        status = getattr(c, "verification_status", None)
        text = getattr(c, "text", "")

        if isinstance(c, dict):
            src_ids = c.get("supporting_source_ids", [])
            chunk_ids = c.get("evidence_chunk_ids", [])
            status = c.get("verification_status", "")
            text = c.get("text", "")

        has_tags = bool(re.search(r"\[(?:Source\s*)?\d+(?:,\s*\d+)*\]", text))
        if src_ids or chunk_ids or has_tags:
            cited_claims.append(c)
            # Must be marked grounded or verified against sources
            if status == "grounded":
                # Ensure referenced sources actually exist in registry
                valid_sources = any(sid in sources for sid in src_ids) if src_ids else True
                if valid_sources:
                    grounded_count += 1

    if not cited_claims:
        return 0.0

    return round(grounded_count / len(cited_claims), 4)


def compute_source_traceability(
    claims: List[Any],
    sources: Dict[str, Any],
    evidence_chunks: Dict[str, Any]
) -> float:
    """
    Source Traceability: Fraction of cited claims where complete provenance lineage
    (Claim -> Evidence Chunk -> Source -> Canonical URL) is fully resolved.
    Traceability = |Traceable Claims| / |Total Cited Claims|
    """
    if not claims:
        return 0.0

    cited_claims = []
    traceable_count = 0

    for c in claims:
        src_ids = getattr(c, "supporting_source_ids", None) or []
        chunk_ids = getattr(c, "evidence_chunk_ids", None) or []
        text = getattr(c, "text", "")

        if isinstance(c, dict):
            src_ids = c.get("supporting_source_ids", [])
            chunk_ids = c.get("evidence_chunk_ids", [])
            text = c.get("text", "")

        has_tags = bool(re.search(r"\[(?:Source\s*)?\d+(?:,\s*\d+)*\]", text))
        if src_ids or chunk_ids or has_tags:
            cited_claims.append(c)

            # Check lineage
            has_trace = False
            for sid in src_ids:
                src_obj = sources.get(sid)
                if src_obj:
                    url = getattr(src_obj, "url", "") if not isinstance(src_obj, dict) else src_obj.get("url", "")
                    if url and url.startswith("http"):
                        has_trace = True
                        break

            if not has_trace and chunk_ids:
                for cid in chunk_ids:
                    chunk_obj = evidence_chunks.get(cid)
                    if chunk_obj:
                        url = getattr(chunk_obj, "url", "") if not isinstance(chunk_obj, dict) else chunk_obj.get("url", "")
                        if url and url.startswith("http"):
                            has_trace = True
                            break

            # If tags present, check if numbered sources exist
            if not has_trace and has_tags:
                matches = re.findall(r"\[(?:Source\s*)?(\d+)\]", text)
                for m in matches:
                    num = int(m)
                    for s in sources.values():
                        s_num = getattr(s, "source_number", None) if not isinstance(s, dict) else s.get("source_number")
                        if s_num == num:
                            s_url = getattr(s, "url", "") if not isinstance(s, dict) else s.get("url", "")
                            if s_url and s_url.startswith("http"):
                                has_trace = True
                                break

            if has_trace:
                traceable_count += 1

    if not cited_claims:
        return 0.0

    return round(traceable_count / len(cited_claims), 4)


@dataclass
class CitationMetrics:
    citation_coverage: float = 0.0
    citation_correctness: float = 0.0
    source_traceability: float = 0.0
    total_claims: int = 0
    cited_claims: int = 0
    grounded_claims: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "citation_coverage": self.citation_coverage,
            "citation_correctness": self.citation_correctness,
            "source_traceability": self.source_traceability,
            "total_claims": self.total_claims,
            "cited_claims": self.cited_claims,
            "grounded_claims": self.grounded_claims,
        }


# =====================================================================
# 3. Generation Metrics
# =====================================================================

def compute_faithfulness(
    claims: List[Any],
    sources: Dict[str, Any],
    evidence_chunks: Dict[str, Any]
) -> float:
    """
    Faithfulness: Fraction of all claims in the report that are grounded in evidence.
    Faithfulness = |Grounded Claims| / |Total Claims|
    """
    if not claims:
        return 0.0

    grounded_count = 0
    for c in claims:
        status = getattr(c, "verification_status", None)
        if isinstance(c, dict):
            status = c.get("verification_status", "")

        if status == "grounded":
            grounded_count += 1

    return round(grounded_count / len(claims), 4)


def compute_answer_relevance(
    query: str,
    generated_text: str,
    expected_entities: List[str]
) -> float:
    """
    Answer Relevance: Measures coverage of core query concepts and expected factual entities.
    Score = 0.7 * entity_coverage + 0.3 * query_keywords_overlap
    """
    if not generated_text:
        return 0.0

    gen_lower = generated_text.lower()

    # 1. Entity coverage
    if expected_entities:
        covered_entities = sum(1 for ent in expected_entities if ent.lower() in gen_lower)
        entity_score = covered_entities / len(expected_entities)
    else:
        entity_score = 1.0

    # 2. Query keywords overlap (ignoring common stop words)
    stop_words = {"what", "are", "the", "how", "does", "why", "in", "of", "and", "to", "for", "with", "is"}
    query_words = [w for w in re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", query.lower()) if w not in stop_words]

    if query_words:
        covered_query = sum(1 for w in query_words if w in gen_lower)
        query_score = covered_query / len(query_words)
    else:
        query_score = 1.0

    final_score = (0.7 * entity_score) + (0.3 * query_score)
    return round(min(1.0, max(0.0, final_score)), 4)


def compute_unsupported_claim_rate(claims: List[Any]) -> float:
    """
    Unsupported Claim Rate: Fraction of generated claims with unsupported status.
    Rate = |Unsupported Claims| / |Total Claims|
    """
    if not claims:
        return 0.0

    unsupported_count = 0
    for c in claims:
        status = getattr(c, "verification_status", None)
        if isinstance(c, dict):
            status = c.get("verification_status", "")

        if status == "unsupported":
            unsupported_count += 1

    return round(unsupported_count / len(claims), 4)


@dataclass
class GenerationMetrics:
    faithfulness: float = 0.0
    answer_relevance: float = 0.0
    unsupported_claim_rate: float = 0.0
    insufficient_claim_rate: float = 0.0
    total_claims: int = 0
    unsupported_claims: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "faithfulness": self.faithfulness,
            "answer_relevance": self.answer_relevance,
            "unsupported_claim_rate": self.unsupported_claim_rate,
            "insufficient_claim_rate": self.insufficient_claim_rate,
            "total_claims": self.total_claims,
            "unsupported_claims": self.unsupported_claims,
        }


# =====================================================================
# 4. System Metrics
# =====================================================================

@dataclass
class SystemMetrics:
    end_to_end_latency: float = 0.0
    search_latency: float = 0.0
    agent_execution_times: Dict[str, float] = field(default_factory=dict)
    failure_rate: float = 0.0
    retry_rate: float = 0.0
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "end_to_end_latency": round(self.end_to_end_latency, 3),
            "search_latency": round(self.search_latency, 3),
            "agent_execution_times": {k: round(v, 3) for k, v in self.agent_execution_times.items()},
            "failure_rate": round(self.failure_rate, 4),
            "retry_rate": round(self.retry_rate, 4),
            "total_tokens": self.total_tokens,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
        }


# =====================================================================
# 5. Composite Results per Query and Across Benchmark
# =====================================================================

@dataclass
class QueryEvaluationResult:
    """Complete evaluation result for a single query."""
    query_id: str
    query: str
    category: str
    status: str  # success | failed | partial
    retrieval: RetrievalMetrics
    citations: CitationMetrics
    generation: GenerationMetrics
    system: SystemMetrics
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_id": self.query_id,
            "query": self.query,
            "category": self.category,
            "status": self.status,
            "retrieval": self.retrieval.to_dict(),
            "citations": self.citations.to_dict(),
            "generation": self.generation.to_dict(),
            "system": self.system.to_dict(),
            "error": self.error,
        }


@dataclass
class AggregateEvaluationSummary:
    """Dataset-level aggregated evaluation summary."""
    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    mode: str = "offline"
    k: int = 5

    # Retrieval aggregates
    mean_precision_at_k: float = 0.0
    mean_recall_at_k: float = 0.0
    mrr: float = 0.0

    # Citation aggregates
    citation_coverage: float = 0.0
    citation_correctness: float = 0.0
    source_traceability: float = 0.0

    # Generation aggregates
    faithfulness: float = 0.0
    answer_relevance: float = 0.0
    unsupported_claim_rate: float = 0.0

    # System aggregates
    average_latency: float = 0.0
    average_search_latency: float = 0.0
    agent_execution_time: Dict[str, float] = field(default_factory=dict)
    failure_rate: float = 0.0
    retry_rate: float = 0.0
    average_tokens_per_query: float = 0.0

    # Per-query detailed results
    query_results: List[QueryEvaluationResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": {
                "total_queries": self.total_queries,
                "successful_queries": self.successful_queries,
                "failed_queries": self.failed_queries,
                "mode": self.mode,
                "k": self.k,
            },
            "retrieval": {
                f"precision@{self.k}": round(self.mean_precision_at_k, 4),
                f"recall@{self.k}": round(self.mean_recall_at_k, 4),
                "mrr": round(self.mrr, 4),
            },
            "citations": {
                "citation_coverage": round(self.citation_coverage, 4),
                "citation_correctness": round(self.citation_correctness, 4),
                "source_traceability": round(self.source_traceability, 4),
            },
            "generation": {
                "faithfulness": round(self.faithfulness, 4),
                "answer_relevance": round(self.answer_relevance, 4),
                "unsupported_claim_rate": round(self.unsupported_claim_rate, 4),
            },
            "system": {
                "average_latency_seconds": round(self.average_latency, 3),
                "average_search_latency_seconds": round(self.average_search_latency, 3),
                "agent_execution_time_seconds": {k: round(v, 3) for k, v in self.agent_execution_time.items()},
                "failure_rate": round(self.failure_rate, 4),
                "retry_rate": round(self.retry_rate, 4),
                "average_tokens_per_query": round(self.average_tokens_per_query, 1),
            },
            "queries": [q.to_dict() for q in self.query_results],
        }

    def format_human_readable(self) -> str:
        """Format clean, human-readable terminal summary report matching requirements."""
        lines = [
            "====================================================================",
            "                   SYNAPSE AI EVALUATION SUMMARY                     ",
            "====================================================================",
            f"Queries Evaluated:         {self.total_queries} (Success: {self.successful_queries}, Failed: {self.failed_queries})",
            f"Evaluation Mode:           {self.mode}",
            f"Retrieval Top-K:           {self.k}",
            "--------------------------------------------------------------------",
            "RETRIEVAL METRICS:",
            f"  Precision@{self.k}:             {self.mean_precision_at_k * 100:.1f}% ({self.mean_precision_at_k:.3f})",
            f"  Recall@{self.k}:                {self.mean_recall_at_k * 100:.1f}% ({self.mean_recall_at_k:.3f})",
            f"  MRR (Mean Reciprocal Rank):  {self.mrr:.3f}",
            "--------------------------------------------------------------------",
            "CITATION INTEGRITY METRICS:",
            f"  Citation Coverage:         {self.citation_coverage * 100:.1f}%",
            f"  Citation Correctness:      {self.citation_correctness * 100:.1f}%",
            f"  Source Traceability:       {self.source_traceability * 100:.1f}%",
            "--------------------------------------------------------------------",
            "GENERATION FIDELITY METRICS:",
            f"  Faithfulness (Grounded):   {self.faithfulness * 100:.1f}%",
            f"  Answer Relevance:          {self.answer_relevance * 100:.1f}%",
            f"  Unsupported Claim Rate:    {self.unsupported_claim_rate * 100:.1f}%",
            "--------------------------------------------------------------------",
            "SYSTEM PERFORMANCE & RELIABILITY:",
            f"  Average End-to-End Latency: {self.average_latency:.2f}s",
            f"  Average Search Latency:     {self.average_search_latency:.2f}s",
            "  Agent Execution Breakdown:",
        ]

        canonical_agents = ["Planner", "Search", "Reader", "Retrieval", "Writer", "Verification"]
        for agent in canonical_agents:
            dur = self.agent_execution_time.get(agent, 0.0)
            lines.append(f"    - {agent:<13}:         {dur:.2f}s")

        lines.extend([
            f"  Failure Rate:              {self.failure_rate * 100:.1f}%",
            f"  Retry Rate:                {self.retry_rate * 100:.1f}%",
            f"  Average Token Usage:       {self.average_tokens_per_query:.0f} tokens/query",
            "====================================================================",
        ])
        return "\n".join(lines)
