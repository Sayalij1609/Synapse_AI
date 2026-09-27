"""
Tests for SYNAPSE AI — Source Quality & Freshness Analysis Engine.

Covers:
  1. Source type classification (official, academic, news, industry, company, general, unknown)
  2. Publication date extraction (ISO, URL-embedded, verbose, reversed, year-only, N/A)
  3. Freshness calculation (current, recent, aging, stale, undated)
  4. Authority score computation
  5. Extraction quality assessment
  6. Duplicate detection
  7. Composite quality score computation
  8. Full source profiling pipeline
  9. Batch profiling with SourceQualityReport
  10. Evidence re-ranking with quality scores
"""

import pytest
from datetime import datetime, timezone

from source_quality import (
    classify_source_type,
    extract_domain_from_url,
    extract_publication_date_enhanced,
    calculate_freshness,
    compute_authority_score,
    assess_extraction_quality,
    detect_content_duplicates,
    compute_quality_score,
    score_to_tier,
    profile_source,
    profile_all_sources,
    rank_retrieved_evidence,
    format_source_quality_briefing,
    SourceQualityProfile,
    SourceQualityReport,
)


# =====================================================================
# Test 1: Source Type Classification
# =====================================================================

class TestClassifySourceType:
    """Deterministic source type classification from domain patterns."""

    def test_official_gov(self):
        assert classify_source_type("https://www.cdc.gov/report", "cdc.gov") == "official"

    def test_official_gov_in(self):
        assert classify_source_type("https://niti.gov.in/policy", "niti.gov.in") == "official"

    def test_official_who(self):
        assert classify_source_type("https://who.int/data", "who.int") == "official"

    def test_official_worldbank(self):
        assert classify_source_type("https://worldbank.org/report", "worldbank.org") == "official"

    def test_academic_edu(self):
        assert classify_source_type("https://mit.edu/paper", "mit.edu") == "academic"

    def test_academic_arxiv(self):
        assert classify_source_type("https://arxiv.org/abs/2405.12345", "arxiv.org") == "academic"

    def test_academic_nature(self):
        assert classify_source_type("https://nature.com/article/123", "nature.com") == "academic"

    def test_academic_pubmed(self):
        assert classify_source_type("https://pubmed.ncbi.nlm.nih.gov/123", "pubmed.ncbi.nlm.nih.gov") == "academic"

    def test_academic_ac_uk(self):
        assert classify_source_type("https://ox.ac.uk/paper", "ox.ac.uk") == "academic"

    def test_news_reuters(self):
        assert classify_source_type("https://reuters.com/article", "reuters.com") == "news"

    def test_news_bbc(self):
        assert classify_source_type("https://bbc.com/news", "bbc.com") == "news"

    def test_news_techcrunch(self):
        assert classify_source_type("https://techcrunch.com/2024/05/01/ai", "techcrunch.com") == "news"

    def test_industry_mckinsey(self):
        assert classify_source_type("https://mckinsey.com/report", "mckinsey.com") == "industry"

    def test_industry_gartner(self):
        assert classify_source_type("https://gartner.com/analysis", "gartner.com") == "industry"

    def test_company_google(self):
        assert classify_source_type("https://blog.google.com/ai", "blog.google.com") == "company"

    def test_company_openai(self):
        assert classify_source_type("https://openai.com/research", "openai.com") == "company"

    def test_general_web(self):
        assert classify_source_type("https://randomsite.xyz/article", "randomsite.xyz") == "general"

    def test_unknown_empty(self):
        assert classify_source_type("", "") == "unknown"

    def test_unknown_localhost(self):
        assert classify_source_type("http://localhost:3000", "localhost") == "unknown"


# =====================================================================
# Test 2: Publication Date Extraction
# =====================================================================

class TestExtractPublicationDate:
    """Publication date heuristic extraction from text and URLs."""

    def test_iso_date(self):
        text = "Published on 2024-05-12. The report concludes..."
        assert extract_publication_date_enhanced(text) == "2024-05-12"

    def test_url_embedded_date(self):
        assert extract_publication_date_enhanced("", "https://example.com/2024/06/15/article") == "2024-06-15"

    def test_url_year_month(self):
        assert extract_publication_date_enhanced("", "https://blog.com/2025/03/post") == "2025-03-01"

    def test_verbose_month_day_year(self):
        text = "May 15, 2024 - An important study"
        result = extract_publication_date_enhanced(text)
        assert result == "2024-05-15"

    def test_reversed_day_month_year(self):
        text = "15 March 2025 - Latest findings"
        result = extract_publication_date_enhanced(text)
        assert result == "2025-03-15"

    def test_abbreviated_month(self):
        text = "Published: Jan 3, 2024"
        result = extract_publication_date_enhanced(text)
        assert result == "2024-01-03"

    def test_year_only(self):
        text = "© 2023 Company Inc. All rights reserved."
        result = extract_publication_date_enhanced(text)
        assert result == "2023-01-01"

    def test_no_date(self):
        text = "This article has no date information whatsoever."
        result = extract_publication_date_enhanced(text)
        assert result == "N/A"


