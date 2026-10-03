"""
Automated Test Suite for SYNAPSE AI Persistent Evidence Retrieval Layer.
Covers:
1. Indexing (chunking, metadata preservation, embeddings, vector store upsert)
2. Duplicate Prevention (identical document/URL deduplication per session)
3. Semantic Retrieval (vector search, ranking, similarity scoring, top_k)
4. Metadata Filtering (subtask_id, source metadata attributes)
5. Session Isolation (cross-session contamination prevention)
6. Graceful Failure Handling (empty content, invalid sessions, missing models)
"""

import os
import shutil
import pytest
import tempfile
from typing import List

from retrieval import (
    EvidenceRetrievalService,
    SourceChunk,
    RetrievedEvidence,
    clean_boilerplate,
    chunk_text,
    extract_domain,
    infer_source_type,
    extract_publication_date,
)


@pytest.fixture(scope="module")
def temp_chroma_service():
    """Create an isolated temporary ChromaDB directory for unit testing."""
    temp_dir = tempfile.mkdtemp(prefix="synapse_test_chroma_")
    service = EvidenceRetrievalService(persist_dir=temp_dir)
    yield service
    # Teardown
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception:
        pass


class TestDocumentCleaningAndHelpers:
    """Tests for document preprocessing, boilerplate removal, and heuristic extractors."""

    def test_clean_boilerplate(self):
        dirty = "Accept all cookies and agree to our Cookie Policy. Important research content. All rights reserved."
        cleaned = clean_boilerplate(dirty)
        assert "cookies" not in cleaned.lower()
        assert "all rights reserved" not in cleaned.lower()
        assert "Important research content" in cleaned

    def test_extract_domain(self):
        assert extract_domain("https://www.nature.com/articles/s41586-024") == "nature.com"
        assert extract_domain("http://ai.niti.gov.in/reports") == "ai.niti.gov.in"
        assert extract_domain("invalid-url") == "web"

    def test_infer_source_type(self):
        assert infer_source_type("https://niti.gov.in/strategy", "niti.gov.in") == "official"
        assert infer_source_type("https://nature.com/articles/123", "nature.com") == "academic"
        assert infer_source_type("https://reuters.com/tech/ai", "reuters.com") == "news"
        assert infer_source_type("https://mckinsey.com/insights", "mckinsey.com") == "industry"
        assert infer_source_type("https://randomblog.xyz", "randomblog.xyz") == "general"

    def test_extract_publication_date(self):
        text_iso = "Published on 2024-06-15 by the National Institute of Health."
        assert extract_publication_date(text_iso) == "2024-06-15"

        text_verbal = "Press release dated October 24, 2024 regarding machine learning."
        assert extract_publication_date(text_verbal) == "October 24, 2024"

        text_none = "No date in this small snippet."
        assert extract_publication_date(text_none) == "N/A"

    def test_chunk_text(self):
        sample = (
            "Sentence one discusses deep learning architectures and transformer attention mechanisms. "
            "Sentence two evaluates clinical diagnostic precision across multimodal imaging tasks. "
            "Sentence three explores computational scaling laws and latency optimization."
        )
        chunks = chunk_text(sample, chunk_size=120, chunk_overlap=30)
        assert len(chunks) >= 2
        for c in chunks:
            assert len(c) > 0


