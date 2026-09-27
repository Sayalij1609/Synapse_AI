"""
SYNAPSE AI — Automated Source Quality & Freshness Analysis Engine.

Provides deterministic, signal-based scoring for every discovered research source.
Does NOT rely on arbitrary LLM credibility ratings.

For every source, computes structured metadata:
  - domain
  - source_type  (official | academic | news | industry | company | general | unknown)
  - publication_date
  - retrieval_date
  - freshness  (current | recent | aging | stale | undated)
  - authority_indicators  (list of matched signals)
  - relevance  (high | moderate | low)
  - extraction_quality  (full | partial | snippet | empty)
  - quality_score  (0.0 – 1.0 composite)

Scoring is deterministic and reproducible across runs.
Lower-quality sources are ranked, never deleted.
"""

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

from pydantic import BaseModel, Field

# -----------------------------
# Logger
# -----------------------------
logger = logging.getLogger("synapse.source_quality")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# =====================================================================
# Source Type Classification Registry
# =====================================================================

# Maps domain patterns to source types.
# Order matters: first match wins.

OFFICIAL_DOMAINS: List[str] = [
    ".gov", ".gov.in", ".gov.uk", ".gov.au", ".gov.ca", ".gov.sg",
    ".mil", ".gc.ca",
    "who.int", "un.org", "europa.eu", "worldbank.org", "imf.org",
    "cdc.gov", "nih.gov", "niti.gov.in", "data.gov",
]

ACADEMIC_DOMAINS: List[str] = [
    ".edu", ".ac.", ".edu.au", ".edu.in",
    "arxiv.org", "ncbi.nlm.nih.gov", "pubmed", "nature.com",
    "sciencedirect.com", "springer.com", "biorxiv.org", "medrxiv.org",
    "cell.com", "thelancet.com", "bmj.com", "nejm.org",
    "ieee.org", "acm.org", "plos.org", "wiley.com", "tandfonline.com",
    "frontiersin.org", "mdpi.com", "jstor.org", "researchgate.net",
    "scholar.google.com", "semanticscholar.org",
]

NEWS_DOMAINS: List[str] = [
    "reuters.com", "apnews.com", "bloomberg.com", "bbc.com", "bbc.co.uk",
    "nytimes.com", "washingtonpost.com", "wsj.com", "economist.com",
    "ft.com", "theguardian.com", "aljazeera.com", "cnn.com",
    "thehindu.com", "ndtv.com", "hindustantimes.com",
    "techcrunch.com", "wired.com", "arstechnica.com", "theverge.com",
    "forbes.com", "fortune.com", "businessinsider.com",
    "politico.com", "axios.com",
]

INDUSTRY_DOMAINS: List[str] = [
    "mckinsey.com", "gartner.com", "deloitte.com", "pwc.com",
    "accenture.com", "bcg.com", "bain.com", "ey.com", "kpmg.com",
    "statista.com", "idc.com", "forrester.com", "cb insights",
    "crunchbase.com",
]

COMPANY_DOMAINS: List[str] = [
    "google.com", "microsoft.com", "amazon.com", "apple.com",
    "meta.com", "openai.com", "deepmind.com", "nvidia.com",
    "ibm.com", "salesforce.com", "oracle.com", "intel.com",
    "blog.", "developers.", "engineering.",
]


# =====================================================================
# Authority Indicators — deterministic signals
# =====================================================================

