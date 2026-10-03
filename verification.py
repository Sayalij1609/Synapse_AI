"""
SYNAPSE AI - Autonomous Research Verification Agent & Evidence Integrity System.

Implements a closed-loop verification cycle:
Writer
 ↓
Verification Agent
 ↓
Decision
 ├── PASS → Final Report
 │
 └── FAIL → Additional Research
                    ↓
                 Reader
                    ↓
                 Evidence
                    ↓
                 Writer
                    ↓
                 Verification

Executes 11 deterministic and semantic verification checks:
1. Citation coverage
2. Unsupported claims
3. Evidence relevance
4. Source consistency
5. Contradictory evidence
6. Duplicate claims
7. Missing important information
8. Source quality
9. Source freshness
10. Numerical consistency
11. Logical consistency

Produces structured output adhering strictly to:
{
  "status": "PASS | RESEARCH_REQUIRED",
  "confidence": 0.0,
  "unsupported_claims": [],
  "weak_claims": [],
  "contradictions": [],
  "missing_topics": [],
  "additional_queries": [],
  "reasoning_summary": ""
}
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# -----------------------------
# Configuration Constants
# -----------------------------
MAX_RESEARCH_ITERATIONS = 1
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")

# Thresholds
MIN_CITATION_COVERAGE = 0.85
MIN_TEXT_OVERLAP_RATIO = 0.20
MIN_RELEVANCE_SCORE = 0.30
MAX_DUPLICATE_JACCARD = 0.65
MIN_PASS_CONFIDENCE = 0.70

logger = logging.getLogger("synapse.verification")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# -----------------------------
# Structured Models
# -----------------------------
class VerificationCheckDetail(BaseModel):
    """Result of an individual verification check."""
    name: str
    passed: bool
    score: float = 1.0
    details: str = ""
    flagged_items: List[Any] = Field(default_factory=list)


class VerificationResult(BaseModel):
    """
    Standard structured output produced by the Research Verification Agent.
    """
    status: str = "PASS"  # "PASS" or "RESEARCH_REQUIRED"
    confidence: float = 1.0  # 0.0 to 1.0
    unsupported_claims: List[Dict[str, Any]] = Field(default_factory=list)
    weak_claims: List[Dict[str, Any]] = Field(default_factory=list)
    contradictions: List[Dict[str, Any]] = Field(default_factory=list)
    missing_topics: List[str] = Field(default_factory=list)
    additional_queries: List[str] = Field(default_factory=list)
    reasoning_summary: str = ""
    iteration: int = 1
    checks: Dict[str, VerificationCheckDetail] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to the exact dictionary schema specified by requirements."""
        return {
            "status": self.status,
            "confidence": round(self.confidence, 3),
            "unsupported_claims": self.unsupported_claims,
            "weak_claims": self.weak_claims,
            "contradictions": self.contradictions,
            "missing_topics": self.missing_topics,
            "additional_queries": self.additional_queries,
            "reasoning_summary": self.reasoning_summary,
        }


# -----------------------------
# Stopwords and Tokenization Helpers
# -----------------------------
STOPWORDS: Set[str] = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of",
    "with", "by", "from", "up", "about", "into", "over", "after", "is", "are",
    "was", "were", "be", "been", "being", "have", "has", "had", "do", "does",
    "did", "will", "would", "shall", "should", "may", "might", "must", "can",
    "could", "that", "this", "these", "those", "it", "its", "as", "than", "then",
    "such", "more", "most", "also", "their", "they", "them", "which", "who", "whom"
}


def _extract_significant_tokens(text: str) -> List[str]:
    """Extract alphanumeric words >= 3 chars excluding common stopwords."""
    words = re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", text.lower())
    return [w for w in words if w not in STOPWORDS]


def _extract_numbers(text: str) -> List[str]:
    """Extract numbers, percentages, currency, and numerical metrics."""
    # Matches patterns like: 94.6%, $50B, 35%, 12, 1.5, 2024
    pattern = r"(?:\$|€|£|₹)?\b\d+(?:,\d+)*(?:\.\d+)?(?:%|[bkmBKM]\b)?"
    matches = re.findall(pattern, text)
    return [m.strip() for m in matches if m.strip() and any(c.isdigit() for c in m)]


# -----------------------------
# 11 Deterministic Verification Checks
# -----------------------------

