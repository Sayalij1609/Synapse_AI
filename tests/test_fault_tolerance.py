"""
SYNAPSE AI - Production-Grade Fault Tolerance Test Suite.

Automated verification of:
1. Exponential retry with maximum attempts & jitter.
2. Per-operation execution timeouts.
3. Graceful degradation modes across search, scraping, and vector store.
4. Structured error hierarchy and user-facing explanations.
5. Candidate URL failover (never allow one failed URL to abort a subtask or session).
6. Non-fabrication & transparency: failed sources are preserved, never hidden, never invented.
7. Fallback search query simplification.
8. LLM fallback model failover and deterministic grounded claim synthesis on complete outage.
9. Circuit breaker protection (service-level and domain-level).
10. Persistent error logging and audit records.
"""

import os
import time
import pytest
from unittest.mock import MagicMock, patch

from resilience import (
    SynapseBaseError,
    SearchError,
    SearchTimeoutError,
    SearchRateLimitError,
    ScrapingError,
    HttpScrapeError,
    ScrapeTimeoutError,
    MalformedContentError,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMOutputFormatError,
    LLMUnavailableError,
    EmbeddingError,
    VectorStoreError,
    DatabaseError,
    CircuitBreakerOpenError,
    CircuitBreaker,
    CircuitBreakerState,
    DomainCircuitRegistry,
    execute_with_retry,
    execute_with_timeout,
    ErrorAuditor,
    get_error_auditor,
)
from tools import search_web_resilient, scrape_url_resilient, _simplify_query
from subtask import Subtask, execute_subtask, URLRegistry
from citations import (
    Source,
    EvidenceChunkRef,
    synthesize_deterministic_grounded_claims,
    build_source_registry,
    assemble_grounded_report,
)
from agents import invoke_chain_resilient
from retrieval import EvidenceRetrievalService, SourceChunk


# ==============================================================================
# 1. Structured Error Hierarchy & User Messages
# ==============================================================================

class TestStructuredErrors:
    def test_structured_error_attributes_and_dict(self):
        err = HttpScrapeError(
            "HTTP 403 Forbidden on paywalled article",
            target="https://wsj.com/article-123",
            domain="wsj.com",
            status_code=403,
            retryable=False,
            user_message="Source blocked access due to paywall or access restriction."
        )
        assert err.code in ["HTTP_403", "HTTP_SCRAPE_ERROR"]
        assert err.status_code == 403
        assert err.domain == "wsj.com"
        assert err.retryable is False
        assert "paywall" in err.user_message.lower()

        data = err.to_dict()
        assert data["code"] in ["HTTP_403", "HTTP_SCRAPE_ERROR"]
        assert data["status_code"] == 403
        assert data["domain"] == "wsj.com"
        assert "timestamp" in data

    def test_all_custom_exceptions_inherit_from_synapse_base_error(self):
        exceptions = [
            SearchError("err"),
            SearchTimeoutError("err"),
            SearchRateLimitError("err"),
            ScrapingError("err"),
            HttpScrapeError("err"),
            ScrapeTimeoutError("err"),
            MalformedContentError("err"),
            LLMError("err"),
            LLMRateLimitError("err"),
            LLMTimeoutError("err"),
            LLMOutputFormatError("err"),
            LLMUnavailableError("err"),
            EmbeddingError("err"),
            VectorStoreError("err"),
            DatabaseError("err"),
            CircuitBreakerOpenError("err"),
        ]
        for ex in exceptions:
            assert isinstance(ex, SynapseBaseError)
            assert isinstance(ex.to_dict(), dict)
            assert len(ex.user_message) > 0


# ==============================================================================
# 2. Exponential Retry & Timeouts
# ==============================================================================

