"""
SYNAPSE AI — Evaluation Framework Test Suite
=============================================
Verifies:
1. Retrieval metric calculations (Precision@K, Recall@K, MRR)
2. Citation metric calculations (Coverage, Correctness, Traceability)
3. Generation metric calculations (Faithfulness, Relevance, Unsupported Claim Rate)
4. Dataset loading and schema validation
5. Runner offline evaluation end-to-end
6. JSON and Markdown report generation
7. Edge cases and error handling
"""

import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from evaluation.config import EvaluationConfig
from evaluation.dataset import (
    BenchmarkDataset,
    BenchmarkQuery,
    ReferencePassage,
    load_benchmark_dataset,
)
from evaluation.metrics import (
    AggregateEvaluationSummary,
    CitationMetrics,
    GenerationMetrics,
    QueryEvaluationResult,
    RetrievalMetrics,
    SystemMetrics,
    compute_answer_relevance,
    compute_citation_correctness,
    compute_citation_coverage,
    compute_faithfulness,
    compute_mrr,
    compute_precision_at_k,
    compute_recall_at_k,
    compute_source_traceability,
    compute_unsupported_claim_rate,
)
from evaluation.runner import EvaluationRunner


# =====================================================================
# Test 1: Retrieval Metrics
# =====================================================================
class TestRetrievalMetrics(unittest.TestCase):
    """Validate mathematical correctness of Precision@K, Recall@K, MRR."""

    def test_precision_at_k_perfect(self):
        """All retrieved items are relevant."""
        retrieved = ["d1", "d2", "d3"]
        relevant = {"d1", "d2", "d3"}
        self.assertEqual(compute_precision_at_k(retrieved, relevant, k=3), 1.0)

    def test_precision_at_k_partial(self):
        """2 of 5 retrieved items are relevant."""
        retrieved = ["d1", "d2", "d3", "d4", "d5"]
        relevant = {"d1", "d5"}
        self.assertEqual(compute_precision_at_k(retrieved, relevant, k=5), 0.4)

    def test_precision_at_k_empty_retrieved(self):
        """No items retrieved."""
        self.assertEqual(compute_precision_at_k([], {"d1"}, k=5), 0.0)

    def test_precision_at_k_zero_k(self):
        """K=0 should return 0."""
        self.assertEqual(compute_precision_at_k(["d1"], {"d1"}, k=0), 0.0)

    def test_recall_at_k_perfect(self):
        """All relevant items retrieved."""
        retrieved = ["d1", "d2", "d3"]
        relevant = {"d1", "d2"}
        self.assertEqual(compute_recall_at_k(retrieved, relevant, k=3), 1.0)

    def test_recall_at_k_partial(self):
        """1 of 3 relevant items retrieved in top-2."""
        retrieved = ["d1", "d4"]
        relevant = {"d1", "d2", "d3"}
        result = compute_recall_at_k(retrieved, relevant, k=2)
        self.assertAlmostEqual(result, 1 / 3, places=3)

    def test_recall_at_k_no_relevant(self):
        """No relevant items defined — edge case."""
        self.assertEqual(compute_recall_at_k([], set(), k=5), 1.0)

    def test_mrr_first_relevant(self):
        """First item is relevant → RR = 1.0."""
        self.assertEqual(compute_mrr(["d1", "d2"], {"d1"}), 1.0)

    def test_mrr_second_relevant(self):
        """Second item is relevant → RR = 0.5."""
        self.assertEqual(compute_mrr(["d3", "d1"], {"d1"}), 0.5)

    def test_mrr_none_relevant(self):
        """No relevant items found → RR = 0.0."""
        self.assertEqual(compute_mrr(["d3", "d4"], {"d1"}), 0.0)

    def test_mrr_empty(self):
        """Empty inputs → 0.0."""
        self.assertEqual(compute_mrr([], {"d1"}), 0.0)
        self.assertEqual(compute_mrr(["d1"], set()), 0.0)


