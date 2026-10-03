"""
SYNAPSE AI — Comprehensive Research Evaluation Framework
=========================================================
Measures retrieval efficacy, citation accuracy, factual generation fidelity,
and system latency/reliability across standardized research benchmark datasets.
"""

from evaluation.config import EvaluationConfig
from evaluation.dataset import BenchmarkDataset, BenchmarkQuery, load_benchmark_dataset
from evaluation.metrics import (
    RetrievalMetrics,
    CitationMetrics,
    GenerationMetrics,
    SystemMetrics,
    QueryEvaluationResult,
    AggregateEvaluationSummary,
    compute_precision_at_k,
    compute_recall_at_k,
    compute_mrr,
    compute_citation_coverage,
    compute_citation_correctness,
    compute_source_traceability,
    compute_faithfulness,
    compute_answer_relevance,
    compute_unsupported_claim_rate,
)
from evaluation.runner import EvaluationRunner

__all__ = [
    "EvaluationConfig",
    "BenchmarkDataset",
    "BenchmarkQuery",
    "load_benchmark_dataset",
    "RetrievalMetrics",
    "CitationMetrics",
    "GenerationMetrics",
    "SystemMetrics",
    "QueryEvaluationResult",
    "AggregateEvaluationSummary",
    "EvaluationRunner",
    "compute_precision_at_k",
    "compute_recall_at_k",
    "compute_mrr",
    "compute_citation_coverage",
    "compute_citation_correctness",
    "compute_source_traceability",
    "compute_faithfulness",
    "compute_answer_relevance",
    "compute_unsupported_claim_rate",
]