class TestRetryAndTimeouts:
    def test_retry_succeeds_on_transient_failure(self):
        attempts = 0

        def flaky_call():
            nonlocal attempts
            attempts += 1
            if attempts < 2:
                raise SearchRateLimitError("Temporary rate limit", retryable=True)
            return "search_success"

        result = execute_with_retry(
            flaky_call,
            max_retries=3,
            initial_delay=0.01,
            backoff_factor=1.5,
            operation_name="Test Flaky Search"
        )
        assert result == "search_success"
        assert attempts == 2

    def test_retry_aborts_immediately_on_non_retryable_error(self):
        attempts = 0

        def non_retryable_call():
            nonlocal attempts
            attempts += 1
            raise HttpScrapeError("404 Not Found", status_code=404, retryable=False)

        with pytest.raises(HttpScrapeError) as exc_info:
            execute_with_retry(
                non_retryable_call,
                max_retries=3,
                initial_delay=0.01,
                operation_name="Test 404"
            )
        assert attempts == 1  # Did not wastefully retry 404!
        assert exc_info.value.status_code == 404

    def test_per_operation_timeout_raises_timeout_error(self):
        def very_slow_op():
            time.sleep(1.0)
            return "finished"

        with pytest.raises(ScrapeTimeoutError):
            execute_with_timeout(
                very_slow_op,
                timeout_seconds=0.1,
                operation_name="Slow Scraper",
                timeout_exception_cls=ScrapeTimeoutError
            )

    def test_per_operation_timeout_returns_normally_on_fast_completion(self):
        def fast_op():
            return "quick_result"

        res = execute_with_timeout(
            fast_op,
            timeout_seconds=1.0,
            operation_name="Fast Op"
        )
        assert res == "quick_result"


# ==============================================================================
# 3. Circuit Breakers (Service & Domain-Level)
# ==============================================================================

class TestCircuitBreakers:
    def test_circuit_breaker_trips_to_open_after_consecutive_failures(self):
        breaker = CircuitBreaker(
            name="test_service",
            failure_threshold=3,
            recovery_timeout=0.2
        )
        assert breaker.state == CircuitBreakerState.CLOSED

        def failing_action():
            raise ValueError("Service down")

        # 3 failures trip the breaker
        for _ in range(3):
            with pytest.raises(ValueError):
                breaker.execute(failing_action)

        assert breaker.state == CircuitBreakerState.OPEN

        # Next call is rejected immediately by the open circuit breaker
        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            breaker.execute(lambda: "never_called")
        assert "test_service" in str(exc_info.value) and "OPEN" in str(exc_info.value)

        # After recovery_timeout, breaker enters HALF_OPEN
        time.sleep(0.25)
        res = breaker.execute(lambda: "recovered_success")
        assert res == "recovered_success"
        assert breaker.state == CircuitBreakerState.CLOSED

    def test_domain_circuit_registry_trips_on_dead_domain(self):
        registry = DomainCircuitRegistry(failure_threshold=2, recovery_timeout=0.2)
        domain = "broken-host.example.com"

        assert registry.can_attempt(domain) is True

        # Record 2 failures
        registry.record_failure(domain, error_message="Connection timed out")
        registry.record_failure(domain, error_message="Connection timed out")

        # Should now be blocked by domain circuit breaker
        assert registry.can_attempt(domain) is False

        # Attempting scrape directly on blocked domain raises CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError):
            registry.execute(domain, lambda: "never")


# ==============================================================================
# 4. Search Resilience & Query Simplification Fallback
# ==============================================================================

class TestSearchResilience:
    def test_simplify_query_strips_punctuation_and_operators(self):
        complex_q = 'What are the "breakthroughs" in deep learning? (2024 OR 2025) filetype:pdf site:edu'
        simple = _simplify_query(complex_q)
        assert simple != complex_q
        assert "filetype:" not in simple
        assert "site:" not in simple
        assert '"' not in simple

    @patch("tools._raw_ddgs_call")
    def test_search_web_resilient_falls_back_to_simplified_query(self, mock_ddgs):
        calls = []

        def side_effect(query, max_results):
            calls.append(query)
            if len(calls) == 1:
                # Primary query fails with exception
                raise RuntimeError("DDG backend failure on complex query")
            return [{"title": "Fallback Result", "href": "https://example.com/fallback", "body": "Verified empirical data."}]

        mock_ddgs.side_effect = side_effect

        result = search_web_resilient(
            "complex query: 'AI in healthcare' (clinical trials) site:gov",
            max_results=3
        )
        assert len(result) >= 1
        assert "Fallback Result" in result[0]["title"]
        assert len(calls) >= 2  # Primary query then simplified query attempted


# ==============================================================================
# 5. Web Scraping Resilience, Failover, & Non-Fabrication
# ==============================================================================