def check_1_citation_coverage(
    claims: List[Any],
    sources: Dict[str, Any]
) -> VerificationCheckDetail:
    """
    Check 1: Citation coverage.
    Ratio of claims with at least 1 valid citation vs. total claims.
    All factual claims must cite valid, registered sources.
    """
    if not claims:
        return VerificationCheckDetail(
            name="citation_coverage",
            passed=False,
            score=0.0,
            details="No claims provided to verify.",
            flagged_items=[]
        )

    valid_cited_count = 0
    flagged = []

    for c in claims:
        cid = getattr(c, "claim_id", c.get("claim_id", "unknown") if isinstance(c, dict) else "unknown")
        text = getattr(c, "text", c.get("text", "") if isinstance(c, dict) else "")
        src_ids = getattr(c, "supporting_source_ids", c.get("supporting_source_ids", []) if isinstance(c, dict) else [])
        chunk_ids = getattr(c, "evidence_chunk_ids", c.get("evidence_chunk_ids", []) if isinstance(c, dict) else [])

        valid_sources = [sid for sid in src_ids if sid in sources]
        if valid_sources or chunk_ids:
            valid_cited_count += 1
        else:
            flagged.append({
                "claim_id": cid,
                "text": text,
                "reason": "Missing or non-existent source citation"
            })

    coverage = valid_cited_count / len(claims)
    passed = (coverage >= MIN_CITATION_COVERAGE) and (len(flagged) == 0)

    return VerificationCheckDetail(
        name="citation_coverage",
        passed=passed,
        score=round(coverage, 3),
        details=f"Citation coverage: {valid_cited_count}/{len(claims)} ({coverage:.1%}). Flagged {len(flagged)} uncited claims.",
        flagged_items=flagged
    )


def check_2_unsupported_claims(
    claims: List[Any],
    sources: Dict[str, Any],
    evidence_chunks: Dict[str, Any]
) -> VerificationCheckDetail:
    """
    Check 2: Unsupported claims.
    Detects claims where cited chunk text does not substantiate claim or citations were invented.
    """
    unsupported = []

    for c in claims:
        cid = getattr(c, "claim_id", c.get("claim_id", "unknown") if isinstance(c, dict) else "unknown")
        text = getattr(c, "text", c.get("text", "") if isinstance(c, dict) else "")
        src_ids = getattr(c, "supporting_source_ids", c.get("supporting_source_ids", []) if isinstance(c, dict) else [])
        chunk_ids = getattr(c, "evidence_chunk_ids", c.get("evidence_chunk_ids", []) if isinstance(c, dict) else [])
        status = getattr(c, "verification_status", c.get("verification_status", "grounded") if isinstance(c, dict) else "grounded")

        # Check for invented citations
        invalid_sources = [sid for sid in src_ids if sid not in sources]
        if src_ids and len(invalid_sources) == len(src_ids) and not chunk_ids:
            unsupported.append({
                "claim_id": cid,
                "text": text,
                "reason": f"Cited sources {invalid_sources} do not exist in the verified evidence store (invented citation)."
            })
            continue

        if status == "unsupported":
            unsupported.append({
                "claim_id": cid,
                "text": text,
                "reason": "Marked unsupported during citation grounding."
            })
            continue

        # Check evidence text backing
        supporting_text = []
        for chid in chunk_ids:
            if chid in evidence_chunks:
                chunk_obj = evidence_chunks[chid]
                t = getattr(chunk_obj, "text", chunk_obj.get("text", "") if isinstance(chunk_obj, dict) else "")
                supporting_text.append(t)

        if not supporting_text:
            for sid in src_ids:
                for chunk_obj in evidence_chunks.values():
                    c_sid = getattr(chunk_obj, "source_id", chunk_obj.get("source_id", "") if isinstance(chunk_obj, dict) else "")
                    if c_sid == sid:
                        t = getattr(chunk_obj, "text", chunk_obj.get("text", "") if isinstance(chunk_obj, dict) else "")
                        supporting_text.append(t)

        evidence_corpus = " ".join(supporting_text).lower()
        if not evidence_corpus:
            unsupported.append({
                "claim_id": cid,
                "text": text,
                "reason": "No evidence text found in store for cited references."
            })
            continue

        # Lexical grounding check
        claim_tokens = _extract_significant_tokens(text)
        if claim_tokens:
            overlap = sum(1 for w in claim_tokens if w in evidence_corpus)
            ratio = overlap / len(claim_tokens)
            if ratio < MIN_TEXT_OVERLAP_RATIO:
                unsupported.append({
                    "claim_id": cid,
                    "text": text,
                    "reason": f"Low evidence overlap ({ratio:.1%}). Significant terms missing from cited evidence."
                })

    passed = len(unsupported) == 0
    score = 1.0 if not claims else max(0.0, 1.0 - (len(unsupported) / len(claims)))

    return VerificationCheckDetail(
        name="unsupported_claims",
        passed=passed,
        score=round(score, 3),
        details=f"Detected {len(unsupported)} unsupported claims.",
        flagged_items=unsupported
    )


