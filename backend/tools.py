import logging
import re
from typing import List, Optional, Tuple, Dict, Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from ddgs import DDGS
from langchain.tools import tool
import requests

from resilience import (
    execute_with_retry,
    execute_with_timeout,
    get_search_circuit_breaker,
    get_domain_circuit_registry,
    SearchError,
    SearchTimeoutError,
    HttpScrapeError,
    ScrapeTimeoutError,
    MalformedContentError,
    CircuitBreakerOpenError,
)

logger = logging.getLogger("synapse.tools")

SEARCH_TIMEOUT_SECONDS = 8.0
SCRAPE_TIMEOUT_SECONDS = 8.0
MAX_SCRAPED_CHARS = 5000


def _simplify_query(query: str) -> str:
    """Strip special syntax, quotes, and punctuation for fallback search."""
    clean = re.sub(r'["\'\(\)\[\]\{\}\+\-\*~`]', " ", query)
    tokens = [t.strip() for t in clean.split() if len(t.strip()) > 2]
    # Remove common filler words
    stopwords = {"what", "when", "where", "which", "about", "their", "there", "these", "those", "have", "with"}
    filtered = [t for t in tokens if t.lower() not in stopwords]
    return " ".join(filtered[:6]) if filtered else query.strip()


def _raw_ddgs_call(query: str, max_results: int) -> list:
    """Direct DDGS invocation wrapped for timeout and retry handlers."""
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=max_results))


def search_web_resilient(query: str, max_results: int = 5) -> List[dict]:
    """
    Search DuckDuckGo with circuit breaker, timeout, retry, and query simplification fallback.
    Returns list of dicts: [{"title": ..., "href": ..., "body": ...}]
    """
    breaker = get_search_circuit_breaker()

    # 1. Primary query attempt
    def _attempt_search(q: str):
        return breaker.execute(
            lambda: execute_with_timeout(
                lambda: execute_with_retry(
                    lambda: _raw_ddgs_call(q, max_results),
                    max_retries=2,
                    initial_delay=0.4,
                    backoff_factor=1.5,
                    operation_name=f"DDGS Search ('{q[:30]}')",
                ),
                timeout_seconds=SEARCH_TIMEOUT_SECONDS,
                operation_name="DDGS Search Timeout",
                timeout_exception_cls=SearchTimeoutError,
                target=q,
            )
        )

    try:
        results = _attempt_search(query)
        if results:
            return results
    except Exception as e:
        logger.warning("Primary search failed for '%s': %s. Attempting fallback query...", query, str(e))

    # 2. Fallback query attempt with simplified terms
    fallback_q = _simplify_query(query)
    if fallback_q and fallback_q.lower() != query.lower():
        try:
            logger.info("Executing search fallback with query: '%s'", fallback_q)
            results = _attempt_search(fallback_q)
            if results:
                return results
        except Exception as e2:
            logger.error("Fallback search also failed for '%s': %s", fallback_q, str(e2))

    return []


@tool
def web_search(query: str) -> str:
    """
    Search DuckDuckGo and return the top search results.
    Guarantees resilient execution with fallback and timeouts.
    """
    results = search_web_resilient(query, max_results=5)
    if not results:
        return "No search results found or search provider temporarily unavailable."

    output = []
    for result in results:
        output.append(
            f"""
Title : {result.get("title")}

URL : {result.get("href")}

Snippet :
{result.get("body")}
"""
        )
    return "\n-----------------------------\n".join(output)


def multi_web_search(queries: list, max_results_per_query: int = 3) -> str:
    """
    Search DuckDuckGo across multiple queries, deduplicating URLs.
    Includes circuit breaker and per-query fallback.
    """
    output = []
    seen_urls = set()

    for query in queries:
        clean_q = str(query).strip()
        if not clean_q:
            continue
        try:
            results = search_web_resilient(clean_q, max_results=max_results_per_query)
            for result in results:
                href = result.get("href", "")
                if href and href not in seen_urls:
                    seen_urls.add(href)
                    output.append(
                        f"""
Title : {result.get("title")}

URL : {href}

Snippet :
{result.get("body")}
"""
                    )
        except Exception as e:
            logger.warning("Query '%s' in multi_web_search failed: %s", clean_q, str(e))
            continue

    if not output and queries:
        return web_search.invoke(queries[0])

    return "\n-----------------------------\n".join(output)


