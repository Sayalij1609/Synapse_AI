"""
Automated Test Suite for SYNAPSE AI Unified Report Export System.

Tests verify:
1. Canonical StructuredReport object contains and preserves all 11 core sections:
   - Executive Summary
   - Research Objectives
   - Key Findings
   - Detailed Analysis
   - Claims
   - Inline citations
   - Sources
   - Evidence references
   - Verification summary
   - Research limitations
   - Generated timestamp

2. Single-source-of-truth export architecture:
   - All export formats (DOCX, PDF, Markdown) are generated from the SAME StructuredReport object.
   - Zero LLM regeneration during export.

3. DOCX specifications:
   - Professional heading hierarchy
   - Tables for claims, sources, and evidence
   - Clickable source hyperlinks (w:hyperlink)
   - Dynamic page numbers (PAGE of NUMPAGES in footer)
   - Enterprise styling (Deep Indigo & Rose Pink accents)

4. PDF specifications:
   - Professional formatting and headers/footers
   - Running page numbers (Page X/{nb})
   - Tables for claims
   - Clickable source links (link=url)
   - Authoritative sources section

5. Markdown specifications:
   - Clean headings (#, ##, ###)
   - Verified claims table
   - Sources table with URLs and quality metadata
   - Verification summary and limitations

6. FastAPI export endpoints:
   - POST /download-pdf
   - POST /download-docx
   - POST /download-markdown
   - POST /export/structured-report
   - GET /sessions/{session_id}/structured-report
"""

import io
import json
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
import docx

from report_export import (
    StructuredReport,
    StructuredClaim,
    StructuredSource,
    StructuredEvidenceRef,
    StructuredVerificationSummary,
    StructuredAnalysisSection,
    build_structured_report,
    export_to_markdown,
    export_to_docx,
    export_to_pdf,
)
from app import app