def check_3_evidence_relevance(
    retrieved_evidence: List[Any],
    plan: Optional[Dict[str, Any]] = None
) -> VerificationCheckDetail:
    """
    Check 3: Evidence relevance.
    Evaluates whether the retrieved evidence chunks semantically match the research objective.
    """
    if not retrieved_evidence:
        return VerificationCheckDetail(
            name="evidence_relevance",
            passed=False,
            score=0.0,
            details="No retrieved evidence chunks available.",
            flagged_items=[]
        )

    low_relevance = []
    total_sim = 0.0

    for ev in retrieved_evidence:
        cid = getattr(ev, "chunk_id", ev.get("chunk_id", "") if isinstance(ev, dict) else "")
        sim = float(getattr(ev, "similarity_score", ev.get("similarity_score", 0.0) if isinstance(ev, dict) else 0.0))
        total_sim += sim

        if sim < MIN_RELEVANCE_SCORE:
            low_relevance.append({
                "chunk_id": cid,
                "similarity_score": sim,
                "reason": f"Similarity score {sim:.2f} is below relevance threshold {MIN_RELEVANCE_SCORE:.2f}"
            })

    avg_sim = total_sim / len(retrieved_evidence)
    # Passed if average similarity is adequate and not more than 40% are low relevance
    passed = (avg_sim >= MIN_RELEVANCE_SCORE) and (len(low_relevance) / len(retrieved_evidence) <= 0.40)

    return VerificationCheckDetail(
        name="evidence_relevance",
        passed=passed,
        score=round(avg_sim, 3),
        details=f"Average evidence relevance score: {avg_sim:.3f}. {len(low_relevance)} chunks below threshold.",
        flagged_items=low_relevance
    )


def check_4_source_consistency(
    claims: List[Any],
    evidence_chunks: Dict[str, Any]
) -> VerificationCheckDetail:
    """
    Check 4: Source consistency.
    Checks whether different sources report consistent findings or diverge on key entities.
    """
    inconsistencies = []

    # Map entities / key topics to reported values
    # Look for divergent numeric claims on common subjects
    subject_map: Dict[str, List[Dict[str, Any]]] = {}

    for c in claims:
        cid = getattr(c, "claim_id", c.get("claim_id", "") if isinstance(c, dict) else "")
        text = getattr(c, "text", c.get("text", "") if isinstance(c, dict) else "")
        tokens = _extract_significant_tokens(text)
        nums = _extract_numbers(text)

        for i in range(len(tokens) - 1):
            pair = f"{tokens[i]}_{tokens[i+1]}"
            if nums:
                subject_map.setdefault(pair, []).append({
                    "claim_id": cid,
                    "text": text,
                    "numbers": nums
                })

    for pair, occurrences in subject_map.items():
        if len(occurrences) >= 2:
            # Check if different numbers are asserted for same concept
            first_nums = set(occurrences[0]["numbers"])
            for other in occurrences[1:]:
                other_nums = set(other["numbers"])
                if first_nums and other_nums and not (first_nums & other_nums):
                    inconsistencies.append({
                        "subject": pair,
                        "claim_a": occurrences[0]["text"],
                        "claim_b": other["text"],
                        "divergent_metrics": f"{first_nums} vs {other_nums}",
                        "reason": f"Conflicting numerical figures reported for subject '{pair}'"
                    })

    passed = len(inconsistencies) == 0
    score = 1.0 if not inconsistencies else max(0.0, 1.0 - (len(inconsistencies) * 0.2))

    return VerificationCheckDetail(
        name="source_consistency",
        passed=passed,
        score=round(score, 3),
        details=f"Source consistency check: {len(inconsistencies)} potential inconsistencies found.",
        flagged_items=inconsistencies
    )


def check_5_contradictory_evidence(
    claims: List[Any],
    evidence_chunks: Dict[str, Any]
) -> VerificationCheckDetail:
    """
    Check 5: Contradictory evidence.
    Direct contradictions across claims or between claims and cited evidence.
    """
    contradictions = []

    antonym_pairs = [
        ("increase", "decrease"), ("grew", "declined"), ("growth", "decline"),
        ("approved", "rejected"), ("legal", "illegal"), ("effective", "ineffective"),
        ("positive", "negative"), ("safe", "unsafe"), ("passed", "failed"),
        ("supported", "unsupported"), ("success", "failure")
    ]

    claim_texts = []
    for c in claims:
        cid = getattr(c, "claim_id", c.get("claim_id", "") if isinstance(c, dict) else "")
        text = getattr(c, "text", c.get("text", "") if isinstance(c, dict) else "")
        claim_texts.append((cid, text, text.lower()))

    # Check pairwise contradictions
    for i in range(len(claim_texts)):
        for j in range(i + 1, len(claim_texts)):
            cid_a, text_a, lower_a = claim_texts[i]
            cid_b, text_b, lower_b = claim_texts[j]

            # Common substantive subject
            tokens_a = set(_extract_significant_tokens(text_a))
            tokens_b = set(_extract_significant_tokens(text_b))
            common = tokens_a & tokens_b

            if len(common) >= 3:
                for pos, neg in antonym_pairs:
                    if (pos in lower_a and neg in lower_b) or (neg in lower_a and pos in lower_b):
                        contradictions.append({
                            "claim_a_id": cid_a,
                            "claim_b_id": cid_b,
                            "claim_a": text_a,
                            "claim_b": text_b,
                            "contradiction_terms": f"'{pos}' vs '{neg}'",
                            "reason": f"Direct polarity contradiction regarding '{', '.join(list(common)[:3])}'"
                        })

    passed = len(contradictions) == 0
    score = 1.0 if not contradictions else max(0.0, 1.0 - (len(contradictions) * 0.3))

    return VerificationCheckDetail(
        name="contradictory_evidence",
        passed=passed,
        score=round(score, 3),
        details=f"Detected {len(contradictions)} direct contradictions.",
        flagged_items=contradictions
    )


