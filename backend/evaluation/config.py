"""
SYNAPSE AI — Evaluation Configuration
======================================
Stores evaluation settings strictly isolated from production application runtime.
Allows configuring dataset sources, retrieval cutoffs (K), evaluation modes,
and artifact output directories.
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class EvaluationConfig:
    """
    Configuration parameters for benchmark evaluation runs.
    Kept strictly isolated from production pipeline configuration.
    """
    # Path to the benchmark dataset (defaults to standard 50-query research benchmark)
    dataset_path: str = os.getenv(
        "SYNAPSE_EVAL_DATASET",
        os.path.join(os.path.dirname(__file__), "datasets", "research_benchmark_50.json")
    )

    # Retrieval evaluation parameters
    default_k: int = int(os.getenv("SYNAPSE_EVAL_K", "5"))
    k_values: List[int] = field(default_factory=lambda: [1, 3, 5, 10])
    relevance_threshold: float = float(os.getenv("SYNAPSE_EVAL_RELEVANCE_THRESHOLD", "0.30"))

    # Execution mode: "offline" (uses reference corpus with deterministic metrics)
    # or "live" (executes full live search and multi-agent pipeline)
    mode: str = os.getenv("SYNAPSE_EVAL_MODE", "offline")

    # Retrieval engine for offline mode: "lexical" (fast, lightweight) or "hybrid" (ChromaDB + embeddings)
    retrieval_engine: str = os.getenv("SYNAPSE_EVAL_ENGINE", "lexical")

    # Evaluation query limits
    max_queries: Optional[int] = None
    timeout_per_query_seconds: float = float(os.getenv("SYNAPSE_EVAL_TIMEOUT", "120.0"))

    # Output directory for machine-readable JSON and CSV evaluation reports
    output_dir: str = os.getenv(
        "SYNAPSE_EVAL_OUTPUT_DIR",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "eval_results")
    )
    save_json: bool = True
    save_markdown_summary: bool = True

    # Output verbosity
    verbose: bool = False

    def validate(self) -> None:
        """Validate configuration settings."""
        if self.default_k <= 0:
            raise ValueError(f"default_k must be positive, got {self.default_k}")
        if self.mode not in ("offline", "live"):
            raise ValueError(f"mode must be 'offline' or 'live', got '{self.mode}'")
        if self.relevance_threshold < 0.0 or self.relevance_threshold > 1.0:
            raise ValueError(f"relevance_threshold must be between 0.0 and 1.0, got {self.relevance_threshold}")