def scrape_url_resilient(url: str, timeout: float = SCRAPE_TIMEOUT_SECONDS) -> Tuple[bool, str, Optional[int]]:
    """
    Scrape webpage with domain-level circuit breaker, timeouts, HTTP status handling,
    binary/malformed content prevention, and HTML tag sanitization.

    Returns:
        (success: bool, content_or_error_message: str, http_status_code: Optional[int])
    """
    domain = ""
    try:
        domain = urlparse(url).netloc.replace("www.", "").lower()
    except Exception:
        domain = "unknown"

    # Skip domains that never provide useful scraped text for research
    SKIP_DOMAINS = {"youtube.com", "youtu.be", "vimeo.com", "tiktok.com",
                    "twitter.com", "x.com", "instagram.com", "facebook.com"}
    if any(sd in domain for sd in SKIP_DOMAINS):
        return False, f"Skipped non-scrapable media domain: {domain}", None

    domain_breaker = get_domain_circuit_registry().get_breaker(domain)
    if not domain_breaker.allow_request():
        return False, f"Domain circuit breaker is OPEN for {domain} (repeated failures)", None

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    def _http_fetch():
        with requests.get(url, timeout=timeout, headers=headers) as resp:
            status = resp.status_code

            # Check for non-retryable HTTP errors
            if status in (401, 403, 404, 410, 451):
                domain_breaker.record_failure()
                return False, f"HTTP {status} - Content not accessible", status

            if status != 200:
                domain_breaker.record_failure()
                return False, f"HTTP {status} Server Error", status

            # Check Content-Type to avoid binary/PDF/image downloads
            content_type = resp.headers.get("Content-Type", "").lower()
            if any(b in content_type for b in ["pdf", "image", "audio", "video", "zip", "octet-stream"]):
                return False, f"Malformed/Binary content ignored ({content_type})", status

            # Check Content-Length to avoid downloading excessively large files (> 5MB)
            content_length = resp.headers.get("Content-Length")
            if content_length and content_length.isdigit() and int(content_length) > 5 * 1024 * 1024:
                return False, f"Content size ({content_length} bytes) exceeds limit", status

            html_text = resp.text
            if not html_text:
                return False, "Empty response from server", status

            # Check for raw binary / compressed bytes (e.g. gzip magic bytes or unhandled zip)
            if html_text.startswith("\x1f\x8b") or html_text.startswith("PK\x03\x04") or "\x00" in html_text[:500]:
                return False, "Binary or compressed stream detected instead of readable text", status

            # Parse and sanitize HTML
            try:
                soup = BeautifulSoup(html_text, "html.parser")
            except Exception as e:
                return False, f"Malformed HTML parse error: {str(e)}", status

            # Remove non-content elements aggressively
            for tag in soup(["script", "style", "nav", "footer", "header", "aside",
                             "noscript", "svg", "form", "button", "iframe", "object",
                             "embed", "canvas", "dialog", "menu", "template"]):
                tag.decompose()

            # Remove elements by role/class patterns that typically contain non-content
            for el in soup.find_all(attrs={"role": re.compile(r"banner|navigation|complementary|contentinfo")}):
                el.decompose()
            for el in soup.find_all(class_=re.compile(r"cookie|consent|sidebar|share|social|newsletter|subscribe|popup|modal|ad-|ads-|advert", re.IGNORECASE)):
                el.decompose()

            # Prefer article/main content if available
            main_content = soup.find("article") or soup.find("main") or soup.find(attrs={"role": "main"})
            if main_content and len(main_content.get_text(strip=True)) > 200:
                text = main_content.get_text(separator=" ", strip=True)
            else:
                text = soup.get_text(separator=" ", strip=True)
            clean_text = re.sub(r"\s+", " ", text).strip()

            if not clean_text or len(clean_text) < 30:
                return False, "Empty or insufficient readable content after markup stripping", status

            # Validate printable character density to ensure zero corrupted binary gibberish passes through
            sample = clean_text[:500]
            printable_count = sum(1 for ch in sample if ch.isprintable() or ch in "\n\r\t")
            if printable_count / max(1, len(sample)) < 0.85:
                return False, "Binary or corrupted non-text payload detected", status

            domain_breaker.record_success()
            return True, clean_text[:MAX_SCRAPED_CHARS], status

    try:
        return execute_with_timeout(
            _http_fetch,
            timeout_seconds=timeout + 2.0,
            operation_name=f"HTTP Scrape ({domain})",
            timeout_exception_cls=ScrapeTimeoutError,
            target=url,
        )
    except ScrapeTimeoutError as e:
        domain_breaker.record_failure()
        return False, f"Scrape timeout exceeded: {str(e)}", 408
    except Exception as e:
        domain_breaker.record_failure()
        return False, f"Scrape network error: {str(e)}", None


@tool
def scrape_url(url: str) -> str:
    """
    Scrape webpage and return readable text with full fault tolerance.
    """
    success, result, _ = scrape_url_resilient(url)
    if success:
        return result
    return f"Unable to scrape.\n{result}"