# =====================================================================
# Test 3: Freshness Calculation
# =====================================================================

class TestCalculateFreshness:
    """Freshness labels based on publication age relative to reference date."""

    @pytest.fixture
    def ref(self):
        return datetime(2026, 6, 1, tzinfo=timezone.utc)

    def test_current(self, ref):
        label, days = calculate_freshness("2026-03-01", ref)
        assert label == "current"
        assert 0 < days <= 180

    def test_recent(self, ref):
        label, days = calculate_freshness("2025-01-01", ref)
        assert label == "recent"
        assert 180 < days <= 730

    def test_aging(self, ref):
        label, days = calculate_freshness("2023-01-01", ref)
        assert label == "aging"
        assert 730 < days <= 1825

    def test_stale(self, ref):
        label, days = calculate_freshness("2019-01-01", ref)
        assert label == "stale"
        assert days > 1825

    def test_undated(self, ref):
        label, days = calculate_freshness("N/A", ref)
        assert label == "undated"
        assert days == -1

    def test_undated_empty(self, ref):
        label, days = calculate_freshness("", ref)
        assert label == "undated"
        assert days == -1

    def test_year_only_parse(self, ref):
        label, days = calculate_freshness("2026", ref)
        assert label == "current"


# =====================================================================
# Test 4: Authority Score
# =====================================================================

class TestAuthorityScore:
    """Authority signals and score computation."""

    def test_gov_domain(self):
        score, labels = compute_authority_score("https://cdc.gov/report", "cdc.gov")
        assert score > 0.0
        assert any("Government" in l for l in labels)

    def test_edu_domain(self):
        score, labels = compute_authority_score("https://mit.edu/paper", "mit.edu")
        assert score > 0.0
        assert any("Academic" in l for l in labels)

    def test_doi_present(self):
        score, labels = compute_authority_score("https://doi.org/10.1234/test", "doi.org")
        assert any("DOI" in l for l in labels)

    def test_https_bonus(self):
        score_https, _ = compute_authority_score("https://example.com", "example.com")
        score_http, _ = compute_authority_score("http://example.com", "example.com")
        assert score_https >= score_http

    def test_wire_service(self):
        score, labels = compute_authority_score("https://reuters.com/article", "reuters.com")
        assert any("wire" in l.lower() for l in labels)

    def test_unknown_domain(self):
        score, labels = compute_authority_score("https://random.xyz", "random.xyz")
        assert score <= 0.10  # Only HTTPS bonus at most


# =====================================================================
# Test 5: Extraction Quality
# =====================================================================

class TestExtractionQuality:
    """Extraction quality assessment based on text length."""

    def test_full(self):
        label, count = assess_extraction_quality("x" * 1000)
        assert label == "full"
        assert count == 1000

    def test_partial(self):
        label, _ = assess_extraction_quality("x" * 500)
        assert label == "partial"

    def test_snippet(self):
        label, _ = assess_extraction_quality("x" * 100)
        assert label == "snippet"

    def test_empty_string(self):
        label, count = assess_extraction_quality("")
        assert label == "empty"
        assert count == 0

    def test_none(self):
        label, count = assess_extraction_quality(None)
        assert label == "empty"
        assert count == 0


# =====================================================================
# Test 6: Duplicate Detection
# =====================================================================

class TestDuplicateDetection:
    """Content fingerprinting for duplicate/syndicated source detection."""

    def test_no_duplicates(self):
        sources = [
            {"url": "https://a.com", "source_id": "a", "text": "Unique content about topic alpha " * 10},
            {"url": "https://b.com", "source_id": "b", "text": "Different content about topic beta " * 10},
        ]
        result = detect_content_duplicates(sources)
        assert len(result) == 0

    def test_exact_duplicate(self):
        shared = "This is duplicated content from a syndicated article " * 20
        sources = [
            {"url": "https://original.com", "source_id": "orig", "text": shared},
            {"url": "https://copy.com", "source_id": "copy", "text": shared},
        ]
        result = detect_content_duplicates(sources)
        assert "copy" in result
        assert result["copy"] == "orig"

    def test_too_short_ignored(self):
        sources = [
            {"url": "https://a.com", "source_id": "a", "text": "short"},
            {"url": "https://b.com", "source_id": "b", "text": "short"},
        ]
        result = detect_content_duplicates(sources)
        assert len(result) == 0


# =====================================================================
# Test 7: Composite Quality Score
# =====================================================================