# =====================================================================
# Test 2: Citation Metrics
# =====================================================================
class TestCitationMetrics(unittest.TestCase):
    """Validate Citation Coverage, Correctness, and Traceability."""

    def _make_claim(self, claim_id, text, src_ids=None, chunk_ids=None, status="grounded"):
        """Helper to create a mock Claim object."""
        from citations import Claim
        return Claim(
            claim_id=claim_id,
            text=text,
            supporting_source_ids=src_ids or [],
            evidence_chunk_ids=chunk_ids or [],
            verification_status=status,
        )

    def test_citation_coverage_all_cited(self):
        """All claims have source IDs."""
        claims = [
            self._make_claim("c1", "Test claim [Source 1]", ["s1"]),
            self._make_claim("c2", "Another claim [Source 2]", ["s2"]),
        ]
        self.assertEqual(compute_citation_coverage(claims), 1.0)

    def test_citation_coverage_none_cited(self):
        """No claims have source IDs or tags."""
        claims = [
            self._make_claim("c1", "Uncited claim"),
            self._make_claim("c2", "Another uncited claim"),
        ]
        self.assertEqual(compute_citation_coverage(claims), 0.0)

    def test_citation_coverage_partial(self):
        """1 of 2 claims cited."""
        claims = [
            self._make_claim("c1", "Cited [Source 1]", ["s1"]),
            self._make_claim("c2", "Not cited"),
        ]
        self.assertEqual(compute_citation_coverage(claims), 0.5)

    def test_citation_coverage_empty(self):
        """No claims at all."""
        self.assertEqual(compute_citation_coverage([]), 0.0)

    def test_citation_correctness_grounded(self):
        """Grounded claims with valid source IDs."""
        from citations import Claim, Source, EvidenceChunkRef
        sources = {
            "s1": Source(source_id="s1", url="https://example.com", title="Test", domain="example.com", retrieved_at="2024-01-01T00:00:00"),
        }
        chunks = {}
        claims = [
            Claim(claim_id="c1", text="Test [Source 1]", supporting_source_ids=["s1"],
                  verification_status="grounded"),
        ]
        result = compute_citation_correctness(claims, sources, chunks)
        self.assertEqual(result, 1.0)

    def test_source_traceability_with_urls(self):
        """Claims traceable to canonical URLs."""
        from citations import Claim, Source, EvidenceChunkRef
        sources = {
            "s1": Source(source_id="s1", url="https://example.com/paper", title="Paper", domain="example.com", retrieved_at="2024-01-01T00:00:00"),
        }
        chunks = {}
        claims = [
            Claim(claim_id="c1", text="Traceable [Source 1]", supporting_source_ids=["s1"]),
        ]
        result = compute_source_traceability(claims, sources, chunks)
        self.assertEqual(result, 1.0)