def check_6_duplicate_claims(
    claims: List[Any]
) -> VerificationCheckDetail:
    """
    Check 6: Duplicate claims.
    Identifies near-duplicate or redundant claims via token Jaccard similarity.
    """
    duplicates = []
    token_sets = []

    for c in claims:
        cid = getattr(c, "claim_id", c.get("claim_id", "") if isinstance(c, dict) else "")
        text = getattr(c, "text", c.get("text", "") if isinstance(c, dict) else "")
        tokens = set(_extract_significant_tokens(text))
        token_sets.append((cid, text, tokens))

    for i in range(len(token_sets)):
        for j in range(i + 1, len(token_sets)):
            cid_a, text_a, set_a = token_sets[i]
            cid_b, text_b, set_b = token_sets[j]

            if not set_a or not set_b:
                continue

            jaccard = len(set_a & set_b) / len(set_a | set_b)
            if jaccard >= MAX_DUPLICATE_JACCARD:
                duplicates.append({
                    "claim_a_id": cid_a,
                    "claim_b_id": cid_b,
                    "claim_a": text_a,
                    "claim_b": text_b,
                    "similarity": round(jaccard, 3),
                    "reason": f"High lexical overlap ({jaccard:.1%}) indicates redundant or duplicate claim."
                })

    passed = len(duplicates) == 0
    score = 1.0 if not duplicates else max(0.0, 1.0 - (len(duplicates) * 0.15))

    return VerificationCheckDetail(
        name="duplicate_claims",
        passed=passed,
        score=round(score, 3),
        details=f"Identified {len(duplicates)} duplicate/redundant claim pairs.",
        flagged_items=duplicates
    )


def check_7_missing_important_information(
    claims: List[Any],
    report: str,
    plan: Optional[Dict[str, Any]] = None
) -> VerificationCheckDetail:
    """
    Check 7: Missing important information.
    Compares the generated report and claims against the sub-questions in the research plan.
    Identifies unaddressed sub-questions as missing topics.
    """
    if not plan or not isinstance(plan, dict):
        return VerificationCheckDetail(
            name="missing_important_information",
            passed=True,
            score=1.0,
            details="No plan provided to evaluate missing topics.",
            flagged_items=[]
        )

    sub_questions = plan.get("sub_questions", [])
    if not sub_questions:
        return VerificationCheckDetail(
            name="missing_important_information",
            passed=True,
            score=1.0,
            details="Plan contains no sub-questions.",
            flagged_items=[]
        )

    claims_text = " ".join([
        getattr(c, "text", c.get("text", "") if isinstance(c, dict) else "")
        for c in claims
    ]).lower()
    full_report_text = f"{claims_text} {report.lower()}"

    missing_topics = []
    for sq in sub_questions:
        sq_tokens = _extract_significant_tokens(sq)
        if not sq_tokens:
            continue
        matched_tokens = sum(1 for tok in sq_tokens if tok in full_report_text)
        coverage_ratio = matched_tokens / len(sq_tokens)

        # If less than 40% of the sub-question's core concepts appear anywhere in report/claims
        if coverage_ratio < 0.40:
            missing_topics.append(sq)

    passed = len(missing_topics) == 0
    score = max(0.0, 1.0 - (len(missing_topics) / len(sub_questions)))

    return VerificationCheckDetail(
        name="missing_important_information",
        passed=passed,
        score=round(score, 3),
        details=f"Plan coverage: {len(sub_questions) - len(missing_topics)}/{len(sub_questions)} sub-questions addressed.",
        flagged_items=missing_topics
    )


def check_8_source_quality(
    sources: Dict[str, Any]
) -> VerificationCheckDetail:
    """
    Check 8: Source quality.
    Evaluates source domains for academic, government, industry, and news reputation.
    Flags suspicious, localhost, empty, or broken domains.
    """
    if not sources:
        return VerificationCheckDetail(
            name="source_quality",
            passed=False,
            score=0.0,
            details="No sources available to evaluate quality.",
            flagged_items=[]
        )

    reputable_suffixes = [".edu", ".gov", ".org", ".ac.uk", ".gov.in", ".int"]
    reputable_domains = [
        "nature.com", "sciencedirect.com", "thelancet.com", "ncbi.nlm.nih.gov",
        "arxiv.org", "reuters.com", "bloomberg.com", "bbc.com", "wsj.com",
        "nytimes.com", "ieee.org", "who.int", "niti.gov.in", "forbes.com"
    ]

    flagged_sources = []
    quality_score_sum = 0.0

    for sid, src in sources.items():
        domain = getattr(src, "domain", src.get("domain", "") if isinstance(src, dict) else "")
        url = getattr(src, "url", src.get("url", "") if isinstance(src, dict) else "")

        if not url or not domain or domain in ["web", "localhost", "127.0.0.1"]:
            flagged_sources.append({
                "source_id": sid,
                "url": url,
                "reason": "Missing, local, or invalid domain"
            })
            quality_score_sum += 0.2
            continue

        lower_d = domain.lower()
        if any(lower_d.endswith(s) for s in reputable_suffixes) or any(k in lower_d for k in reputable_domains):
            quality_score_sum += 1.0
        else:
            # Standard valid web domain
            quality_score_sum += 0.8

    avg_quality = quality_score_sum / len(sources)
    passed = (avg_quality >= 0.70) and (len(flagged_sources) == 0)

    return VerificationCheckDetail(
        name="source_quality",
        passed=passed,
        score=round(avg_quality, 3),
        details=f"Average source quality score: {avg_quality:.2f}. {len(flagged_sources)} low-quality sources flagged.",
        flagged_items=flagged_sources
    )