AUTHORITY_SIGNALS: Dict[str, Dict[str, Any]] = {
    # TLD-based signals
    "gov_tld": {
        "pattern_fn": lambda domain, url: any(f".gov" in domain for _ in [1]) and ".gov" in domain,
        "weight": 0.15,
        "label": "Government TLD (.gov)",
    },
    "edu_tld": {
        "pattern_fn": lambda domain, url: ".edu" in domain or ".ac." in domain,
        "weight": 0.12,
        "label": "Academic TLD (.edu/.ac)",
    },
    "org_tld": {
        "pattern_fn": lambda domain, url: domain.endswith(".org"),
        "weight": 0.05,
        "label": "Organization TLD (.org)",
    },
    # Peer-reviewed indicators
    "doi_present": {
        "pattern_fn": lambda domain, url: "/doi/" in url or "doi.org" in url,
        "weight": 0.10,
        "label": "DOI present (peer-reviewed)",
    },
    "pubmed_id": {
        "pattern_fn": lambda domain, url: "pubmed" in domain or "/pmc/" in url,
        "weight": 0.10,
        "label": "PubMed/PMC indexed",
    },
    "arxiv_preprint": {
        "pattern_fn": lambda domain, url: "arxiv.org" in domain,
        "weight": 0.08,
        "label": "arXiv preprint",
    },
    # Wire service
    "wire_service": {
        "pattern_fn": lambda domain, url: any(ws in domain for ws in ["reuters.com", "apnews.com", "bloomberg.com"]),
        "weight": 0.08,
        "label": "Major wire service",
    },
    # HTTPS
    "https": {
        "pattern_fn": lambda domain, url: url.startswith("https://"),
        "weight": 0.02,
        "label": "HTTPS secure",
    },
}


# =====================================================================
# Structured Models
# =====================================================================

class SourceQualityProfile(BaseModel):
    """
    Complete quality and metadata profile for a single discovered source.
    """
    source_id: str
    url: str
    title: str = "Web Document"
    domain: str = "web"
    source_type: str = "unknown"  # official|academic|news|industry|company|general|unknown
    publication_date: str = "N/A"
    retrieval_date: str = ""
    freshness: str = "undated"  # current|recent|aging|stale|undated
    freshness_days: int = -1  # -1 = undated
    authority_indicators: List[str] = Field(default_factory=list)
    authority_score: float = 0.0  # 0.0–1.0
    extraction_quality: str = "empty"  # full|partial|snippet|empty
    extraction_char_count: int = 0
    is_duplicate: bool = False
    duplicate_of: str = ""
    quality_score: float = 0.0  # 0.0–1.0 composite
    quality_tier: str = "unknown"  # excellent|good|adequate|low|poor
    subtask_id: str = "general"
    penalties: List[str] = Field(default_factory=list)


class SourceQualityReport(BaseModel):
    """
    Aggregated quality report for all sources in a research session.
    """
    session_id: str = ""
    total_sources: int = 0
    scored_sources: List[SourceQualityProfile] = Field(default_factory=list)
    type_distribution: Dict[str, int] = Field(default_factory=dict)
    freshness_distribution: Dict[str, int] = Field(default_factory=dict)
    quality_distribution: Dict[str, int] = Field(default_factory=dict)
    average_quality: float = 0.0
    duplicate_count: int = 0
    undated_count: int = 0
    stale_count: int = 0


# =====================================================================
# Core Classification Functions
# =====================================================================

def classify_source_type(url: str, domain: str) -> str:
    """
    Deterministic source type classification based on domain pattern matching.
    Returns one of: official, academic, news, industry, company, general, unknown.
    """
    if not url and not domain:
        return "unknown"

    lower_domain = domain.lower() if domain else ""
    lower_url = url.lower() if url else ""

    if not lower_domain or lower_domain in ("web", "localhost", "127.0.0.1", ""):
        return "unknown"

    # Academic / Research  (checked first: some academic hosts sit on .gov TLDs)
    for pattern in ACADEMIC_DOMAINS:
        if pattern in lower_domain:
            return "academic"

    # Official / Government
    for pattern in OFFICIAL_DOMAINS:
        if pattern in lower_domain:
            return "official"

    # News / Media
    for pattern in NEWS_DOMAINS:
        if pattern in lower_domain:
            return "news"

    # Industry / Consulting
    for pattern in INDUSTRY_DOMAINS:
        if pattern in lower_domain:
            return "industry"

    # Company / Corporate
    for pattern in COMPANY_DOMAINS:
        if pattern in lower_domain or pattern in lower_url:
            return "company"

    # General web — has a valid domain but doesn't match any known category
    if "." in lower_domain:
        return "general"

    return "unknown"