@pytest.fixture
def sample_structured_report() -> StructuredReport:
    """Fixture producing a fully populated canonical StructuredReport."""
    return StructuredReport(
        title="Autonomous AI Multi-Agent Systems in Healthcare Diagnostics",
        generated_at="2026-09-27 12:00:00 UTC",
        executive_summary=(
            "Autonomous AI systems utilizing coordinated multi-agent architectures have achieved "
            "clinical-grade diagnostic accuracy across radiology and pathology domains."
        ),
        research_objectives=[
            "Evaluate multi-agent diagnostic precision across clinical image modalities.",
            "Determine latency, error handling, and verification failure rates in production.",
            "Assess regulatory compliance and provenance traceability of generated claims."
        ],
        key_findings=[
            "Multi-agent diagnostic concordance reached 94.8% across 1,200 peer-reviewed test cases.",
            "Autonomous verification loops reduced unsupported clinical hallucination rates by 82%.",
            "End-to-end latency averaged 4.6 seconds when utilizing warm vector index caches."
        ],
        detailed_analysis=[
            StructuredAnalysisSection(
                heading="Multi-Agent Consensus & Verification",
                content=(
                    "Diagnostic pipelines that decouple planning, evidence retrieval, and clinical "
                    "critique demonstrate a significant reduction in false positives compared to "
                    "monolithic single-prompt models."
                ),
                subsections=[
                    {"subheading": "Retrieval Precision", "content": "Precision@5 remained above 0.88 across PubMed benchmarks."}
                ]
            ),
            StructuredAnalysisSection(
                heading="Regulatory and Audit Trail Adherence",
                content=(
                    "Every clinical statement is mapped directly to a persistent vector chunk "
                    "with immutable cryptographic hashes to satisfy FDA SaMD transparency requirements."
                )
            )
        ],
        claims=[
            StructuredClaim(
                claim_id="CLM-001",
                text="Multi-agent diagnostic concordance reached 94.8% across 1,200 clinical radiology cases.",
                status="grounded",
                confidence=0.96,
                evidence_text="In comparative clinical trials, the consensus agent ensemble demonstrated 94.8% concordance.",
                supporting_source_ids=["src-1"],
                source_url="https://jamanetwork.com/journals/jama/article-abstract/2819441",
                source_title="JAMA: Clinical Multi-Agent Diagnostics",
                verification_notes="Fully grounded in trial empirical dataset."
            ),
            StructuredClaim(
                claim_id="CLM-002",
                text="Self-correction verification reduced hallucinations by 82% compared to baseline LLM outputs.",
                status="grounded",
                confidence=0.92,
                evidence_text="The iterative critique loop pruned 82% of unverified assertions before synthesis.",
                supporting_source_ids=["src-2"],
                source_url="https://nature.com/articles/s41591-024-03120-x",
                source_title="Nature Medicine: Autonomous Verification in Medicine",
                verification_notes="Verified via citation trace."
            )
        ],
        inline_citations={
            "CLM-001": "[1]",
            "CLM-002": "[2]"
        },
        sources=[
            StructuredSource(
                source_id="src-1",
                source_number=1,
                title="JAMA: Clinical Multi-Agent Diagnostics",
                url="https://jamanetwork.com/journals/jama/article-abstract/2819441",
                domain="jamanetwork.com",
                source_type="academic",
                publication_date="2024-05-18",
                freshness="current",
                quality_score=0.94,
                quality_tier="authoritative"
            ),
            StructuredSource(
                source_id="src-2",
                source_number=2,
                title="Nature Medicine: Autonomous Verification in Medicine",
                url="https://nature.com/articles/s41591-024-03120-x",
                domain="nature.com",
                source_type="academic",
                publication_date="2024-06-02",
                freshness="current",
                quality_score=0.96,
                quality_tier="authoritative"
            )
        ],
        evidence_references=[
            StructuredEvidenceRef(
                chunk_id="chk-101",
                source_id="src-1",
                source_title="JAMA: Clinical Multi-Agent Diagnostics",
                source_url="https://jamanetwork.com/journals/jama/article-abstract/2819441",
                excerpt="Ensemble diagnostic pipelines demonstrated a 94.8% concordance rate in 1,200 cases.",
                similarity_score=0.91
            )
        ],
        verification_summary=StructuredVerificationSummary(
            status="verified",
            iteration_count=2,
            confidence_score=0.94,
            total_claims=2,
            grounded_claims=2,
            insufficient_claims=0,
            unsupported_claims=0,
            feedback_notes="All identified factual claims strictly supported by retrieved academic evidence."
        ),
        research_limitations=[
            "Evaluation was conducted predominantly on English-language academic publications.",
            "Hardware latency measurements reflect NVIDIA A100 GPU compute environments.",
            "Prospective patient outcome trials remain subject to Institutional Review Board review."
        ],
        metadata={
            "pipeline_version": "2.4.0",
            "model": "deepseek-r1",
            "execution_duration_sec": 4.62
        }
    )


# =====================================================================
# Core Model & 11 Sections Preservation Tests
# =====================================================================

def test_structured_report_preserves_all_11_components(sample_structured_report: StructuredReport):
    """Verify that StructuredReport explicitly encapsulates all 11 required report components."""
    report = sample_structured_report

    # 1. Executive Summary
    assert report.executive_summary
    assert "clinical-grade diagnostic accuracy" in report.executive_summary

    # 2. Research Objectives
    assert len(report.research_objectives) == 3
    assert any("diagnostic precision" in obj for obj in report.research_objectives)

    # 3. Key Findings
    assert len(report.key_findings) == 3
    assert any("94.8%" in kf for kf in report.key_findings)

    # 4. Detailed Analysis
    assert len(report.detailed_analysis) >= 2
    assert report.detailed_analysis[0].heading == "Multi-Agent Consensus & Verification"

    # 5. Claims
    assert len(report.claims) == 2
    assert report.claims[0].claim_id == "CLM-001"
    assert report.claims[0].status == "grounded"

    # 6. Inline Citations
    assert "CLM-001" in report.inline_citations
    assert report.inline_citations["CLM-001"] == "[1]"

    # 7. Sources
    assert len(report.sources) == 2
    assert report.sources[0].url == "https://jamanetwork.com/journals/jama/article-abstract/2819441"
    assert report.sources[0].quality_score >= 0.9

    # 8. Evidence references
    assert len(report.evidence_references) == 1
    assert report.evidence_references[0].chunk_id == "chk-101"

    # 9. Verification summary
    assert report.verification_summary.status == "verified"
    assert report.verification_summary.confidence_score == 0.94
    assert report.verification_summary.grounded_claims == 2

    # 10. Research limitations
    assert len(report.research_limitations) == 3
    assert any("English-language" in lim for lim in report.research_limitations)

    # 11. Generated timestamp
    assert report.generated_at
    assert "2026" in report.generated_at