class TestPersistentEvidenceRetrievalLayer:
    """Comprehensive tests for the persistent vector store retrieval service."""

    SESSION_A = "test_session_alpha"
    SESSION_B = "test_session_beta"

    DOC_HEALTHCARE_AI = {
        "url": "https://aihealth.org/advances-2024",
        "title": "AI in Medical Diagnostics 2024",
        "text": (
            "Artificial intelligence in healthcare is revolutionizing clinical workflows, "
            "diagnostic radiology, and pathology assessment. Clinical evaluations demonstrate "
            "that deep convolutional neural networks achieve a 94.6% sensitivity rate in detecting "
            "early-stage diabetic retinopathy. Furthermore, automated electronic health record triaging "
            "reduces emergency department wait times by up to 35% across regional hospital networks."
        ),
        "subtask_id": "st_diagnostics",
    }

    DOC_FUSION_ENERGY = {
        "url": "https://fusionenergy.gov/progress-2024",
        "title": "Commercial Fusion Progress 2024",
        "text": (
            "Magnetically confined tokamak fusion devices achieved high beta plasma stability "
            "and sustained positive Q-energy gain for 45 consecutive seconds. Cryogenic superconducting "
            "magnets enabled magnetic field strengths exceeding 20 Tesla, marking a pivotal transition "
            "toward commercial grid power delivery."
        ),
        "subtask_id": "st_fusion",
    }

    def test_1_indexing_and_metadata_preservation(self, temp_chroma_service):
        """
        Requirement:
        - Split documents into meaningful chunks.
        - Generate embeddings.
        - Store chunks in ChromaDB.
        - Preserve complete source metadata:
          source_id, URL, title, domain, extracted text, publication date,
          retrieval timestamp, source type, subtask_id, chunk_id, embedding.
        """
        service = temp_chroma_service
        service.clear_session(self.SESSION_A)

        chunks = service.index_document(
            url=self.DOC_HEALTHCARE_AI["url"],
            title=self.DOC_HEALTHCARE_AI["title"],
            text=self.DOC_HEALTHCARE_AI["text"],
            session_id=self.SESSION_A,
            subtask_id=self.DOC_HEALTHCARE_AI["subtask_id"]
        )

        assert len(chunks) > 0, "Indexing must produce at least one chunk"
        chunk: SourceChunk = chunks[0]

        # Verify all required metadata fields
        assert chunk.chunk_id.startswith(f"{self.SESSION_A}_")
        assert chunk.source_id is not None and len(chunk.source_id) > 0
        assert chunk.session_id == self.SESSION_A
        assert chunk.subtask_id == "st_diagnostics"
        assert chunk.url == self.DOC_HEALTHCARE_AI["url"]
        assert chunk.title == self.DOC_HEALTHCARE_AI["title"]
        assert chunk.domain == "aihealth.org"
        assert chunk.source_type == "general"
        assert chunk.text is not None and len(chunk.text) > 0
        assert chunk.retrieval_timestamp is not None
        assert chunk.publication_date is not None

    def test_2_duplicate_prevention(self, temp_chroma_service):
        """
        Requirement:
        - Prevent duplicate documents within the same research session.
        """
        service = temp_chroma_service

        # Re-index the same document in the same session
        duplicate_chunks = service.index_document(
            url=self.DOC_HEALTHCARE_AI["url"],
            title=self.DOC_HEALTHCARE_AI["title"],
            text=self.DOC_HEALTHCARE_AI["text"],
            session_id=self.SESSION_A,
            subtask_id=self.DOC_HEALTHCARE_AI["subtask_id"]
        )

        assert len(duplicate_chunks) == 0, "Duplicate indexing must be rejected (returning 0 chunks)"

    def test_3_semantic_retrieval_and_configurable_top_k(self, temp_chroma_service):
        """
        Requirement:
        - Implement semantic retrieval.
        - Implement configurable top_k.
        - Return similarity scores and complete attribution.
        """
        service = temp_chroma_service

        # Query relevant to diabetic retinopathy
        results: List[RetrievedEvidence] = service.retrieve_evidence(
            query="diabetic retinopathy diagnostic neural networks",
            session_id=self.SESSION_A,
            top_k=3
        )

        assert len(results) >= 1
        assert len(results) <= 3
        top_result = results[0]
        assert "aihealth.org" in top_result.url
        assert top_result.similarity_score > 0.0
        assert "retinopathy" in top_result.text.lower()
        assert top_result.session_id == self.SESSION_A
        assert top_result.subtask_id == "st_diagnostics"

    def test_4_metadata_filtering(self, temp_chroma_service):
        """
        Requirement:
        - Filter retrieval by subtask_id and session.
        """
        service = temp_chroma_service

        # Subtask matches -> should find results
        matching_results = service.retrieve_evidence(
            query="clinical workflows",
            session_id=self.SESSION_A,
            subtask_id="st_diagnostics",
            top_k=5
        )
        assert len(matching_results) > 0
        assert all(r.subtask_id == "st_diagnostics" for r in matching_results)

        # Subtask does not match -> should return empty
        non_matching = service.retrieve_evidence(
            query="clinical workflows",
            session_id=self.SESSION_A,
            subtask_id="st_different_task",
            top_k=5
        )
        assert len(non_matching) == 0

    def test_5_session_isolation(self, temp_chroma_service):
        """
        Requirement:
        - Filter retrieval by research session.
        - Ensure evidence from one research session cannot contaminate another.
        """
        service = temp_chroma_service
        service.clear_session(self.SESSION_B)

        # Index Fusion Energy doc ONLY in Session B
        chunks_b = service.index_document(
            url=self.DOC_FUSION_ENERGY["url"],
            title=self.DOC_FUSION_ENERGY["title"],
            text=self.DOC_FUSION_ENERGY["text"],
            session_id=self.SESSION_B,
            subtask_id=self.DOC_FUSION_ENERGY["subtask_id"]
        )
        assert len(chunks_b) > 0

        # Now, query Session A for 'tokamak fusion energy'
        # Even though high-dimensional vectors for fusion exist in the vector database,
        # Session A MUST NEVER return any chunk from Session B.
        leak_results_a = service.retrieve_evidence(
            query="tokamak fusion superconductivity plasma",
            session_id=self.SESSION_A,
            top_k=5
        )
        for r in leak_results_a:
            assert r.session_id == self.SESSION_A
            assert "fusionenergy.gov" not in r.url, "CRITICAL ERROR: Cross-session leak from Session B into Session A!"

        # Query Session B for fusion -> MUST return the fusion document
        session_b_results = service.retrieve_evidence(
            query="tokamak fusion superconductivity plasma",
            session_id=self.SESSION_B,
            top_k=5
        )
        assert len(session_b_results) > 0
        assert session_b_results[0].session_id == self.SESSION_B
        assert "fusionenergy.gov" in session_b_results[0].url

        # Query Session B for healthcare -> MUST NOT find healthcare document from Session A
        leak_results_b = service.retrieve_evidence(
            query="diabetic retinopathy hospital workflows",
            session_id=self.SESSION_B,
            top_k=5
        )
        for r in leak_results_b:
            assert r.session_id == self.SESSION_B
            assert "aihealth.org" not in r.url, "CRITICAL ERROR: Cross-session leak from Session A into Session B!"

    def test_6_evidence_briefing_formatting(self, temp_chroma_service):
        """
        Requirement:
        - Writer receives structured, attributed evidence rather than raw messy HTML.
        """
        service = temp_chroma_service
        results = service.retrieve_evidence(
            query="radiology clinical workflows",
            session_id=self.SESSION_A,
            top_k=2
        )
        briefing = service.format_evidence_briefing(results)
        assert "### [EVIDENCE CHUNK 1]" in briefing
        assert "Source URL:" in briefing
        assert "Domain & Type:" in briefing
        assert "Verified Content Excerpt:" in briefing

    def test_7_graceful_failures(self, temp_chroma_service):
        """
        Requirement:
        - Handle embedding and ChromaDB failures gracefully.
        """
        service = temp_chroma_service

        # Empty query
        assert service.retrieve_evidence("", session_id=self.SESSION_A) == []

        # Empty session
        assert service.retrieve_evidence("test", session_id="") == []

        # Empty document text
        assert service.index_document("https://example.com", "Test", "", session_id=self.SESSION_A) == []

        # Empty URL
        assert service.index_document("", "Test", "Content", session_id=self.SESSION_A) == []


if __name__ == "__main__":
    pytest.main(["-v", __file__])