def extract_domain_from_url(url: str) -> str:
    """Extract clean domain from a URL."""
    if not url:
        return "web"
    try:
        if "://" not in url and not url.startswith("//"):
            url = f"http://{url}"
        parsed = urlparse(url)
        netloc = parsed.netloc or parsed.path.split("/")[0]
        domain = netloc.replace("www.", "").lower()
        return domain if "." in domain else "web"
    except Exception:
        return "web"


# =====================================================================
# Publication Date Extraction
# =====================================================================

MONTH_MAP = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "jun": "06", "jul": "07", "aug": "08", "sep": "09",
    "oct": "10", "nov": "11", "dec": "12",
}


def extract_publication_date_enhanced(text: str, url: str = "") -> str:
    """
    Enhanced heuristic publication date extraction.
    Searches text first 1500 chars + URL for date patterns.
    Returns ISO-style YYYY-MM-DD string or 'N/A'.
    """
    search_text = (text[:1500] + " " + url) if text else url

    # 1. ISO date: 2024-05-12 or 2024/05/12
    iso_match = re.search(
        r"\b(20[12]\d)[-/.]([01]\d)[-/.]([0-3]\d)\b",
        search_text
    )
    if iso_match:
        return f"{iso_match.group(1)}-{iso_match.group(2)}-{iso_match.group(3)}"

    # 2. URL-embedded date: /2024/05/12/ or /2024-05-12/
    url_date = re.search(
        r"/(20[12]\d)/([01]\d)/([0-3]\d)",
        url
    )
    if url_date:
        return f"{url_date.group(1)}-{url_date.group(2)}-{url_date.group(3)}"

    # URL-embedded year-month: /2024/05/
    url_ym = re.search(r"/(20[12]\d)/([01]\d)/", url)
    if url_ym:
        return f"{url_ym.group(1)}-{url_ym.group(2)}-01"

    # 3. Verbose: "May 15, 2024" or "15 May 2024"
    verbose_match = re.search(
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December|"
        r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2}),?\s+(20[12]\d)\b",
        search_text,
        re.IGNORECASE
    )
    if verbose_match:
        month_str = verbose_match.group(1).lower()
        day = verbose_match.group(2).zfill(2)
        year = verbose_match.group(3)
        mm = MONTH_MAP.get(month_str, "01")
        return f"{year}-{mm}-{day}"

    # 4. Reversed verbose: "15 May 2024"
    rev_match = re.search(
        r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December|"
        r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(20[12]\d)\b",
        search_text,
        re.IGNORECASE
    )
    if rev_match:
        day = rev_match.group(1).zfill(2)
        month_str = rev_match.group(2).lower()
        year = rev_match.group(3)
        mm = MONTH_MAP.get(month_str, "01")
        return f"{year}-{mm}-{day}"

    # 5. Year-only: "Published 2024" or "© 2024"
    year_match = re.search(r"\b(20[12]\d)\b", search_text[:800])
    if year_match:
        return f"{year_match.group(1)}-01-01"

    return "N/A"


# =====================================================================
# Freshness Calculation
# =====================================================================

def calculate_freshness(
    publication_date: str,
    reference_date: Optional[datetime] = None
) -> Tuple[str, int]:
    """
    Deterministic freshness classification based on publication date.

    Returns:
        (freshness_label, days_old)
        freshness_label: 'current' | 'recent' | 'aging' | 'stale' | 'undated'
        days_old: integer days since publication, or -1 if undated

    Thresholds:
        current:  <= 180 days (6 months)
        recent:   <= 730 days (2 years)
        aging:    <= 1825 days (5 years)
        stale:    > 1825 days (5+ years)
        undated:  publication date unavailable
    """
    if not publication_date or publication_date == "N/A":
        return "undated", -1

    ref = reference_date or datetime.now(timezone.utc)

    # Try ISO parse
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            pub_dt = datetime.strptime(publication_date.strip()[:19], fmt)
            if pub_dt.tzinfo is None:
                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
            break
        except ValueError:
            continue
    else:
        # Try year-only
        year_match = re.search(r"\b(20[12]\d)\b", publication_date)
        if year_match:
            pub_dt = datetime(int(year_match.group(1)), 1, 1, tzinfo=timezone.utc)
        else:
            return "undated", -1

    delta = ref - pub_dt
    days_old = max(0, delta.days)

    if days_old <= 180:
        return "current", days_old
    elif days_old <= 730:
        return "recent", days_old
    elif days_old <= 1825:
        return "aging", days_old
    else:
        return "stale", days_old