class TestCompositeQualityScore:
    """Quality score composition from individual dimensions."""

    def test_high_quality_source(self):
        profile = SourceQualityProfile(
            source_id="test1",
            url="https://nature.com/article/123",
            title="Nature Paper",
            domain="nature.com",
            source_type="academic",
            publication_date="2026-01-01",
            freshness="current",
            authority_score=0.32,
            extraction_quality="full",
            is_duplicate=False,
        )
        score = compute_quality_score(profile)
        assert score >= 0.70
        assert score_to_tier(score) in ("excellent", "good")

    def test_low_quality_source(self):
        profile = SourceQualityProfile(
            source_id="test2",
            url="http://random.xyz/page",
            title="Web Page",
            domain="random.xyz",
            source_type="unknown",
            publication_date="N/A",
            freshness="undated",
            authority_score=0.0,
            extraction_quality="empty",
            is_duplicate=True,
        )
        score = compute_quality_score(profile)
        assert score < 0.30
        assert score_to_tier(score) in ("low", "poor")

    def test_duplicate_penalty(self):
        base = SourceQualityProfile(
            source_id="a",
            url="https://example.com",
            domain="example.com",
            source_type="general",
            freshness="current",
            authority_score=0.1,
            extraction_quality="full",
            is_duplicate=False,
        )
        dup = base.model_copy(update={"is_duplicate": True, "source_id": "b"})
        score_base = compute_quality_score(base)
        score_dup = compute_quality_score(dup)
        assert score_base > score_dup


# =====================================================================
# Test 8: Full Source Profiling
# =====================================================================

class TestProfileSource:
    """End-to-end source profiling pipeline."""

    def test_academic_profile(self):
        p = profile_source(
            url="https://arxiv.org/abs/2405.12345",
            title="Deep Learning for Genomics",
            text="This paper presents a novel architecture for genomic sequence analysis. " * 50,
            reference_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        assert p.source_type == "academic"
        assert p.domain == "arxiv.org"
        assert p.extraction_quality == "full"
        assert p.quality_score > 0.0
        assert p.quality_tier in ("excellent", "good", "adequate")

    def test_unknown_minimal(self):
        p = profile_source(url="", title="", text="")
        assert p.source_type == "unknown"
        assert p.extraction_quality == "empty"
        assert "no_extracted_content" in p.penalties

    def test_stale_penalty(self):
        p = profile_source(
            url="https://example.com/old",
            title="Old Article",
            text="Article content " * 100,
            publication_date="2015-01-01",
            reference_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        assert p.freshness == "stale"
        assert "stale_content" in p.penalties

    def test_no_https_penalty(self):
        p = profile_source(
            url="http://insecure.com/page",
            title="HTTP Page",
            text="content " * 200,
        )
        assert "no_https" in p.penalties


# =====================================================================
# Test 9: Batch Source Profiling (SourceQualityReport)
# =====================================================================

class TestProfileAllSources:
    """Batch profiling, ranking, and distribution statistics."""

    def test_multiple_sources_ranked(self):
        sources = [
            {"url": "http://random.xyz/page", "title": "Random", "text": "short"},
            {"url": "https://nature.com/article", "title": "Nature Article", "text": "Detailed research content " * 100},
            {"url": "https://cdc.gov/report", "title": "CDC Report", "text": "Official government data " * 100},
        ]
        report = profile_all_sources(sources, session_id="test_session")
        assert report.total_sources == 3
        assert report.session_id == "test_session"
        # First ranked source should be higher quality than last
        assert report.scored_sources[0].quality_score >= report.scored_sources[-1].quality_score

    def test_type_distribution(self):
        sources = [
            {"url": "https://cdc.gov/a", "title": "CDC", "text": "x" * 100},
            {"url": "https://reuters.com/b", "title": "Reuters", "text": "y" * 100},
        ]
        report = profile_all_sources(sources)
        assert "official" in report.type_distribution
        assert "news" in report.type_distribution

    def test_empty_sources(self):
        report = profile_all_sources([])
        assert report.total_sources == 0
        assert report.average_quality == 0.0


# =====================================================================
# Test 10: Evidence Re-Ranking
# =====================================================================

class TestRankRetrievedEvidence:
    """Evidence re-ranking by blending similarity and quality scores."""

    def test_reranking(self):
        evidence = [
            {"source_id": "low", "similarity_score": 0.9, "text": "Low quality match"},
            {"source_id": "high", "similarity_score": 0.7, "text": "High quality match"},
        ]
        profiles = {
            "low": SourceQualityProfile(
                source_id="low", url="http://x.com", domain="x.com",
                source_type="unknown", quality_score=0.1,
            ),
            "high": SourceQualityProfile(
                source_id="high", url="https://nature.com", domain="nature.com",
                source_type="academic", quality_score=0.95,
            ),
        }
        ranked = rank_retrieved_evidence(evidence, profiles)
        # High quality source should beat low quality despite lower similarity
        # high: 0.7*0.7 + 0.3*0.95 = 0.49 + 0.285 = 0.775
        # low:  0.7*0.9 + 0.3*0.1  = 0.63 + 0.03  = 0.66
        assert ranked[0]["source_id"] == "high"
        assert ranked[0]["combined_score"] > ranked[1]["combined_score"]

    def test_no_profile_fallback(self):
        evidence = [
            {"source_id": "missing", "similarity_score": 0.8, "text": "Content"},
        ]
        ranked = rank_retrieved_evidence(evidence, {})
        assert ranked[0]["quality_score"] == 0.5  # default fallback
        assert "combined_score" in ranked[0]

    def test_empty_evidence(self):
        ranked = rank_retrieved_evidence([], {})
        assert ranked == []