class TestScrapingResilienceAndFailover:
    @patch("tools.requests.get")
    def test_scrape_url_resilient_handles_403_paywall_gracefully(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_get.return_value.__enter__.return_value = mock_resp

        success, err_msg, status = scrape_url_resilient("https://paywall.example.com/article", timeout=2.0)
        assert success is False
        assert status == 403
        assert "403" in err_msg

    @patch("tools.requests.get")
    def test_scrape_url_resilient_rejects_binary_pdf_stream(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/pdf"}
        mock_get.return_value.__enter__.return_value = mock_resp

        success, err_msg, status = scrape_url_resilient("https://example.com/doc.pdf", timeout=2.0)
        assert success is False
        assert "binary" in err_msg.lower()

    @patch("subtask.search_web_resilient")
    @patch("subtask.scrape_url_resilient")
    def test_subtask_candidate_failover_when_url_1_fails(self, mock_scrape, mock_search):
        """
        Critical Requirement:
        Never allow one failed URL to terminate the research session.
        If URL 1 fails (e.g. 403 paywall), failover to candidate URL 2.
        Transparently record failed source in failed_sources.
        """
        mock_search.return_value = [
            {"title": "Source 1 (Paywalled)", "href": "https://paywall.com/article", "body": "snippet 1"},
            {"title": "Source 2 (Accessible)", "href": "https://openaccess.org/article", "body": "snippet 2"},
        ]

        def mock_scrape_side_effect(url, **kwargs):
            if "paywall" in url:
                return (False, "HTTP 403 Forbidden", 403)
            return (
                True,
                "Open Access Clinical Findings: Deep learning showed 94% sensitivity across multi-site trials. Turnaround was reduced by 30%.",
                200,
            )

        mock_scrape.side_effect = mock_scrape_side_effect

        subtask = Subtask(
            subtask_id="st_failover_test",
            question="What are the clinical diagnostic metrics?",
            search_queries=["clinical diagnostics AI"]
        )

        completed = execute_subtask(subtask, url_registry=URLRegistry())

        # Research subtask completed successfully using candidate 2!
        assert completed.status == "completed"
        assert len(completed.extracted_documents) >= 1
        assert completed.extracted_documents[0].url == "https://openaccess.org/article"

        # Transparent audit: URL 1 was NOT hidden
        assert len(completed.failed_sources) == 1
        assert completed.failed_sources[0]["url"] == "https://paywall.com/article"
        assert completed.failed_sources[0]["status_code"] == 403

    @patch("subtask.search_web_resilient")
    @patch("subtask.scrape_url_resilient")
    def test_subtask_graceful_degradation_to_search_snippets_when_all_scrapes_fail(self, mock_scrape, mock_search):
        """
        Requirement:
        If all deep page scrapes fail (e.g. strict Cloudflare block),
        research gracefully degrades to verified search snippets as evidence
        rather than crashing or returning zero sources.
        """
        mock_search.return_value = [
            {
                "title": "Global Health Metrics",
                "href": "https://who-blocked.int/report",
                "body": "Global trials confirmed a 42% decrease in diagnostics latency across 10 regions."
            }
        ]
        # All scrapes return failed tuple
        mock_scrape.return_value = (False, "HTTP 403 Forbidden", 403)

        subtask = Subtask(
            subtask_id="st_snippet_fallback",
            question="What is the global health impact?",
            search_queries=["global health AI latency"]
        )

        completed = execute_subtask(subtask, url_registry=URLRegistry())

        assert completed.status == "degraded"
        assert completed.degraded is True
        assert len(completed.extracted_documents) == 1
        assert completed.extracted_documents[0].subtask_id == "st_snippet_fallback"
        assert "[Search Snippet]" in completed.extracted_documents[0].title
        assert "42% decrease" in completed.extracted_documents[0].text
        assert len(completed.failed_sources) == 1


# ==============================================================================
# 6. LLM Fallback & Deterministic Grounded Synthesis (Zero Fabrication)
# ==============================================================================

class TestLLMFallbackAndZeroFabrication:
    def test_invoke_chain_resilient_falls_back_to_secondary_model_on_error(self):
        primary_mock = MagicMock()
        primary_mock.invoke.side_effect = LLMRateLimitError("Rate limit 429 on primary model", status_code=429)

        fallback_mock = MagicMock()
        fallback_mock.invoke.return_value = "Fallback model synthesis response"

        with patch("agents.GROQ_MODEL", "qwen-primary"):
            with patch("agents.GROQ_FALLBACK_MODEL", "llama-fallback"):
                res = invoke_chain_resilient(
                    primary_chain=primary_mock,
                    fallback_chain=fallback_mock,
                    input_dict={"prompt": "test"},
                    timeout_seconds=2.0,
                    operation_name="Resilience Test"
                )
                assert res == "Fallback model synthesis response"
                assert primary_mock.invoke.call_count >= 1
                assert fallback_mock.invoke.call_count == 1

    def test_deterministic_grounded_claims_synthesis_never_invents_sources(self):
        """
        Requirement:
        Never silently fabricate a result after a failed tool call.
        If Writer LLM is entirely unavailable, deterministic synthesis generates
        claims strictly grounded in real evidence chunks and registered sources.
        """
        sources = {
            "src_who": Source(
                source_id="src_who",
                title="WHO Guidelines on AI",
                url="https://who.int/ai-guidance",
                domain="who.int",
                publication_date="2024-03-01",
                retrieved_at="2026-09-27T00:00:00"
            )
        }
        evidence_chunks = {
            "src_who_chunk_0": EvidenceChunkRef(
                chunk_id="src_who_chunk_0",
                source_id="src_who",
                url="https://who.int/ai-guidance",
                text="The World Health Organization mandates algorithmic transparency and safety audits for clinical AI deployments.",
                similarity_score=0.9
            )
        }

        summary, claims, conclusion = synthesize_deterministic_grounded_claims(
            topic="Healthcare AI Governance",
            sources=sources,
            evidence_chunks=evidence_chunks
        )

        assert len(claims) >= 1
        claim = claims[0]
        # Grounded in real evidence
        assert claim.supporting_source_ids == ["src_who"]
        assert claim.evidence_chunk_ids == ["src_who_chunk_0"]
        assert "World Health Organization" in claim.text

        # Assembled report has valid citations and automated Sources section
        grounded_report = assemble_grounded_report(
            topic="Healthcare AI Governance",
            summary="Executive summary from verified sources.",
            claims=claims,
            conclusion="Conclusion based on empirical findings.",
            sources=sources,
            evidence_chunks=evidence_chunks
        )
        assert "https://who.int/ai-guidance" in grounded_report.markdown_report
        assert "[1]" in grounded_report.markdown_report
        assert len(grounded_report.grounded_claims) == 1
        assert len(grounded_report.unsupported_claims) == 0


# ==============================================================================
# 7. Vector Store & Lexical Fallback Retrieval
# ==============================================================================

class TestRetrievalResilience:
    def test_retrieval_service_graceful_lexical_fallback(self):
        """
        When ChromaDB or SentenceTransformer fails, the service maintains an
        in-memory lexical index and retrieves relevant evidence chunks without error.
        """
        service = EvidenceRetrievalService.__new__(EvidenceRetrievalService)
        service.persist_dir = "dummy_dir"
        service._embedder = None
        service._chroma_client = None
        service._collection = None
        service._init_failed = True
        service._init_error = "Mocked vector store uninitialized"
        service._is_degraded = True
        service._memory_chunks = {}

        # Index extracted docs in degraded memory mode
        sample_docs = [
            {
                "url": "https://clinical-ai.org/study",
                "title": "Oncology AI Study",
                "text": "Deep learning achieved 91.5% accuracy in detecting malignant melanoma lesions.",
                "subtask_id": "st_oncology"
            }
        ]

        indexed = service.index_extracted_documents(sample_docs, session_id="test_sess")
        assert len(indexed) >= 1
        assert service._is_degraded is True

        # Semantic retrieve falls back to token overlap / lexical matching
        results = service.retrieve_evidence("melanoma accuracy", session_id="test_sess", top_k=3)
        assert len(results) >= 1
        assert "91.5% accuracy" in results[0].text
        assert results[0].url == "https://clinical-ai.org/study"


# ==============================================================================
# 8. Error Auditor & Persistent Logging
# ==============================================================================

class TestErrorAuditor:
    def test_auditor_records_and_exports_failures(self):
        auditor = ErrorAuditor()

        auditor.record_failed_source(
            url="https://paywalled.com/news",
            domain="paywalled.com",
            error="403 Forbidden",
            status_code=403,
            subtask_id="st_1"
        )
        auditor.record_degraded_mode(
            mode_name="search_snippet_evidence_fallback",
            reason="All full page scrapes timed out",
            session_id="sess_123"
        )
        auditor.record_warning("Subtask 2 completed with partial evidence", session_id="sess_123")

        summary = auditor.get_session_summary("sess_123")
        assert summary["failed_sources_count"] == 1
        assert len(summary["failed_sources"]) == 1
        assert summary["failed_sources"][0]["status_code"] == 403
        assert "search_snippet_evidence_fallback" in summary["degraded_modes"]
        assert len(summary["warnings"]) == 2
        assert "Subtask 2 completed with partial evidence" in summary["warnings"]