# =====================================================================
# Authority Score Calculation
# =====================================================================

def compute_authority_score(url: str, domain: str) -> Tuple[float, List[str]]:
    """
    Compute a deterministic authority score from signal matching.
    Returns (score 0.0–1.0, list_of_matched_indicator_labels).
    """
    matched: List[str] = []
    raw_score = 0.0

    for signal_name, signal_def in AUTHORITY_SIGNALS.items():
        try:
            if signal_def["pattern_fn"](domain, url):
                raw_score += signal_def["weight"]
                matched.append(signal_def["label"])
        except Exception:
            continue

    # Clamp to 1.0
    clamped = min(1.0, raw_score)
    return round(clamped, 3), matched


# =====================================================================
# Extraction Quality Assessment
# =====================================================================

def assess_extraction_quality(text: str) -> Tuple[str, int]:
    """
    Assess quality of extracted text content.
    Returns (quality_label, char_count).
        full:     >= 1000 chars of substantive text
        partial:  >= 300 chars
        snippet:  >= 50 chars
        empty:    < 50 chars
    """
    if not text:
        return "empty", 0

    clean = text.strip()
    char_count = len(clean)

    if char_count >= 1000:
        return "full", char_count
    elif char_count >= 300:
        return "partial", char_count
    elif char_count >= 50:
        return "snippet", char_count
    else:
        return "empty", char_count


# =====================================================================
# Duplicate / Syndication Detection
# =====================================================================

def detect_content_duplicates(
    sources: List[Dict[str, Any]]
) -> Dict[str, str]:
    """
    Detect duplicate or syndicated sources by content fingerprinting.
    Returns dict mapping duplicate source_id -> original source_id.
    """
    fingerprints: Dict[str, str] = {}  # fingerprint -> first source_id
    duplicates: Dict[str, str] = {}  # duplicate_source_id -> original_source_id

    for src in sources:
        text = src.get("text", "") or src.get("snippet", "")
        url = src.get("url", "")
        source_id = src.get("source_id", "")

        if not source_id:
            source_id = hashlib.sha256(url.lower().encode("utf-8")).hexdigest()[:16]

        if not text or len(text.strip()) < 50:
            continue

        # Content fingerprint: normalized first 500 chars
        normalized = re.sub(r"\s+", " ", text[:500].lower().strip())
        fp = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]

        if fp in fingerprints:
            duplicates[source_id] = fingerprints[fp]
        else:
            fingerprints[fp] = source_id

    return duplicates


# =====================================================================
# Composite Quality Score
# =====================================================================

# Weights for each dimension in the final composite score.
# These are deterministic and explicit — no LLM involvement.
SCORE_WEIGHTS = {
    "source_type": 0.25,
    "authority": 0.20,
    "freshness": 0.20,
    "extraction": 0.15,
    "duplicate_penalty": 0.10,
    "https_bonus": 0.05,
    "date_available": 0.05,
}

# Source type base scores
SOURCE_TYPE_SCORES: Dict[str, float] = {
    "official": 1.0,
    "academic": 0.95,
    "news": 0.80,
    "industry": 0.75,
    "company": 0.60,
    "general": 0.45,
    "unknown": 0.20,
}

FRESHNESS_SCORES: Dict[str, float] = {
    "current": 1.0,
    "recent": 0.85,
    "aging": 0.55,
    "stale": 0.25,
    "undated": 0.40,
}

EXTRACTION_SCORES: Dict[str, float] = {
    "full": 1.0,
    "partial": 0.70,
    "snippet": 0.40,
    "empty": 0.10,
}