# =====================================================================
# Test 3: Generation Metrics
# =====================================================================
class TestGenerationMetrics(unittest.TestCase):
    """Validate Faithfulness, Answer Relevance, and Unsupported Claim Rate."""

    def _make_claim(self, status="grounded"):
        from citations import Claim
        return Claim(claim_id="c1", text="Test", verification_status=status)

    def test_faithfulness_all_grounded(self):
        claims = [self._make_claim("grounded"), self._make_claim("grounded")]
        self.assertEqual(compute_faithfulness(claims, {}, {}), 1.0)

    def test_faithfulness_mixed(self):
        claims = [self._make_claim("grounded"), self._make_claim("unsupported")]
        self.assertEqual(compute_faithfulness(claims, {}, {}), 0.5)

    def test_faithfulness_none_grounded(self):
        claims = [self._make_claim("unsupported")]
        self.assertEqual(compute_faithfulness(claims, {}, {}), 0.0)

    def test_faithfulness_empty(self):
        self.assertEqual(compute_faithfulness([], {}, {}), 0.0)

    def test_answer_relevance_all_entities_present(self):
        """All expected entities appear in the generated text."""
        score = compute_answer_relevance(
            "What is quantum computing?",
            "Quantum computing uses qubits and superposition to achieve computational advantages.",
            ["quantum", "qubits", "superposition"]
        )
        # Should be high since all entities present and query keywords overlap
        self.assertGreater(score, 0.6)

    def test_answer_relevance_no_entities(self):
        """No expected entities → falls back to query keyword match only."""
        score = compute_answer_relevance(
            "What is quantum computing?",
            "This text discusses quantum computing principles.",
            []
        )
        self.assertGreater(score, 0.5)

    def test_answer_relevance_empty_text(self):
        """Empty generated text → 0.0."""
        self.assertEqual(compute_answer_relevance("query", "", ["entity"]), 0.0)

    def test_unsupported_claim_rate_zero(self):
        claims = [self._make_claim("grounded"), self._make_claim("grounded")]
        self.assertEqual(compute_unsupported_claim_rate(claims), 0.0)

    def test_unsupported_claim_rate_half(self):
        claims = [self._make_claim("grounded"), self._make_claim("unsupported")]
        self.assertEqual(compute_unsupported_claim_rate(claims), 0.5)

    def test_unsupported_claim_rate_all(self):
        claims = [self._make_claim("unsupported")]
        self.assertEqual(compute_unsupported_claim_rate(claims), 1.0)


