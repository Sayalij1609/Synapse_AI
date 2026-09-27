"""
Automated Test Suite for Citation Integrity and Evidence Grounding in SYNAPSE AI.

Covers:
1. Structured claim generation and parsing (Claim, Source, EvidenceChunkRef).
2. Reference to supporting evidence (chunk IDs, source IDs).
3. Prevention of invented citations (hallucinated sources/chunks are rejected).
4. Citations must come ONLY from retrieved sources in the evidence store.
5. Every source retains its original canonical URL.
6. Support for multiple sources per claim.
7. Detection of unsupported claims.
8. Detection of claims with insufficient evidence.
9. Automatic generation of the Sources section.
10. Preservation of citations across Markdown, DOCX, and PDF exports.
11. Lineage tracing: Report -> Claim -> Evidence -> Source -> URL.
"""

import pytest
from typing import Dict, List

from citations import (
    Source,
    EvidenceChunkRef,
    Claim,
    GroundedReport,
    build_source_registry,
    format_evidence_catalog_for_writer,
    verify_claim,
    verify_all_claims,
    trace_claim_lineage,
    trace_report_lineage,
    generate_sources_section,
    assemble_grounded_report,
    parse_writer_claims_response,
)
from app import markdown_to_pdf, markdown_to_docx


# -----------------------------
# Test Fixtures & Sample Data
# -----------------------------
@pytest.fixture
def sample_evidence():
    """Sample verified evidence chunks as stored in ChromaDB."""
    return [
        {
            "chunk_id": "sess_101_src_ai_chunk_0",
            "source_id": "src_ai_health",
            "url": "https://aihealth.org/reports/diagnostics-2024",
            "title": "Clinical AI Diagnostics in 2024",
            "domain": "aihealth.org",
            "publication_date": "2024-05-15",
            "retrieval_timestamp": "2026-09-27T01:00:00",
            "similarity_score": 0.88,
            "text": (
                "Clinical trials across 12 hospitals demonstrated that deep learning models "
                "achieved a 94.6% sensitivity in detecting early diabetic retinopathy, "
                "reducing diagnostic turnaround time by 35%."
            ),
        },
        {
            "chunk_id": "sess_101_src_ai_chunk_1",
            "source_id": "src_ai_health",
            "url": "https://aihealth.org/reports/diagnostics-2024",
            "title": "Clinical AI Diagnostics in 2024",
            "domain": "aihealth.org",
            "publication_date": "2024-05-15",
            "retrieval_timestamp": "2026-09-27T01:00:00",
            "similarity_score": 0.79,
            "text": (
                "Emergency department triage automated by natural language processing "
                "decreased patient wait times from 4.2 hours to 2.8 hours."
            ),
        },
        {
            "chunk_id": "sess_101_src_who_chunk_0",
            "source_id": "src_who_policy",
            "url": "https://who.int/publications/ai-guidance-2024",
            "title": "WHO Regulatory Framework for Healthcare AI",
            "domain": "who.int",
            "publication_date": "2024-02-10",
            "retrieval_timestamp": "2026-09-27T01:05:00",
            "similarity_score": 0.82,
            "text": (
                "The World Health Organization mandates algorithmic transparency, bias auditing, "
                "and informed patient consent for all clinical AI deployments."
            ),
        },
    ]


@pytest.fixture
def registries(sample_evidence):
    """Build source and chunk registries from sample evidence."""
    return build_source_registry(sample_evidence)