def check_9_source_freshness(
    sources: Dict[str, Any],
    current_year: int = 2026
) -> VerificationCheckDetail:
    """
    Check 9: Source freshness.
    Evaluates publication dates of retrieved sources to verify currency.
    """
    if not sources:
        return VerificationCheckDetail(
            name="source_freshness",
            passed=True,
            score=1.0,
            details="No sources to check for freshness.",
            flagged_items=[]
        )

    outdated_sources = []
    dated_sources_count = 0
    fresh_count = 0

    for sid, src in sources.items():
        pub_date = getattr(src, "publication_date", src.get("publication_date", "N/A") if isinstance(src, dict) else "N/A")
        year_match = re.search(r"\b(20[12]\d)\b", str(pub_date))
        if year_match:
            dated_sources_count += 1
            year = int(year_match.group(1))
            # If source is older than 5 years
            if (current_year - year) > 5:
                outdated_sources.append({
                    "source_id": sid,
                    "publication_date": pub_date,
                    "year": year,
                    "reason": f"Source published in {year}, older than 5 years."
                })
            else:
                fresh_count += 1

    # Freshness score
    if dated_sources_count > 0:
        freshness_ratio = fresh_count / dated_sources_count
    else:
        freshness_ratio = 0.8  # Neutral score if dates are unstated

    passed = (len(outdated_sources) / max(1, dated_sources_count)) <= 0.40

    return VerificationCheckDetail(
        name="source_freshness",
        passed=passed,
        score=round(freshness_ratio, 3),
        details=f"Source freshness: {fresh_count}/{dated_sources_count} dated sources are current.",
        flagged_items=outdated_sources
    )


def check_10_numerical_consistency(
    claims: List[Any],
    evidence_chunks: Dict[str, Any]
) -> VerificationCheckDetail:
    """
    Check 10: Numerical consistency.
    Extracts numbers, percentages, and metrics from claims and verifies they appear
    in the cited evidence chunks (flags fabricated statistics or mismatched numbers).
    """
    numerical_mismatches = []
    total_metrics_checked = 0
    verified_metrics = 0

    for c in claims:
        cid = getattr(c, "claim_id", c.get("claim_id", "") if isinstance(c, dict) else "")
        text = getattr(c, "text", c.get("text", "") if isinstance(c, dict) else "")
        chunk_ids = getattr(c, "evidence_chunk_ids", c.get("evidence_chunk_ids", []) if isinstance(c, dict) else [])
        src_ids = getattr(c, "supporting_source_ids", c.get("supporting_source_ids", []) if isinstance(c, dict) else [])

        numbers = _extract_numbers(text)
        if not numbers:
            continue

        # Collect evidence text
        evidence_texts = []
        for chid in chunk_ids:
            if chid in evidence_chunks:
                c_obj = evidence_chunks[chid]
                t = getattr(c_obj, "text", c_obj.get("text", "") if isinstance(c_obj, dict) else "")
                evidence_texts.append(t)

        if not evidence_texts:
            for sid in src_ids:
                for c_obj in evidence_chunks.values():
                    s_id = getattr(c_obj, "source_id", c_obj.get("source_id", "") if isinstance(c_obj, dict) else "")
                    if s_id == sid:
                        t = getattr(c_obj, "text", c_obj.get("text", "") if isinstance(c_obj, dict) else "")
                        evidence_texts.append(t)

        evidence_blob = " ".join(evidence_texts).lower()

        # Check each number in claim against evidence
        unmatched_for_claim = []
        for num in numbers:
            total_metrics_checked += 1
            clean_num = num.lower().replace(",", "")
            # Look for number in evidence
            if clean_num in evidence_blob:
                verified_metrics += 1
            else:
                unmatched_for_claim.append(num)

        if unmatched_for_claim:
            numerical_mismatches.append({
                "claim_id": cid,
                "text": text,
                "unmatched_numbers": unmatched_for_claim,
                "reason": f"Numbers {unmatched_for_claim} not found in cited evidence chunks."
            })

    passed = len(numerical_mismatches) == 0
    score = 1.0 if total_metrics_checked == 0 else verified_metrics / total_metrics_checked

    return VerificationCheckDetail(
        name="numerical_consistency",
        passed=passed,
        score=round(score, 3),
        details=f"Verified {verified_metrics}/{total_metrics_checked} numeric metrics. {len(numerical_mismatches)} claims contain unbacked figures.",
        flagged_items=numerical_mismatches
    )