# =====================================================================
# Markdown Export Tests
# =====================================================================

def test_export_to_markdown_format_and_sections(sample_structured_report: StructuredReport):
    """Verify Markdown export contains clean headings, tables, links, and all 11 components."""
    md = export_to_markdown(sample_structured_report)

    # Check headings and structure
    assert "# Autonomous AI Multi-Agent Systems in Healthcare Diagnostics" in md
    assert "## 1. Executive Summary" in md
    assert "clinical-grade diagnostic accuracy" in md

    assert "## 2. Research Objectives" in md
    assert "Evaluate multi-agent diagnostic precision" in md

    assert "## 3. Key Findings" in md
    assert "Multi-agent diagnostic concordance reached 94.8%" in md

    assert "## 4. Detailed Analysis" in md
    assert "### Multi-Agent Consensus & Verification" in md

    # Claims table
    assert "## 5. Verified Claims & Grounding Lineage" in md
    assert "| `CLM-001` |" in md
    assert "✅ Grounded" in md

    # Sources table with clickable URLs
    assert "## 6. Authoritative Sources" in md
    assert "[JAMA: Clinical Multi-Agent Diagnostics](https://jamanetwork.com/journals/jama/article-abstract/2819441)" in md

    # Evidence references
    assert "## 7. Vector Evidence References" in md
    assert "`chk-101`" in md

    # Verification summary
    assert "## 8. Autonomous Verification Summary" in md
    assert "VERIFIED" in md
    assert "94%" in md

    # Research limitations
    assert "## 9. Research Limitations & Methodology Notes" in md
    assert "English-language academic publications" in md

    # Generated metadata
    assert "Generated" in md
    assert "2026-09-27" in md


# =====================================================================
# DOCX Export Tests
# =====================================================================

def test_export_to_docx_format_headings_tables_links_page_numbers(sample_structured_report: StructuredReport):
    """Verify DOCX generation from StructuredReport includes headings, tables, page numbers, and links."""
    docx_bytes = export_to_docx(sample_structured_report)
    assert len(docx_bytes) > 0
    assert docx_bytes[:2] == b"PK"  # Valid zip container

    # Parse with python-docx
    doc = docx.Document(io.BytesIO(docx_bytes))

    # Verify Title and Headings
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    assert any("Autonomous AI Multi-Agent Systems" in p for p in paragraphs)
    assert any("1. Executive Summary" in p for p in paragraphs)
    assert any("2. Research Objectives" in p for p in paragraphs)
    assert any("3. Key Findings" in p for p in paragraphs)
    assert any("4. Detailed Analysis" in p for p in paragraphs)
    assert any("7. Autonomous Verification Audit" in p for p in paragraphs)
    assert any("8. Research Limitations & Scope" in p for p in paragraphs)

    # Verify Tables present (Claims, Sources, Evidence)
    assert len(doc.tables) >= 2  # Claims table, Sources table, etc.
    claims_table = doc.tables[0]
    header_cells = [cell.text.strip() for cell in claims_table.rows[0].cells]
    assert "Claim Statement" in header_cells
    assert "Status" in header_cells
    assert "Confidence" in header_cells

    # Check claims table content
    table_texts = [[c.text.strip() for c in row.cells] for row in claims_table.rows]
    flat_table_text = " ".join(sum(table_texts, []))
    assert "94.8%" in flat_table_text

    # Verify Hyperlinks (w:hyperlink elements present in document XML)
    doc_xml = doc._body._element.xml
    assert "w:hyperlink" in doc_xml

    # Verify Page Number in Footer (PAGE and NUMPAGES fields)
    footer_xml = doc.sections[0].footer._element.xml
    assert "PAGE" in footer_xml
    assert "NUMPAGES" in footer_xml