# =====================================================================
# Test 4: Dataset Loading
# =====================================================================
class TestDatasetLoading(unittest.TestCase):
    """Validate dataset schema, loading, and serialization."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.dataset_data = {
            "name": "Test Benchmark",
            "version": "1.0.0",
            "description": "Test dataset",
            "queries": [
                {
                    "id": "q_test_1",
                    "query": "What is machine learning?",
                    "category": "AI",
                    "expected_entities": ["machine learning", "neural networks"],
                    "expected_domains": ["arxiv.org"],
                    "ground_truth_claims": ["ML uses statistical methods"],
                    "unsupported_claims_to_test": ["ML will destroy humanity"],
                    "reference_corpus": [
                        {
                            "doc_id": "d1",
                            "url": "https://arxiv.org/abs/ml_paper",
                            "title": "ML Paper",
                            "domain": "arxiv.org",
                            "source_type": "academic",
                            "publication_date": "2024-01-15",
                            "text": "Machine learning uses statistical methods and neural networks for pattern recognition.",
                            "is_relevant": True,
                        },
                        {
                            "doc_id": "d2",
                            "url": "https://cooking.com/recipe",
                            "title": "Recipe",
                            "domain": "cooking.com",
                            "source_type": "general",
                            "publication_date": "2024-02-01",
                            "text": "Add salt and pepper to taste.",
                            "is_relevant": False,
                        },
                    ],
                }
            ],
        }

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_load_valid_dataset(self):
        """Load a well-formed dataset and validate structure."""
        path = os.path.join(self.test_dir, "test_dataset.json")
        with open(path, "w") as f:
            json.dump(self.dataset_data, f)

        dataset = load_benchmark_dataset(path)
        self.assertEqual(dataset.name, "Test Benchmark")
        self.assertEqual(len(dataset), 1)
        self.assertEqual(dataset.queries[0].id, "q_test_1")
        self.assertEqual(len(dataset.queries[0].reference_corpus), 2)
        self.assertEqual(dataset.queries[0].relevant_doc_ids, ["d1"])

    def test_load_missing_file(self):
        """Should raise FileNotFoundError for missing dataset."""
        with self.assertRaises(FileNotFoundError):
            load_benchmark_dataset(os.path.join(self.test_dir, "nonexistent.json"))

    def test_dataset_roundtrip(self):
        """Dataset serialization/deserialization preserves data."""
        path = os.path.join(self.test_dir, "roundtrip.json")
        with open(path, "w") as f:
            json.dump(self.dataset_data, f)

        dataset = load_benchmark_dataset(path)
        serialized = dataset.to_dict()
        self.assertEqual(serialized["name"], "Test Benchmark")
        self.assertEqual(serialized["total_queries"], 1)
        self.assertEqual(len(serialized["queries"]), 1)

    def test_filter_by_category(self):
        """Filter queries by category."""
        path = os.path.join(self.test_dir, "filter_test.json")
        data = dict(self.dataset_data)
        data["queries"].append({
            "id": "q_test_2",
            "query": "What is blockchain?",
            "category": "Crypto",
            "expected_entities": [],
            "expected_domains": [],
            "ground_truth_claims": [],
            "reference_corpus": [],
        })
        with open(path, "w") as f:
            json.dump(data, f)

        dataset = load_benchmark_dataset(path)
        ai_queries = dataset.filter_by_category("AI")
        self.assertEqual(len(ai_queries), 1)
        crypto_queries = dataset.filter_by_category("Crypto")
        self.assertEqual(len(crypto_queries), 1)

    def test_get_query_by_id(self):
        """Retrieve specific query by ID."""
        path = os.path.join(self.test_dir, "id_test.json")
        with open(path, "w") as f:
            json.dump(self.dataset_data, f)

        dataset = load_benchmark_dataset(path)
        q = dataset.get_query("q_test_1")
        self.assertIsNotNone(q)
        self.assertEqual(q.query, "What is machine learning?")
        self.assertIsNone(dataset.get_query("nonexistent_id"))


# =====================================================================
# Test 5: Evaluation Config
# =====================================================================
class TestEvaluationConfig(unittest.TestCase):
    """Validate configuration validation rules."""

    def test_default_config_valid(self):
        """Default config should pass validation."""
        config = EvaluationConfig()
        config.validate()  # Should not raise

    def test_invalid_k(self):
        """k <= 0 should fail validation."""
        config = EvaluationConfig(default_k=0)
        with self.assertRaises(ValueError):
            config.validate()

    def test_invalid_mode(self):
        """Invalid mode should fail validation."""
        config = EvaluationConfig(mode="invalid")
        with self.assertRaises(ValueError):
            config.validate()

    def test_invalid_relevance_threshold(self):
        """Threshold outside [0,1] should fail."""
        config = EvaluationConfig(relevance_threshold=1.5)
        with self.assertRaises(ValueError):
            config.validate()


# =====================================================================
# Test 6: Runner Offline Execution
# =====================================================================
class TestEvaluationRunner(unittest.TestCase):
    """Validate runner produces non-fabricated results from actual computation."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.output_dir = os.path.join(self.test_dir, "eval_output")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _make_mini_dataset(self) -> BenchmarkDataset:
        """Create a minimal dataset for testing."""
        return BenchmarkDataset(
            name="Mini Test Benchmark",
            version="0.1.0",
            description="Test dataset for unit tests",
            queries=[
                BenchmarkQuery(
                    id="test_q1",
                    query="What are the applications of graph neural networks?",
                    category="AI",
                    expected_entities=["graph", "neural", "networks", "GNN"],
                    expected_domains=["arxiv.org"],
                    ground_truth_claims=[
                        "Graph neural networks aggregate neighbor features through message passing layers.",
                        "GNNs have been applied to molecular property prediction, recommendation systems, and traffic forecasting.",
                    ],
                    unsupported_claims_to_test=[
                        "GNNs can predict the weather with 100% accuracy using only node degree distributions."
                    ],
                    reference_corpus=[
                        ReferencePassage(
                            doc_id="d_gnn_1",
                            url="https://arxiv.org/abs/gnn_survey",
                            title="A Survey on Graph Neural Networks",
                            domain="arxiv.org",
                            source_type="academic",
                            publication_date="2024-03-10",
                            text=(
                                "Graph neural networks (GNNs) extend deep learning to graph-structured data by aggregating "
                                "neighbor features through message passing layers. Key GNN architectures include GCN, GAT, and "
                                "GraphSAGE. These networks have been applied to molecular property prediction tasks, "
                                "recommendation systems, traffic forecasting, and social network analysis."
                            ),
                            is_relevant=True,
                        ),
                        ReferencePassage(
                            doc_id="d_gnn_2",
                            url="https://example.com/cooking",
                            title="Cooking Tips",
                            domain="example.com",
                            source_type="general",
                            publication_date="2024-01-01",
                            text="Season your pasta water with salt for better flavor.",
                            is_relevant=False,
                        ),
                    ],
                ),
            ],
        )

    def test_offline_evaluation_produces_results(self):
        """Runner produces QueryEvaluationResult from actual computation."""
        config = EvaluationConfig(
            mode="offline",
            default_k=5,
            retrieval_engine="lexical",
            output_dir=self.output_dir,
            save_json=True,
            save_markdown_summary=True,
        )
        runner = EvaluationRunner(config)
        dataset = self._make_mini_dataset()

        summary = runner.run_benchmark(dataset=dataset, max_queries=1)

        # Validate aggregate summary structure
        self.assertIsInstance(summary, AggregateEvaluationSummary)
        self.assertEqual(summary.total_queries, 1)
        self.assertEqual(summary.successful_queries, 1)
        self.assertEqual(summary.failed_queries, 0)
        self.assertEqual(summary.mode, "offline")

        # Validate retrieval metrics are computed (not zero-filled from failure)
        self.assertGreater(summary.mean_precision_at_k, 0.0)
        self.assertEqual(summary.mean_recall_at_k, 1.0)  # Only 1 relevant doc, should retrieve it

        # Validate citation metrics
        self.assertEqual(summary.citation_coverage, 1.0)  # All claims have tags

        # Validate system metrics
        self.assertGreater(summary.average_latency, 0.0)
        self.assertEqual(summary.failure_rate, 0.0)

    def test_per_query_results_are_non_fabricated(self):
        """Verify per-query results contain computed, not hardcoded values."""
        config = EvaluationConfig(
            mode="offline",
            default_k=5,
            retrieval_engine="lexical",
            output_dir=self.output_dir,
            save_json=False,
        )
        runner = EvaluationRunner(config)
        dataset = self._make_mini_dataset()

        summary = runner.run_benchmark(dataset=dataset)
        result = summary.query_results[0]

        self.assertIsInstance(result, QueryEvaluationResult)
        self.assertEqual(result.query_id, "test_q1")
        self.assertEqual(result.status, "success")
        self.assertIsNone(result.error)

        # Retrieval should find the relevant doc
        self.assertGreater(result.retrieval.precision_at_k, 0.0)
        self.assertGreater(result.retrieval.mrr, 0.0)

        # System latency should be measured, not zero
        self.assertGreater(result.system.end_to_end_latency, 0.0)

    def test_json_report_generated(self):
        """JSON machine-readable report is saved to output directory."""
        config = EvaluationConfig(
            mode="offline",
            retrieval_engine="lexical",
            output_dir=self.output_dir,
            save_json=True,
            save_markdown_summary=True,
        )
        runner = EvaluationRunner(config)
        dataset = self._make_mini_dataset()
        runner.run_benchmark(dataset=dataset)

        # Verify output directory contains JSON report
        self.assertTrue(os.path.exists(self.output_dir))
        json_files = [f for f in os.listdir(self.output_dir) if f.endswith(".json")]
        self.assertGreater(len(json_files), 0)

        # Validate JSON structure
        report_path = os.path.join(self.output_dir, json_files[0])
        with open(report_path) as f:
            report_data = json.load(f)

        self.assertIn("summary", report_data)
        self.assertIn("retrieval", report_data)
        self.assertIn("citations", report_data)
        self.assertIn("generation", report_data)
        self.assertIn("system", report_data)
        self.assertIn("queries", report_data)
        self.assertEqual(len(report_data["queries"]), 1)

    def test_markdown_summary_generated(self):
        """Markdown human-readable summary is saved."""
        config = EvaluationConfig(
            mode="offline",
            retrieval_engine="lexical",
            output_dir=self.output_dir,
            save_json=True,
            save_markdown_summary=True,
        )
        runner = EvaluationRunner(config)
        dataset = self._make_mini_dataset()
        runner.run_benchmark(dataset=dataset)

        md_files = [f for f in os.listdir(self.output_dir) if f.endswith(".md")]
        self.assertGreater(len(md_files), 0)

        md_path = os.path.join(self.output_dir, md_files[0])
        with open(md_path) as f:
            content = f.read()
        self.assertIn("SYNAPSE AI EVALUATION SUMMARY", content)
        self.assertIn("Precision@", content)
        self.assertIn("Faithfulness", content)

    def test_human_readable_format(self):
        """Human-readable summary contains all required sections."""
        summary = AggregateEvaluationSummary(
            total_queries=10,
            successful_queries=9,
            failed_queries=1,
            mode="offline",
            k=5,
            mean_precision_at_k=0.72,
            mean_recall_at_k=0.85,
            mrr=0.9,
            citation_coverage=0.95,
            citation_correctness=0.80,
            source_traceability=0.75,
            faithfulness=0.88,
            answer_relevance=0.70,
            unsupported_claim_rate=0.12,
            average_latency=1.5,
            average_search_latency=0.3,
            failure_rate=0.1,
            retry_rate=0.05,
            average_tokens_per_query=2500,
        )
        output = summary.format_human_readable()

        self.assertIn("RETRIEVAL METRICS", output)
        self.assertIn("CITATION INTEGRITY METRICS", output)
        self.assertIn("GENERATION FIDELITY METRICS", output)
        self.assertIn("SYSTEM PERFORMANCE", output)
        self.assertIn("72.0%", output)  # Precision
        self.assertIn("85.0%", output)  # Recall
        self.assertIn("10", output)  # Total queries