def compute_quality_score(profile: SourceQualityProfile) -> float:
    """
    Compute composite quality score from individual dimensions.
    Returns a float in [0.0, 1.0].
    """
    type_score = SOURCE_TYPE_SCORES.get(profile.source_type, 0.2)
    freshness_score = FRESHNESS_SCORES.get(profile.freshness, 0.4)
    extraction_score = EXTRACTION_SCORES.get(profile.extraction_quality, 0.1)
    authority = profile.authority_score
    https_bonus = 1.0 if profile.url.startswith("https://") else 0.0
    date_bonus = 1.0 if profile.publication_date != "N/A" else 0.0
    duplicate_penalty = 0.0 if not profile.is_duplicate else 1.0

    composite = (
        SCORE_WEIGHTS["source_type"] * type_score +
        SCORE_WEIGHTS["authority"] * authority +
        SCORE_WEIGHTS["freshness"] * freshness_score +
        SCORE_WEIGHTS["extraction"] * extraction_score +
        SCORE_WEIGHTS["https_bonus"] * https_bonus +
        SCORE_WEIGHTS["date_available"] * date_bonus -
        SCORE_WEIGHTS["duplicate_penalty"] * duplicate_penalty
    )

    # Clamp to [0.0, 1.0]
    return round(max(0.0, min(1.0, composite)), 3)


def score_to_tier(score: float) -> str:
    """Map composite score to human-readable quality tier."""
    if score >= 0.80:
        return "excellent"
    elif score >= 0.60:
        return "good"
    elif score >= 0.40:
        return "adequate"
    elif score >= 0.20:
        return "low"
    else:
        return "poor"


# =====================================================================
# Full Source Profiling Pipeline
# =====================================================================

def profile_source(
    url: str,
    title: str = "",
    text: str = "",
    subtask_id: str = "general",
    source_id: str = "",
    publication_date: str = "",
    reference_date: Optional[datetime] = None,
    is_duplicate: bool = False,
    duplicate_of: str = "",
) -> SourceQualityProfile:
    """
    Build a complete SourceQualityProfile for a single source.
    Pure deterministic — no LLM calls.
    """
    domain = extract_domain_from_url(url)
    if not source_id:
        source_id = hashlib.sha256(url.lower().encode("utf-8")).hexdigest()[:16] if url else "unknown"

    source_type = classify_source_type(url, domain)
    pub_date = publication_date or extract_publication_date_enhanced(text, url)
    retrieval_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    freshness_label, freshness_days = calculate_freshness(pub_date, reference_date)
    authority, authority_labels = compute_authority_score(url, domain)
    extraction_label, char_count = assess_extraction_quality(text)

    penalties: List[str] = []
    if is_duplicate:
        penalties.append(f"duplicate_of:{duplicate_of}")
    if freshness_label == "stale":
        penalties.append("stale_content")
    if extraction_label == "empty":
        penalties.append("no_extracted_content")
    if pub_date == "N/A":
        penalties.append("missing_publication_date")
    if not url.startswith("https://"):
        penalties.append("no_https")

    profile = SourceQualityProfile(
        source_id=source_id,
        url=url,
        title=title or "Web Document",
        domain=domain,
        source_type=source_type,
        publication_date=pub_date,
        retrieval_date=retrieval_date,
        freshness=freshness_label,
        freshness_days=freshness_days,
        authority_indicators=authority_labels,
        authority_score=authority,
        extraction_quality=extraction_label,
        extraction_char_count=char_count,
        is_duplicate=is_duplicate,
        duplicate_of=duplicate_of,
        subtask_id=subtask_id,
        penalties=penalties,
    )

    profile.quality_score = compute_quality_score(profile)
    profile.quality_tier = score_to_tier(profile.quality_score)

    return profile