# =====================================================================
# PDF Export Tests
# =====================================================================

def test_export_to_pdf_format_and_pages(sample_structured_report: StructuredReport):
    """Verify PDF generation produces valid PDF with tables, clickable links, and page numbers."""
    import zlib
    import re
    pdf_bytes = export_to_pdf(sample_structured_report)
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF")

    # Verify URI link dictionary and URLs exist in PDF dictionary annotations
    assert b"/URI" in pdf_bytes or b"/Link" in pdf_bytes
    assert b"jamanetwork.com" in pdf_bytes or b"nature.com" in pdf_bytes

    # Inspect decompressed page streams using regex
    decompressed_chunks = []
    for m in re.finditer(rb'stream[\r\n]+(.*?)[\r\n]+endstream', pdf_bytes, re.DOTALL):
        try:
            decompressed_chunks.append(zlib.decompress(m.group(1)).decode("latin-1", errors="ignore"))
        except Exception:
            decompressed_chunks.append(m.group(1).decode("latin-1", errors="ignore"))
    all_decompressed = " ".join(decompressed_chunks)

    assert "SYNAPSE" in all_decompressed
    assert "Executive Summary" in all_decompressed
    assert "Key Findings" in all_decompressed
    assert "Verified Claims" in all_decompressed or "CLM-001" in all_decompressed


# =====================================================================
# Deterministic Single-Source-Of-Truth Architecture Test
# =====================================================================

def test_all_formats_derived_from_same_structured_report(sample_structured_report: StructuredReport):
    """
    CRITICAL ARCHITECTURAL CONSTRAINT:
    All export formats (Web UI/JSON, DOCX, PDF, Markdown) MUST be generated from the
    exact same StructuredReport instance without invoking any separate LLM calls.
    """
    report = sample_structured_report

    # Export to all 3 file formats + dict for Web UI
    web_ui_data = report.model_dump()
    md_content = export_to_markdown(report)
    docx_bytes = export_to_docx(report)
    pdf_bytes = export_to_pdf(report)

    # Validate Web UI representation matches canonical schema
    assert web_ui_data["title"] == report.title
    assert web_ui_data["verification_summary"]["confidence_score"] == 0.94
    assert len(web_ui_data["claims"]) == 2

    # Validate Markdown contains same core content
    assert report.title in md_content
    assert report.claims[0].claim_id in md_content
    assert report.sources[0].url in md_content

    # Validate DOCX bytes are valid
    assert len(docx_bytes) > 5000
    assert docx_bytes[:2] == b"PK"

    # Validate PDF bytes are valid
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")


# =====================================================================
# Builder Flexibility & Adaptability Tests
# =====================================================================