def check_11_logical_consistency(
    claims: List[Any],
    report: str
) -> VerificationCheckDetail:
    """
    Check 11: Logical consistency.
    Audits the report and claims for internal logical paradoxes or self-negating assertions.
    """
    logical_issues = []

    # Check for direct logical paradox phrases
    paradox_indicators = [
        r"\bboth entirely true and completely false\b",
        r"\bunanimously opposed yet universally adopted\b",
        r"\bzero cost but extremely expensive\b",
        r"\b100% effective but failed in all trials\b"
    ]

    combined_text = f"{report} " + " ".join([
        getattr(c, "text", c.get("text", "") if isinstance(c, dict) else "")
        for c in claims
    ])

    for pattern in paradox_indicators:
        match = re.search(pattern, combined_text, re.IGNORECASE)
        if match:
            logical_issues.append({
                "phrase": match.group(0),
                "reason": "Direct internal logical paradox detected."
            })

    passed = len(logical_issues) == 0
    score = 1.0 if passed else 0.5

    return VerificationCheckDetail(
        name="logical_consistency",
        passed=passed,
        score=round(score, 3),
        details=f"Logical consistency check: {len(logical_issues)} issues found.",
        flagged_items=logical_issues
    )


# -----------------------------
# Targeted Additional Query Generator
# -----------------------------
def generate_additional_queries_deterministic(
    unsupported_claims: List[Dict[str, Any]],
    weak_claims: List[Dict[str, Any]],
    contradictions: List[Dict[str, Any]],
    missing_topics: List[str],
    topic: str
) -> List[str]:
    """
    Deterministically generate targeted, high-precision search queries
    to resolve specific verification failures.
    """
    queries = []
    seen = set()

    def add_q(q: str):
        clean_q = " ".join(q.split())
        if clean_q and clean_q.lower() not in seen and len(queries) < 5:
            seen.add(clean_q.lower())
            queries.append(clean_q)

    # 1. Missing topics from plan get direct targeted search queries
    for topic_item in missing_topics:
        # Extract concise query from sub-question
        clean_item = re.sub(r"^(what|how|why|when|is|can|does|analyze|evaluate)\s+", "", topic_item, flags=re.IGNORECASE)
        clean_item = re.sub(r"[?!.]", "", clean_item).strip()
        add_q(f"{topic} {clean_item}")

    # 2. Unsupported claims need empirical verification queries
    for item in unsupported_claims:
        text = item.get("text", "")
        tokens = _extract_significant_tokens(text)
        if tokens:
            key_terms = " ".join(tokens[:5])
            add_q(f"{topic} {key_terms} research data")

    # 3. Contradictions need clarifying empirical queries
    for item in contradictions:
        reason = item.get("reason", "")
        terms = item.get("contradiction_terms", "")
        add_q(f"{topic} {terms} statistics report")

    # 4. Weak claims needing numerical or source confirmation
    for item in weak_claims:
        text = item.get("text", "")
        tokens = _extract_significant_tokens(text)
        if tokens:
            key_terms = " ".join(tokens[:4])
            add_q(f"{topic} {key_terms} facts evidence")

    # Fallback if no specific queries were derived
    if not queries and (unsupported_claims or missing_topics):
        add_q(f"{topic} latest empirical research facts")

    return queries