def profile_all_sources(
    sources: List[Dict[str, Any]],
    session_id: str = "",
    reference_date: Optional[datetime] = None,
) -> SourceQualityReport:
    """
    Profile and score all discovered sources for a research session.
    Detects duplicates, ranks by quality, and compiles distribution statistics.
    Sources are NEVER deleted — only ranked.
    """
    # Detect duplicates first
    duplicates = detect_content_duplicates(sources)

    profiles: List[SourceQualityProfile] = []
    for src in sources:
        url = src.get("url", "")
        sid = src.get("source_id", "")
        if not sid:
            sid = hashlib.sha256(url.lower().encode("utf-8")).hexdigest()[:16] if url else "unknown"

        is_dup = sid in duplicates
        dup_of = duplicates.get(sid, "")

        p = profile_source(
            url=url,
            title=src.get("title", ""),
            text=src.get("text", "") or src.get("snippet", ""),
            subtask_id=src.get("subtask_id", "general"),
            source_id=sid,
            publication_date=src.get("publication_date", ""),
            reference_date=reference_date,
            is_duplicate=is_dup,
            duplicate_of=dup_of,
        )
        profiles.append(p)

    # Sort by quality_score descending (rank, not delete)
    profiles.sort(key=lambda p: p.quality_score, reverse=True)

    # Compile distributions
    type_dist: Dict[str, int] = {}
    fresh_dist: Dict[str, int] = {}
    quality_dist: Dict[str, int] = {}

    for p in profiles:
        type_dist[p.source_type] = type_dist.get(p.source_type, 0) + 1
        fresh_dist[p.freshness] = fresh_dist.get(p.freshness, 0) + 1
        quality_dist[p.quality_tier] = quality_dist.get(p.quality_tier, 0) + 1

    avg_quality = sum(p.quality_score for p in profiles) / len(profiles) if profiles else 0.0

    return SourceQualityReport(
        session_id=session_id,
        total_sources=len(profiles),
        scored_sources=profiles,
        type_distribution=type_dist,
        freshness_distribution=fresh_dist,
        quality_distribution=quality_dist,
        average_quality=round(avg_quality, 3),
        duplicate_count=len(duplicates),
        undated_count=sum(1 for p in profiles if p.freshness == "undated"),
        stale_count=sum(1 for p in profiles if p.freshness == "stale"),
    )


# =====================================================================
# Integration Helpers
# =====================================================================

def rank_retrieved_evidence(
    evidence_list: List[Dict[str, Any]],
    quality_profiles: Dict[str, SourceQualityProfile],
) -> List[Dict[str, Any]]:
    """
    Re-rank retrieved evidence by combining semantic similarity with source quality.
    Blends similarity_score (70%) with quality_score (30%) for final ranking.

    Does NOT remove any evidence — only reorders.
    """
    ranked = []
    for ev in evidence_list:
        sid = ev.get("source_id", "")
        sim = float(ev.get("similarity_score", 0.0))
        quality = 0.5  # default if profile not found

        if sid in quality_profiles:
            quality = quality_profiles[sid].quality_score

        combined = (0.70 * sim) + (0.30 * quality)
        enriched = dict(ev)
        enriched["quality_score"] = quality
        enriched["combined_score"] = round(combined, 4)
        ranked.append(enriched)

    ranked.sort(key=lambda x: x["combined_score"], reverse=True)
    return ranked


def format_source_quality_briefing(report: SourceQualityReport) -> str:
    """
    Format a human-readable source quality briefing for inclusion
    in the evidence section or for frontend display.
    """
    if not report.scored_sources:
        return "No sources profiled."

    lines = [
        "## Source Quality Analysis",
        f"**Total Sources**: {report.total_sources}",
        f"**Average Quality**: {report.average_quality:.1%}",
        f"**Duplicates Detected**: {report.duplicate_count}",
        f"**Undated Sources**: {report.undated_count}",
        f"**Stale Sources (>5yr)**: {report.stale_count}",
        "",
        "### Type Distribution",
    ]

    for t, count in sorted(report.type_distribution.items(), key=lambda x: -x[1]):
        lines.append(f"- {t}: {count}")

    lines.append("")
    lines.append("### Top Sources by Quality")
    for i, p in enumerate(report.scored_sources[:10], 1):
        star = "⭐" if p.quality_tier in ("excellent", "good") else ""
        lines.append(
            f"{i}. **{p.title}** ({p.domain}) — "
            f"`{p.source_type}` | {p.freshness} | "
            f"Score: {p.quality_score:.0%} [{p.quality_tier}] {star}"
        )

    return "\n".join(lines)
