"""
Automated Test Suite for SYNAPSE AI Autonomous Research Verification Agent.

Tests:
1. Successful verification (PASS, high confidence, zero unsupported claims).
2. Unsupported claim detection (RESEARCH_REQUIRED, flags unsupported claim, generates targeted queries).
3. Conflicting sources & contradictory evidence (polar or numerical contradictions detected).
4. Missing evidence & unaddressed plan sub-questions (detects missing topics).
5. Numerical consistency (flags hallucinated figures not backed by evidence chunks).
6. Maximum iteration handling (terminates loop at MAX_RESEARCH_ITERATIONS = 3, marks unresolved claims, zero fabrication).
7. Structured output schema conformance ({status, confidence, unsupported_claims, weak_claims, contradictions, missing_topics, additional_queries, reasoning_summary}).
8. Closed-loop LangGraph routing condition (re_research vs finalize).
"""

import pytest
from typing import Dict, List

from citations import Source, EvidenceChunkRef, Claim
from state import ResearchState
from verification import (
    MAX_RESEARCH_ITERATIONS,
    VerificationResult,
    run_deterministic_verification,
    mark_unresolved_claims,
    check_1_citation_coverage,
    check_2_unsupported_claims,
    check_3_evidence_relevance,
    check_4_source_consistency,
    check_5_contradictory_evidence,
    check_6_duplicate_claims,
    check_7_missing_important_information,
    check_8_source_quality,
    check_9_source_freshness,
    check_10_numerical_consistency,
    check_11_logical_consistency,
    generate_additional_queries_deterministic,
)
from pipeline import (
    should_continue_verification,
    finalize_report_node,
    create_research_graph,
)


# -----------------------------
# Fixtures & Verified Datasets
# -----------------------------
@pytest.fixture
def verified_test_data():
    """Provides a completely verified, grounded dataset."""
    sources = {
        "src_nature_ai": Source(
            source_id="src_nature_ai",
            title="AI in Cardiology Diagnostics",
            url="https://nature.com/articles/s41586-2024-ai-cardio",
            domain="nature.com",
            publication_date="2024-03-12",
            retrieved_at="2026-09-27T00:00:00",
            source_number=1,
        ),
        "src_nih_gov": Source(
            source_id="src_nih_gov",
            title="Clinical Validation of AI Systems",
            url="https://ncbi.nlm.nih.gov/pmc/articles/PMC9928172",
            domain="ncbi.nlm.nih.gov",
            publication_date="2024-07-20",
            retrieved_at="2026-09-27T00:00:00",
            source_number=2,
        ),
    }

    chunks = {
        "chunk_1": EvidenceChunkRef(
            chunk_id="chunk_1",
            source_id="src_nature_ai",
            text="In prospective clinical evaluations across 8 centers, deep learning algorithms achieved 93.8% diagnostic accuracy in detecting atrial fibrillation.",
            similarity_score=0.89,
            url="https://nature.com/articles/s41586-2024-ai-cardio",
            title="AI in Cardiology Diagnostics",
        ),
        "chunk_2": EvidenceChunkRef(
            chunk_id="chunk_2",
            source_id="src_nih_gov",
            text="Implementation of automated screening reduced patient wait times by 42% while maintaining rigorous clinical safety standards.",
            similarity_score=0.84,
            url="https://ncbi.nlm.nih.gov/pmc/articles/PMC9928172",
            title="Clinical Validation of AI Systems",
        ),
    }

    claims = [
        Claim(
            claim_id="claim_1",
            text="Deep learning algorithms achieved 93.8% diagnostic accuracy across 8 clinical centers in detecting atrial fibrillation.",
            supporting_source_ids=["src_nature_ai"],
            evidence_chunk_ids=["chunk_1"],
            confidence=0.95,
            verification_status="grounded",
        ),
        Claim(
            claim_id="claim_2",
            text="Automated screening reduced patient wait times by 42% with verified clinical safety.",
            supporting_source_ids=["src_nih_gov"],
            evidence_chunk_ids=["chunk_2"],
            confidence=0.92,
            verification_status="grounded",
        ),
    ]

    plan = {
        "main_topic": "AI in Cardiology",
        "research_objective": "Evaluate clinical accuracy and operational efficiency of AI in cardiology.",
        "sub_questions": [
            "What is the diagnostic accuracy of AI in cardiology?",
            "How does automated screening affect patient wait times?",
        ],
    }

    report = (
        "# AI in Cardiology\n\n"
        "## Diagnostic Accuracy\n"
        "Deep learning algorithms achieved 93.8% diagnostic accuracy across 8 clinical centers in detecting atrial fibrillation. [Source 1]\n\n"
        "## Operational Efficiency\n"
        "Automated screening reduced patient wait times by 42% with verified clinical safety. [Source 2]\n"
    )

    retrieved_evidence = [
        {
            "chunk_id": "chunk_1",
            "source_id": "src_nature_ai",
            "similarity_score": 0.89,
            "text": chunks["chunk_1"].text,
        },
        {
            "chunk_id": "chunk_2",
            "source_id": "src_nih_gov",
            "similarity_score": 0.84,
            "text": chunks["chunk_2"].text,
        },
    ]

    return {
        "sources": sources,
        "chunks": chunks,
        "claims": claims,
        "plan": plan,
        "report": report,
        "retrieved_evidence": retrieved_evidence,
    }