# =====================================================================
# Test 7: Edge Cases
# =====================================================================
class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""

    def test_empty_dataset_evaluation(self):
        """Runner handles empty dataset gracefully."""
        config = EvaluationConfig(mode="offline", retrieval_engine="lexical", save_json=False)
        runner = EvaluationRunner(config)
        dataset = BenchmarkDataset(
            name="Empty", version="1.0.0", description="Empty test", queries=[]
        )
        summary = runner.run_benchmark(dataset=dataset)
        self.assertEqual(summary.total_queries, 0)
        self.assertEqual(summary.successful_queries, 0)

    def test_to_dict_serialization(self):
        """All metric dataclasses serialize correctly."""
        ret = RetrievalMetrics(precision_at_k=0.8, recall_at_k=0.9, mrr=1.0, k=5)
        d = ret.to_dict()
        self.assertEqual(d["precision_at_k"], 0.8)
        self.assertIn("precision@5", d)

        cit = CitationMetrics(citation_coverage=0.95, citation_correctness=0.8)
        d = cit.to_dict()
        self.assertEqual(d["citation_coverage"], 0.95)

        gen = GenerationMetrics(faithfulness=0.9, answer_relevance=0.7)
        d = gen.to_dict()
        self.assertEqual(d["faithfulness"], 0.9)

        sys_m = SystemMetrics(end_to_end_latency=1.5, search_latency=0.3)
        d = sys_m.to_dict()
        self.assertEqual(d["end_to_end_latency"], 1.5)

    def test_query_evaluation_result_with_error(self):
        """Failed query result includes error message."""
        result = QueryEvaluationResult(
            query_id="err_1",
            query="Broken query",
            category="Test",
            status="failed",
            retrieval=RetrievalMetrics(k=5),
            citations=CitationMetrics(),
            generation=GenerationMetrics(),
            system=SystemMetrics(failure_rate=1.0),
            error="Connection timeout",
        )
        d = result.to_dict()
        self.assertEqual(d["status"], "failed")
        self.assertEqual(d["error"], "Connection timeout")
        self.assertEqual(d["system"]["failure_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