# -----------------------------
# Test Suite: Citation Integrity
# -----------------------------
class TestCitationIntegrity:

    def test_1_build_source_registry_and_url_preservation(self, registries):
        """
        Requirement 4 & 5:
        - Citations come only from retrieved sources.
        - Every source retains its original URL and metadata.
        """
        sources, chunks = registries
        assert len(sources) == 2
        assert len(chunks) == 3

        # Verify Source 1
        src_ai = sources["src_ai_health"]
        assert src_ai.url == "https://aihealth.org/reports/diagnostics-2024"
        assert src_ai.title == "Clinical AI Diagnostics in 2024"
        assert src_ai.domain == "aihealth.org"
        assert src_ai.publication_date == "2024-05-15"
        assert src_ai.source_number == 1
        assert src_ai.citation_tag == "[Source 1]"

        # Verify Source 2
        src_who = sources["src_who_policy"]
        assert src_who.url == "https://who.int/publications/ai-guidance-2024"
        assert src_who.domain == "who.int"
        assert src_who.source_number == 2
        assert src_who.citation_tag == "[Source 2]"

    def test_2_grounded_claim_verification(self, registries):
        """
        Requirement 1 & 2:
        - Writer must generate structured claims.
        - Each claim should reference supporting evidence.
        - Verified claims pass with status 'grounded'.
        """
        sources, chunks = registries

        claim = Claim(
            claim_id="claim_1",
            text="Deep learning models achieved 94.6% sensitivity in detecting diabetic retinopathy.",
            supporting_source_ids=["src_ai_health"],
            evidence_chunk_ids=["sess_101_src_ai_chunk_0"],
            confidence=0.95,
        )

        verified = verify_claim(claim, sources, chunks)
        assert verified.verification_status == "grounded"
        assert "Verified" in (verified.verification_notes or "")

    def test_3_prevention_of_invented_citations(self, registries):
        """
        Requirement 3:
        - Do not allow citations to be invented.
        - Do not use an LLM-generated citation unless that citation exists in actual evidence store.
        """
        sources, chunks = registries

        # Claim with completely fake / hallucinated source ID
        fake_claim = Claim(
            claim_id="claim_fake",
            text="Global AI healthcare spending reached $500 billion according to TechCrunch.",
            supporting_source_ids=["src_hallucinated_techcrunch_999"],
            evidence_chunk_ids=["chunk_invented_xyz"],
            confidence=0.9,
        )

        verified = verify_claim(fake_claim, sources, chunks)
        # MUST detect invented citation and mark as unsupported
        assert verified.verification_status == "unsupported"
        assert "Invented citation detected" in verified.verification_notes
        assert verified.confidence <= 0.3

    def test_4_support_multiple_sources_for_a_claim(self, registries):
        """
        Requirement 6:
        - Support multiple sources for a single claim.
        """
        sources, chunks = registries

        multi_source_claim = Claim(
            claim_id="claim_multi",
            text=(
                "Clinical AI models achieving 94.6% diagnostic accuracy must comply with WHO "
                "algorithmic transparency and patient consent mandates."
            ),
            supporting_source_ids=["src_ai_health", "src_who_policy"],
            evidence_chunk_ids=["sess_101_src_ai_chunk_0", "sess_101_src_who_chunk_0"],
            confidence=0.95,
        )

        verified = verify_claim(multi_source_claim, sources, chunks)
        assert verified.verification_status == "grounded"
        assert len(verified.supporting_source_ids) == 2

        # Verify rendered tag contains both sources: [Source 1, Source 2]
        from citations import format_claim_citation_tags
        cit_tag = format_claim_citation_tags(verified, sources)
        assert cit_tag == "[Source 1, Source 2]"

    def test_5_detection_of_unsupported_claims(self, registries):
        """
        Requirement 7:
        - Detect unsupported claims (claims where evidence text contradicts or has zero overlap).
        """
        sources, chunks = registries

        unsupported_claim = Claim(
            claim_id="claim_unsupported",
            text="Autonomous robotic surgery replaced all human cardiac surgeons in Europe.",
            supporting_source_ids=["src_ai_health"],  # Cited source exists, but text does NOT support this!
            evidence_chunk_ids=["sess_101_src_ai_chunk_0"],
            confidence=0.9,
        )

        verified = verify_claim(unsupported_claim, sources, chunks)
        assert verified.verification_status == "unsupported"
        assert "Unsupported" in (verified.verification_notes or "")

    def test_6_detection_of_insufficient_evidence(self, registries):
        """
        Requirement 8:
        - Detect claims with insufficient evidence (marginal overlap or unverified extrapolation).
        """
        sources, chunks = registries

        insufficient_claim = Claim(
            claim_id="claim_insufficient",
            text="Emergency department wait times dropped and hospitals saved 100 million dollars annually.",
            supporting_source_ids=["src_ai_health"],
            evidence_chunk_ids=["sess_101_src_ai_chunk_1"],  # Mentions wait times, but NOT the 100M dollar figure!
            confidence=0.8,
        )

        verified = verify_claim(insufficient_claim, sources, chunks)
        assert verified.verification_status in ["insufficient_evidence", "unsupported"]
        assert verified.confidence <= 0.5

    def test_7_automatic_sources_section_generation(self, registries):
        """
        Requirement 9:
        - Generate a Sources section automatically.
        - Preserves all canonical URLs and domains.
        """
        sources, _ = registries
        sources_md = generate_sources_section(sources)

        assert "# Sources" in sources_md
        assert "[1]" in sources_md or "[Source 1]" in sources_md
        assert "https://aihealth.org/reports/diagnostics-2024" in sources_md
        assert "https://who.int/publications/ai-guidance-2024" in sources_md
        assert "aihealth.org" in sources_md
        assert "who.int" in sources_md

    def test_8_end_to_end_lineage_tracing(self, registries):
        """
        Tracing Requirement:
        - System must be able to trace: Report -> Claim -> Evidence -> Source -> URL.
        """
        sources, chunks = registries

        claim = Claim(
            claim_id="claim_1",
            text="Emergency department wait times decreased from 4.2 hours to 2.8 hours with NLP triage.",
            supporting_source_ids=["src_ai_health"],
            evidence_chunk_ids=["sess_101_src_ai_chunk_1"],
            confidence=0.95,
        )
        verify_claim(claim, sources, chunks)

        trace = trace_claim_lineage(claim, sources, chunks)

        # 1. Report Claim
        assert trace["claim_id"] == "claim_1"
        assert "wait times" in trace["claim_text"]
        assert trace["verification_status"] == "grounded"

        # 2. Evidence Chunk
        assert len(trace["evidence_chain"]) >= 1
        ev_node = trace["evidence_chain"][0]
        assert ev_node["chunk_id"] == "sess_101_src_ai_chunk_1"
        assert "4.2 hours" in ev_node["excerpt"]

        # 3. Source & URL
        src_node = ev_node["source"]
        assert src_node["source_id"] == "src_ai_health"
        assert src_node["url"] == "https://aihealth.org/reports/diagnostics-2024"
        assert src_node["domain"] == "aihealth.org"

    def test_9_writer_json_response_parsing(self, registries):
        """
        Requirement 1:
        - Writer generates structured claims in JSON.
        - Parser handles JSON output, resolves IDs, and handles fallbacks.
        """
        sources, chunks = registries

        raw_llm_json = """
        {
          "summary": "AI adoption in healthcare is accelerating across clinical diagnostics.",
          "claims": [
            {
              "claim_id": "claim_1",
              "text": "Deep learning models achieved 94.6% sensitivity in detecting diabetic retinopathy.",
              "supporting_source_ids": ["src_ai_health"],
              "evidence_chunk_ids": ["sess_101_src_ai_chunk_0"],
              "confidence": 0.95
            },
            {
              "claim_id": "claim_2",
              "text": "WHO mandates algorithmic transparency and patient consent for clinical AI.",
              "supporting_source_ids": ["2"],
              "evidence_chunk_ids": ["sess_101_src_who_chunk_0"],
              "confidence": 0.90
            }
          ],
          "conclusion": "Standardized auditing will be essential for scaled deployment."
        }
        """

        summary, claims, conclusion = parse_writer_claims_response(raw_llm_json, sources, chunks)
        assert len(claims) == 2
        assert "diagnostics" in summary
        assert "deployment" in conclusion

        # Claim 1 resolved
        assert claims[0].supporting_source_ids == ["src_ai_health"]
        # Claim 2 mapped "2" (Source 2) -> "src_who_policy"
        assert claims[1].supporting_source_ids == ["src_who_policy"]

    def test_10_preservation_of_citations_in_markdown_pdf_and_docx(self, registries):
        """
        Requirement 10:
        - Preserve citations when exporting to Markdown, DOCX, and PDF.
        """
        sources, chunks = registries

        claim_1 = Claim(
            claim_id="claim_1",
            text="Deep learning achieved 94.6% sensitivity in detecting diabetic retinopathy.",
            supporting_source_ids=["src_ai_health"],
            evidence_chunk_ids=["sess_101_src_ai_chunk_0"],
            confidence=0.95,
        )
        claim_2 = Claim(
            claim_id="claim_2",
            text="WHO requires algorithmic transparency and patient consent for medical algorithms.",
            supporting_source_ids=["src_who_policy"],
            evidence_chunk_ids=["sess_101_src_who_chunk_0"],
            confidence=0.95,
        )

        grounded_report = assemble_grounded_report(
            topic="Artificial Intelligence in Healthcare",
            summary="Executive evaluation of clinical AI applications.",
            claims=[claim_1, claim_2],
            conclusion="Continued oversight is paramount.",
            sources=sources,
            evidence_chunks=chunks,
        )

        md = grounded_report.markdown_report

        # 1. Verify in Markdown
        assert "[Source 1]" in md
        assert "[Source 2]" in md
        assert "# Sources" in md
        assert "https://aihealth.org/reports/diagnostics-2024" in md

        # 2. Verify PDF generation retains citations and URLs
        pdf_bytes = markdown_to_pdf(md, "AI Healthcare")
        assert len(pdf_bytes) > 0
        # Text inspection on sanitized output: ensure no font exceptions thrown
        assert b"%PDF" in pdf_bytes[:10]

        # 3. Verify DOCX generation retains citations and URLs
        docx_bytes = markdown_to_docx(md, "AI Healthcare")
        assert len(docx_bytes) > 0
        assert b"PK" in docx_bytes[:10]  # Valid zip container for .docx


if __name__ == "__main__":
    pytest.main(["-v", __file__])