# -----------------------------
# Test Cases
# -----------------------------
class TestResearchVerificationAgent:
    """Comprehensive test suite for the autonomous Research Verification Agent."""

    def test_1_successful_verification(self, verified_test_data):
        """
        Test 1: Successful verification.
        All 11 checks pass with verified citations, matching metrics, and full plan coverage.
        Decision must be PASS with high confidence.
        """
        data = verified_test_data
        result = run_deterministic_verification(
            claims=data["claims"],
            sources=data["sources"],
            evidence_chunks=data["chunks"],
            retrieved_evidence=data["retrieved_evidence"],
            report=data["report"],
            plan=data["plan"],
            iteration=1,
            topic="AI in Cardiology",
        )

        assert result.status == "PASS"
        assert result.confidence >= 0.70
        assert len(result.unsupported_claims) == 0
        assert len(result.contradictions) == 0
        assert len(result.missing_topics) == 0
        assert len(result.additional_queries) == 0
        assert "All 11 verification checks passed" in result.reasoning_summary
        assert result.checks["citation_coverage"].passed is True
        assert result.checks["numerical_consistency"].passed is True
        assert result.checks["missing_important_information"].passed is True

    def test_2_unsupported_claim_detection(self, verified_test_data):
        """
        Test 2: Unsupported claim detection.
        A claim references non-existent / invented source and has zero supporting evidence.
        System must autonomously flag as RESEARCH_REQUIRED and generate targeted queries.
        """
        data = verified_test_data
        corrupted_claims = list(data["claims"]) + [
            Claim(
                claim_id="claim_hallucinated",
                text="Quantum biometric scanners cured 99% of metabolic disorders in Tokyo.",
                supporting_source_ids=["invented_source_999"],
                evidence_chunk_ids=["invented_chunk_999"],
                confidence=0.8,
                verification_status="unsupported",
            )
        ]

        result = run_deterministic_verification(
            claims=corrupted_claims,
            sources=data["sources"],
            evidence_chunks=data["chunks"],
            retrieved_evidence=data["retrieved_evidence"],
            report=data["report"] + "\nQuantum biometric scanners cured 99% of metabolic disorders.",
            plan=data["plan"],
            iteration=1,
            topic="AI in Cardiology",
        )

        assert result.status == "RESEARCH_REQUIRED"
        assert len(result.unsupported_claims) > 0
        unsupported_ids = [u["claim_id"] for u in result.unsupported_claims]
        assert "claim_hallucinated" in unsupported_ids
        assert len(result.additional_queries) > 0
        # Check that query targets the unsupported claim
        assert any("quantum" in q.lower() or "metabolic" in q.lower() for q in result.additional_queries)

    def test_3_conflicting_sources_and_contradictions(self, verified_test_data):
        """
        Test 3: Conflicting sources & contradictory evidence.
        Claims assert directly opposing polarity ('grew' vs 'declined') regarding the same entity.
        System must detect contradiction and trigger research.
        """
        data = verified_test_data
        contradictory_claims = [
            Claim(
                claim_id="claim_pos",
                text="Cardiology diagnostic adoption grew rapidly by 50% across metropolitan health networks.",
                supporting_source_ids=["src_nature_ai"],
                evidence_chunk_ids=["chunk_1"],
                confidence=0.9,
            ),
            Claim(
                claim_id="claim_neg",
                text="Cardiology diagnostic adoption declined severely across metropolitan health networks.",
                supporting_source_ids=["src_nih_gov"],
                evidence_chunk_ids=["chunk_2"],
                confidence=0.9,
            ),
        ]

        result = run_deterministic_verification(
            claims=contradictory_claims,
            sources=data["sources"],
            evidence_chunks=data["chunks"],
            retrieved_evidence=data["retrieved_evidence"],
            report="Cardiology diagnostic adoption grew. Cardiology diagnostic adoption declined.",
            plan=data["plan"],
            iteration=1,
            topic="AI in Cardiology",
        )

        assert result.status == "RESEARCH_REQUIRED"
        assert len(result.contradictions) > 0
        assert result.checks["contradictory_evidence"].passed is False
        assert len(result.additional_queries) > 0

    def test_4_missing_evidence_and_topics(self, verified_test_data):
        """
        Test 4: Missing evidence / unaddressed sub-questions.
        Plan contains a critical sub-question that is never mentioned in claims or report.
        Verifier must identify missing topic and create a targeted search query.
        """
        data = verified_test_data
        plan_with_missing_question = {
            "main_topic": "AI in Cardiology",
            "research_objective": "Evaluate accuracy and ethical compliance.",
            "sub_questions": [
                "What is the diagnostic accuracy of AI in cardiology?",
                "How does automated screening affect patient wait times?",
                "What are the national ethical and regulatory compliance frameworks for patient data privacy?",  # Unaddressed
            ],
        }

        result = run_deterministic_verification(
            claims=data["claims"],
            sources=data["sources"],
            evidence_chunks=data["chunks"],
            retrieved_evidence=data["retrieved_evidence"],
            report=data["report"],
            plan=plan_with_missing_question,
            iteration=1,
            topic="AI in Cardiology",
        )

        assert result.status == "RESEARCH_REQUIRED"
        assert len(result.missing_topics) > 0
        assert any("regulatory" in t.lower() or "ethical" in t.lower() for t in result.missing_topics)
        # Targeted query generated for missing topic
        assert any("regulatory" in q.lower() or "ethical" in q.lower() for q in result.additional_queries)

    def test_5_numerical_consistency_check(self, verified_test_data):
        """
        Test 5: Numerical consistency check.
        Claim asserts a specific numerical metric (e.g. 77.5%) that is completely absent
        from the cited evidence chunk (detecting fabricated stats).
        """
        data = verified_test_data
        claim_with_fabricated_metric = Claim(
            claim_id="claim_mismatch",
            text="The hospital reduced operational overhead by 77.5% using deep learning.",
            supporting_source_ids=["src_nih_gov"],
            evidence_chunk_ids=["chunk_2"],  # chunk_2 only mentions 42%, not 77.5%
            confidence=0.9,
        )

        c10 = check_10_numerical_consistency(
            claims=[claim_with_fabricated_metric],
            evidence_chunks=data["chunks"],
        )

        assert c10.passed is False
        assert len(c10.flagged_items) == 1
        assert "77.5%" in c10.flagged_items[0]["unmatched_numbers"]

    def test_6_maximum_iteration_handling(self, verified_test_data):
        """
        Test 6: Maximum iteration handling and unresolved claim badging.
        When verification fails repeatedly and reaches MAX_RESEARCH_ITERATIONS (3):
        - `should_continue_verification` halts loop and routes to 'finalize'
        - `finalize_report_node` badges unresolved claims with warning badge
        - Report includes Verification & Evidence Audit section
        - Evidence is NEVER fabricated
        """
        data = verified_test_data

        corrupted_claims = [
            Claim(
                claim_id="claim_unresolved_x",
                text="Experimental neural nanomachine synthesized antibodies in 3 seconds.",
                supporting_source_ids=["missing_src"],
                evidence_chunk_ids=[],
                confidence=0.3,
            )
        ]

        # Iteration 1: should continue to re_research
        state_iter1: ResearchState = {
            "verification_iteration": 1,
            "verification_result": {
                "status": "RESEARCH_REQUIRED",
                "unsupported_claims": [{"claim_id": "claim_unresolved_x", "text": "Experimental neural..."}],
            },
        }
        assert should_continue_verification(state_iter1) == "re_research"

        # Iteration 2: should continue to re_research
        state_iter2: ResearchState = {
            "verification_iteration": 2,
            "verification_result": {
                "status": "RESEARCH_REQUIRED",
                "unsupported_claims": [{"claim_id": "claim_unresolved_x", "text": "Experimental neural..."}],
            },
        }
        assert should_continue_verification(state_iter2) == "re_research"

        # Iteration 3 (MAX_RESEARCH_ITERATIONS): must stop and finalize
        state_iter3: ResearchState = {
            "claims": [c.model_dump() for c in corrupted_claims],
            "report": "Initial summary.\nExperimental neural nanomachine synthesized antibodies in 3 seconds.\nConclusion.",
            "verification_iteration": MAX_RESEARCH_ITERATIONS,
            "verification_result": {
                "status": "RESEARCH_REQUIRED",
                "confidence": 0.35,
                "unsupported_claims": [
                    {
                        "claim_id": "claim_unresolved_x",
                        "text": "Experimental neural nanomachine synthesized antibodies in 3 seconds.",
                    }
                ],
                "weak_claims": [],
                "contradictions": [],
                "missing_topics": [],
                "additional_queries": ["neural nanomachine clinical trial"],
                "reasoning_summary": "Substantiating evidence could not be obtained after 3 search iterations.",
            },
        }

        # Decision MUST be finalize
        assert should_continue_verification(state_iter3) == "finalize"

        # Execute finalize_report_node
        final_state = finalize_report_node(state_iter3)

        assert len(final_state["unresolved_claims"]) == 1
        assert final_state["unresolved_claims"][0]["claim_id"] == "claim_unresolved_x"
        # Must contain explicit warning badge in report text
        assert "⚠️ **[UNRESOLVED CLAIM — Insufficient Evidence]**" in final_state["report"]
        assert "## Verification & Evidence Audit" in final_state["report"]
        assert "Could not be verified after 3 search iterations" in final_state["report"]

    def test_7_structured_output_schema(self, verified_test_data):
        """
        Test 7: Structured output schema conformance.
        Must produce exact required JSON keys:
        {status, confidence, unsupported_claims, weak_claims, contradictions, missing_topics, additional_queries, reasoning_summary}
        """
        data = verified_test_data
        result = run_deterministic_verification(
            claims=data["claims"],
            sources=data["sources"],
            evidence_chunks=data["chunks"],
            retrieved_evidence=data["retrieved_evidence"],
            report=data["report"],
            plan=data["plan"],
            iteration=1,
            topic="AI in Cardiology",
        )

        d = result.to_dict()
        required_keys = [
            "status",
            "confidence",
            "unsupported_claims",
            "weak_claims",
            "contradictions",
            "missing_topics",
            "additional_queries",
            "reasoning_summary",
        ]
        for k in required_keys:
            assert k in d, f"Missing required schema key: {k}"

        assert d["status"] in ["PASS", "RESEARCH_REQUIRED"]
        assert isinstance(d["confidence"], float)
        assert isinstance(d["unsupported_claims"], list)
        assert isinstance(d["weak_claims"], list)
        assert isinstance(d["contradictions"], list)
        assert isinstance(d["missing_topics"], list)
        assert isinstance(d["additional_queries"], list)
        assert isinstance(d["reasoning_summary"], str)

    def test_8_duplicate_claims_check(self):
        """Test duplicate / redundant claim detection."""
        claims = [
            Claim(
                claim_id="c1",
                text="The neural network achieved ninety-five percent accuracy in clinical hospital trials.",
            ),
            Claim(
                claim_id="c2",
                text="The neural network achieved ninety-five percent accuracy in clinical hospital trials.",  # Exact duplicate
            ),
        ]
        c6 = check_6_duplicate_claims(claims)
        assert c6.passed is False
        assert len(c6.flagged_items) == 1
        assert c6.flagged_items[0]["similarity"] >= 0.90

    def test_9_source_quality_and_freshness_checks(self):
        """Test source quality and freshness checks."""
        sources = {
            "s_bad": Source(
                source_id="s_bad",
                title="Unknown",
                url="",
                domain="localhost",
                retrieved_at="2026-09-27T00:00:00",
            ),
            "s_old": Source(
                source_id="s_old",
                title="Old paper",
                url="https://example.com/paper",
                domain="example.com",
                publication_date="2015-01-01",
                retrieved_at="2026-09-27T00:00:00",
            ),
        }
        q_check = check_8_source_quality(sources)
        assert q_check.passed is False
        assert any(item["source_id"] == "s_bad" for item in q_check.flagged_items)

        f_check = check_9_source_freshness(sources, current_year=2026)
        assert any(item["source_id"] == "s_old" for item in f_check.flagged_items)

    def test_10_langgraph_creation_with_verification_loop(self):
        """Verify that the compiled LangGraph StateGraph builds with all nodes and conditional edges."""
        graph = create_research_graph()
        assert graph is not None
        # Verify node names in compiled graph
        nodes = graph.nodes
        assert "planner" in nodes
        assert "execute_subtask_node" in nodes
        assert "evidence_collector" in nodes
        assert "writer" in nodes
        assert "verifier" in nodes
        assert "re_research" in nodes
        assert "finalize" in nodes