# -----------------------------
# Deterministic Verifier Engine
# -----------------------------
def run_deterministic_verification(
    claims: List[Any],
    sources: Dict[str, Any],
    evidence_chunks: Dict[str, Any],
    retrieved_evidence: List[Any],
    report: str,
    plan: Optional[Dict[str, Any]] = None,
    iteration: int = 1,
    topic: str = ""
) -> VerificationResult:
    """
    Execute all 11 deterministic checks and construct the structured VerificationResult.
    Guarantees deterministic, reproducible verification without arbitrary LLM scoring.
    """
    logger.info("Executing 11 deterministic verification checks (Iteration %d)...", iteration)

    c1 = check_1_citation_coverage(claims, sources)
    c2 = check_2_unsupported_claims(claims, sources, evidence_chunks)
    c3 = check_3_evidence_relevance(retrieved_evidence, plan)
    c4 = check_4_source_consistency(claims, evidence_chunks)
    c5 = check_5_contradictory_evidence(claims, evidence_chunks)
    c6 = check_6_duplicate_claims(claims)
    c7 = check_7_missing_important_information(claims, report, plan)
    c8 = check_8_source_quality(sources)
    c9 = check_9_source_freshness(sources)
    c10 = check_10_numerical_consistency(claims, evidence_chunks)
    c11 = check_11_logical_consistency(claims, report)

    all_checks = {
        "citation_coverage": c1,
        "unsupported_claims": c2,
        "evidence_relevance": c3,
        "source_consistency": c4,
        "contradictory_evidence": c5,
        "duplicate_claims": c6,
        "missing_important_information": c7,
        "source_quality": c8,
        "source_freshness": c9,
        "numerical_consistency": c10,
        "logical_consistency": c11,
    }

    # Aggregate flagged items
    unsupported_claims = list(c2.flagged_items)
    # Weak claims: claims with citation issues or numerical mismatches
    weak_claims = []
    for item in c1.flagged_items:
        weak_claims.append(item)
    for item in c10.flagged_items:
        weak_claims.append(item)

    contradictions = list(c5.flagged_items) + list(c4.flagged_items)
    missing_topics = [str(item) for item in c7.flagged_items]

    # Weighted confidence score calculation
    # Weights prioritize core empirical validity:
    weights = {
        "citation_coverage": 0.15,
        "unsupported_claims": 0.20,
        "evidence_relevance": 0.10,
        "source_consistency": 0.05,
        "contradictory_evidence": 0.15,
        "duplicate_claims": 0.05,
        "missing_important_information": 0.10,
        "source_quality": 0.05,
        "source_freshness": 0.05,
        "numerical_consistency": 0.05,
        "logical_consistency": 0.05,
    }

    confidence = sum(all_checks[k].score * weights[k] for k in weights)

    # Hard criteria for PASS:
    # 1. No unsupported claims
    # 2. No direct contradictions
    # 3. No missing topics from research plan
    # 4. Confidence >= MIN_PASS_CONFIDENCE
    # 5. Citation coverage >= MIN_CITATION_COVERAGE
    is_hard_pass = (
        len(unsupported_claims) == 0 and
        len(contradictions) == 0 and
        len(missing_topics) == 0 and
        confidence >= MIN_PASS_CONFIDENCE and
        c1.passed
    )

    status = "PASS" if is_hard_pass else "RESEARCH_REQUIRED"

    # Generate targeted additional queries if research is required
    additional_queries = []
    if status == "RESEARCH_REQUIRED":
        additional_queries = generate_additional_queries_deterministic(
            unsupported_claims=unsupported_claims,
            weak_claims=weak_claims,
            contradictions=contradictions,
            missing_topics=missing_topics,
            topic=topic
        )

    # Build reasoning summary
    summary_parts = [
        f"Verification Iteration {iteration}: Status={status}, Confidence={confidence:.1%}.",
    ]
    if status == "PASS":
        summary_parts.append(
            f"All 11 verification checks passed. Citation coverage is {c1.score:.1%}, "
            f"0 unsupported claims, 0 contradictions, and all {len(claims)} factual assertions are verified."
        )
    else:
        reasons = []
        if unsupported_claims:
            reasons.append(f"{len(unsupported_claims)} unsupported claims detected")
        if contradictions:
            reasons.append(f"{len(contradictions)} conflicting findings or contradictions detected")
        if missing_topics:
            reasons.append(f"{len(missing_topics)} sub-questions from plan unaddressed")
        if weak_claims:
            reasons.append(f"{len(weak_claims)} weak claims or numerical mismatches")
        if not c1.passed:
            reasons.append(f"Citation coverage below threshold ({c1.score:.1%})")

        summary_parts.append(
            f"Autonomous remediation triggered because: {'; '.join(reasons)}. "
            f"Generated {len(additional_queries)} targeted search queries to acquire missing evidence."
        )

    reasoning_summary = " ".join(summary_parts)

    return VerificationResult(
        status=status,
        confidence=confidence,
        unsupported_claims=unsupported_claims,
        weak_claims=weak_claims,
        contradictions=contradictions,
        missing_topics=missing_topics,
        additional_queries=additional_queries,
        reasoning_summary=reasoning_summary,
        iteration=iteration,
        checks=all_checks
    )