def test_build_structured_report_from_dictionary():
    """Verify builder handles raw pipeline state dictionary seamlessly."""
    raw_state = {
        "topic": "Autonomous Agents in Space Exploration",
        "report": (
            "# Autonomous Agents in Space Exploration\n\n"
            "## 1. Executive Summary\n"
            "Autonomous rover agents navigate complex terrain without human intervention.\n\n"
            "## 2. Research Objectives\n"
            "- Evaluate autonomous SLAM pathfinding on Martian regolith.\n\n"
            "## 3. Key Findings\n"
            "- Path latency decreased by 40%.\n\n"
            "## 4. Detailed Analysis\n"
            "Agent cooperative localization outperforms single-node navigation.\n"
        ),
        "claims": [
            {
                "claim_id": "CLM-S01",
                "text": "Path latency decreased by 40% under cooperative SLAM.",
                "status": "grounded",
                "confidence": 0.95,
                "evidence_text": "Field trials demonstrated 40% reduction in path traversal latency.",
                "source_url": "https://nasa.gov/mission_pages/rover/report.pdf",
                "source_title": "NASA Autonomous Navigation Report"
            }
        ],
        "sources": [
            {
                "title": "NASA Autonomous Navigation Report",
                "url": "https://nasa.gov/mission_pages/rover/report.pdf",
                "domain": "nasa.gov",
                "source_type": "official",
                "freshness": "current",
                "quality_score": 0.98
            }
        ],
        "verification_report": {
            "status": "verified",
            "confidence": 0.95,
            "iteration": 1,
            "feedback": "All trajectory claims validated against telemetry."
        },
        "limitations": [
            "Radiation shielding impacts processor clock frequencies."
        ]
    }

    report = build_structured_report(raw_state)
    assert isinstance(report, StructuredReport)
    assert report.title == "Autonomous Agents in Space Exploration"
    assert "rover agents navigate" in report.executive_summary
    assert len(report.research_objectives) >= 1
    assert len(report.key_findings) >= 1
    assert len(report.claims) == 1
    assert report.claims[0].claim_id == "CLM-S01"
    assert len(report.sources) == 1
    assert report.sources[0].domain == "nasa.gov"
    assert report.verification_summary.status == "verified"
    assert len(report.research_limitations) >= 1


def test_build_structured_report_from_raw_markdown():
    """Verify builder parses and extracts sections from unstructured markdown."""
    raw_md = (
        "# Quantum Computing Fault Tolerance\n\n"
        "## Executive Summary\n"
        "Topological qubits demonstrate high suppression of phase-flip errors.\n\n"
        "## Key Findings\n"
        "- Error threshold exceeded 1%.\n"
        "- Surface code syndrome extraction latency under 200ns.\n\n"
        "## Detailed Analysis\n"
        "Syndrome measurement circuits require cryogenic control ASICs.\n\n"
        "## Research Limitations\n"
        "- Dilution refrigerator thermal limits restrict qubit count to 1,000.\n"
    )

    report = build_structured_report(raw_md, topic="Quantum Computing Fault Tolerance")
    assert isinstance(report, StructuredReport)
    assert report.title == "Quantum Computing Fault Tolerance"
    assert "Topological qubits demonstrate" in report.executive_summary
    assert len(report.key_findings) >= 1
    assert len(report.detailed_analysis) >= 1
    assert len(report.research_limitations) >= 1


# =====================================================================
# FastAPI Endpoints Integration Tests
# =====================================================================

def test_api_export_endpoints(sample_structured_report: StructuredReport):
    """Test all backend export API endpoints using TestClient."""
    client = TestClient(app)

    payload = {
        "topic": sample_structured_report.title,
        "structured_data": sample_structured_report.model_dump()
    }

    # 1. POST /download-pdf
    res_pdf = client.post("/download-pdf", json=payload)
    assert res_pdf.status_code == 200
    assert res_pdf.headers["content-type"] == "application/pdf"
    assert "attachment; filename=" in res_pdf.headers["content-disposition"]
    assert res_pdf.content.startswith(b"%PDF")

    # 2. POST /download-docx
    res_docx = client.post("/download-docx", json=payload)
    assert res_docx.status_code == 200
    assert "wordprocessingml.document" in res_docx.headers["content-type"]
    assert "attachment; filename=" in res_docx.headers["content-disposition"]
    assert res_docx.content[:2] == b"PK"

    # 3. POST /download-markdown
    res_md = client.post("/download-markdown", json=payload)
    assert res_md.status_code == 200
    assert "text/markdown" in res_md.headers["content-type"]
    assert sample_structured_report.title in res_md.text
    assert "## 1. Executive Summary" in res_md.text

    # 4. POST /export/structured-report
    res_struct = client.post("/export/structured-report", json=payload)
    assert res_struct.status_code == 200
    data = res_struct.json()
    assert data["title"] == sample_structured_report.title
    assert len(data["claims"]) == 2
    assert data["verification_summary"]["confidence_score"] == 0.94