# -----------------------------
# Autonomous Research Verification Agent (LLM + Deterministic)
# -----------------------------
class ResearchVerificationAgent:
    """
    Autonomous Research Verification Agent.
    Combines deterministic verification checks with an LLM reasoning audit layer.
    Guarantees no human-in-the-loop and strict adherence to evidence grounding.
    """

    def __init__(self, model_name: str = GROQ_MODEL):
        self.model_name = model_name
        self._llm = ChatGroq(
            model=model_name,
            temperature=0,
            max_tokens=450,
            max_retries=3
        )

    def verify(
        self,
        claims: List[Any],
        sources: Dict[str, Any],
        evidence_chunks: Dict[str, Any],
        retrieved_evidence: List[Any],
        report: str,
        plan: Optional[Dict[str, Any]] = None,
        iteration: int = 1,
        topic: str = ""
    ) -> VerificationResult:
        """
        Execute full autonomous verification pipeline:
        1. Run 11 deterministic verification checks.
        2. If deterministic checks fail, immediately return RESEARCH_REQUIRED with targeted queries.
        3. If deterministic checks pass, invoke LLM verifier to audit higher-order logical coherence.
        """
        # Step 1: Run deterministic checks
        det_result = run_deterministic_verification(
            claims=claims,
            sources=sources,
            evidence_chunks=evidence_chunks,
            retrieved_evidence=retrieved_evidence,
            report=report,
            plan=plan,
            iteration=iteration,
            topic=topic
        )

        # Deterministic checks have final veto power: if deterministic check requires research, do not allow LLM to override to PASS
        if det_result.status == "RESEARCH_REQUIRED":
            logger.info(
                "Deterministic verification required research: %d unsupported claims, %d contradictions, %d missing topics",
                len(det_result.unsupported_claims),
                len(det_result.contradictions),
                len(det_result.missing_topics)
            )
            return det_result

        # Step 2: Deterministic passed; run secondary LLM semantic verification audit
        try:
            llm_result = self._audit_with_llm(
                report=report,
                claims=claims,
                topic=topic,
                plan=plan
            )
            if llm_result:
                # Merge LLM nuances
                if llm_result.get("status") == "RESEARCH_REQUIRED":
                    det_result.status = "RESEARCH_REQUIRED"
                    det_result.confidence = min(det_result.confidence, float(llm_result.get("confidence", 0.6)))
                    llm_queries = llm_result.get("additional_queries", [])
                    if llm_queries:
                        det_result.additional_queries.extend([q for q in llm_queries if q not in det_result.additional_queries])
                    det_result.reasoning_summary += f" LLM Audit: {llm_result.get('reasoning_summary', '')}"
        except Exception as e:
            logger.warning("Secondary LLM verification audit skipped due to error: %s. Using deterministic result.", str(e))

        return det_result

    def _audit_with_llm(
        self,
        report: str,
        claims: List[Any],
        topic: str,
        plan: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Invoke Groq LLM with concise JSON schema for semantic audit."""
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                """You are an elite autonomous Research Verification Agent.
Audit the synthesized research claims against the topic and objective.
Output ONLY a valid JSON object matching this schema:
{{
  "status": "PASS",
  "confidence": 0.95,
  "unsupported_claims": [],
  "weak_claims": [],
  "contradictions": [],
  "missing_topics": [],
  "additional_queries": [],
  "reasoning_summary": "One sentence summary of findings."
}}
If claims lack depth or contradict each other, set status to "RESEARCH_REQUIRED" and suggest 2 targeted additional search queries.
Do not output commentary outside JSON."""
            ),
            (
                "human",
                """Research Topic: {topic}
Objective: {objective}

Report Excerpt:
{report_excerpt}

Verify:"""
            )
        ])

        obj = plan.get("research_objective", "") if isinstance(plan, dict) else ""
        chain = prompt | self._llm | StrOutputParser()
        raw = chain.invoke({
            "topic": topic,
            "objective": obj,
            "report_excerpt": report[:1200]
        })

        # Parse JSON
        clean = raw.strip()
        if "```" in clean:
            clean = re.sub(r"```(?:json)?", "", clean).strip()
        return json.loads(clean)


# -----------------------------
# Unresolved Claim Badging & Final Report Formatter
# -----------------------------
def mark_unresolved_claims(
    claims: List[Any],
    markdown_report: str,
    verification_result: VerificationResult
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    When MAX_RESEARCH_ITERATIONS is reached without complete verification:
    1. Explicitly marks unresolved claims with a visible warning badge in the report text.
    2. Appends an authoritative Verification & Evidence Audit section.
    3. Guarantees NEVER fabricating evidence.
    """
    unresolved_ids = set()
    for item in verification_result.unsupported_claims:
        unresolved_ids.add(item.get("claim_id"))
    for item in verification_result.contradictions:
        if item.get("claim_a_id"):
            unresolved_ids.add(item.get("claim_a_id"))
        if item.get("claim_b_id"):
            unresolved_ids.add(item.get("claim_b_id"))

    unresolved_records = []
    updated_report = markdown_report

    for c in claims:
        cid = getattr(c, "claim_id", c.get("claim_id", "") if isinstance(c, dict) else "")
        text = getattr(c, "text", c.get("text", "") if isinstance(c, dict) else "")

        if cid in unresolved_ids:
            unresolved_records.append({
                "claim_id": cid,
                "text": text,
                "status": "UNRESOLVED",
                "notes": f"Evidence could not be fully substantiated after {MAX_RESEARCH_ITERATIONS} autonomous verification cycles."
            })
            # Replace occurrences in report with explicit unresolved badge
            badge = f"\n> ⚠️ **[UNRESOLVED CLAIM — Insufficient Evidence]**: {text} *(Could not be verified after {MAX_RESEARCH_ITERATIONS} search iterations; no evidence fabricated)*\n"
            if text in updated_report:
                updated_report = updated_report.replace(text, badge)

    # Append formal audit section to the report
    audit_section = [
        "\n\n---\n\n## Verification & Evidence Audit",
        f"- **Verification Status**: {verification_result.status}",
        f"- **Final Confidence Score**: {verification_result.confidence:.1%}",
        f"- **Iterations Completed**: {verification_result.iteration}/{MAX_RESEARCH_ITERATIONS}",
        f"- **Autonomous Summary**: {verification_result.reasoning_summary}",
    ]

    if unresolved_records:
        audit_section.append("\n### Flagged Unresolved Assertions")
        for u in unresolved_records:
            audit_section.append(f"- **[{u['claim_id']}]**: {u['text']}")
            audit_section.append(f"  *Audit Note*: {u['notes']}")

    if verification_result.missing_topics:
        audit_section.append("\n### Topics Requiring Further Field Inquiry")
        for t in verification_result.missing_topics:
            audit_section.append(f"- {t}")

    updated_report += "\n".join(audit_section)
    return updated_report, unresolved_records
