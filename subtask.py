import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, Set
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from tools import search_web_resilient, scrape_url_resilient
from resilience import (
    SynapseBaseError,
    SearchError,
    ScrapingError,
    HttpScrapeError,
    ScrapeTimeoutError,
    MalformedContentError,
    CircuitBreakerOpenError,
)

# -----------------------------
# Logger Configuration
# -----------------------------
logger = logging.getLogger("synapse.subtask")
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
# Concurrency & Resilience Config
# -----------------------------
MAX_CONCURRENT_SUBTASKS = int(os.getenv("MAX_CONCURRENT_SUBTASKS", "3"))
SUBTASK_TIMEOUT_SECONDS = int(os.getenv("SUBTASK_TIMEOUT_SECONDS", "30"))
MAX_SUBTASK_RETRIES = int(os.getenv("MAX_SUBTASK_RETRIES", "2"))
SCRAPE_TIMEOUT_SECONDS = int(os.getenv("SCRAPE_TIMEOUT_SECONDS", "8"))
MAX_SCRAPED_CHARS = int(os.getenv("MAX_SCRAPED_CHARS", "4000"))


# -----------------------------
# Data Models
# -----------------------------
class DiscoveredSource(BaseModel):
    """A web source discovered during subtask search."""
    title: str = "Web Source"
    url: str
    snippet: str = ""
    domain: str = ""
    subtask_id: str
    question: str


class ExtractedDocument(BaseModel):
    """Full-text content extracted from a webpage during subtask execution."""
    url: str
    title: str = "Web Document"
    text: str
    char_count: int
    subtask_id: str
    question: str


class Subtask(BaseModel):
    """
    Independent research subtask.
    Tracks query, search results, extracted evidence, status, failed sources, and errors.
    """
    subtask_id: str
    question: str
    search_queries: List[str] = Field(default_factory=list)
    discovered_urls: List[DiscoveredSource] = Field(default_factory=list)
    extracted_documents: List[ExtractedDocument] = Field(default_factory=list)
    failed_sources: List[Dict[str, Any]] = Field(default_factory=list)
    status: str = "pending"  # "pending" | "running" | "completed" | "failed" | "degraded"
    degraded: bool = False
    warnings: List[str] = Field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


# -----------------------------
# Thread-Safe URL Registry
# -----------------------------
class URLRegistry:
    """Thread-safe registry to deduplicate URLs across concurrent subtasks."""

    def __init__(self):
        self._lock = threading.Lock()
        self._seen_urls: Set[str] = set()
        self._scraped_urls: Set[str] = set()

    def normalize(self, url: str) -> str:
        """Normalize URL for consistent deduplication."""
        try:
            parsed = urlparse(url.strip())
            netloc = parsed.netloc.lower().replace("www.", "")
            path = parsed.path.rstrip("/")
            return f"{parsed.scheme}://{netloc}{path}"
        except Exception:
            return url.strip().lower()

    def register(self, url: str) -> bool:
        """Register a URL. Returns True if newly added, False if duplicate."""
        norm = self.normalize(url)
        with self._lock:
            if norm in self._seen_urls:
                return False
            self._seen_urls.add(norm)
            return True

    def is_seen(self, url: str) -> bool:
        norm = self.normalize(url)
        with self._lock:
            return norm in self._seen_urls

    def register_scraped(self, url: str) -> bool:
        norm = self.normalize(url)
        with self._lock:
            if norm in self._scraped_urls:
                return False
            self._scraped_urls.add(norm)
            return True


# -----------------------------
# Single Subtask Execution with Failover & Graceful Degradation
# -----------------------------
def execute_subtask(
    subtask: Subtask,
    url_registry: Optional[URLRegistry] = None,
    timeout: int = SUBTASK_TIMEOUT_SECONDS,
) -> Subtask:
    """
    Execute a single research subtask with production-grade fault tolerance:
    1. Runs focused search queries with query-simplification fallback on empty/timeout.
    2. Deduplicates discovered URLs.
    3. Attempts scraping candidate URLs with candidate failover:
       - If candidate URL 1 fails (HTTP 403, 404, timeout, or blocked), records URL as failed source
         and immediately fails over to candidate URL 2 or 3.
       - NEVER allows one failed URL to abort the subtask.
    4. If all full-text page scrapes fail, gracefully degrades to search snippet evidence
       so research can continue with grounded factual evidence.
    5. Isolated execution guarantees zero crash propagation.
    """
    subtask.status = "running"
    logger.info("Starting subtask [%s]: '%s'", subtask.subtask_id, subtask.question)
    registry = url_registry or URLRegistry()

    start_time = time.time()
    try:
        discovered: List[DiscoveredSource] = []
        queries = subtask.search_queries or [subtask.question]

        # 1. Search queries for this subtask with resilient search helper
        for q in queries:
            if time.time() - start_time > timeout:
                logger.warning("Subtask [%s] reached timeout limit during search phase", subtask.subtask_id)
                subtask.warnings.append(f"Search phase truncated due to timeout at {timeout}s")
                break

            results = search_web_resilient(q, max_results=3)
            for res in results:
                raw_url = res.get("href", "")
                if not raw_url or not raw_url.startswith("http"):
                    continue

                if registry.register(raw_url):
                    domain = ""
                    try:
                        domain = urlparse(raw_url).netloc.replace("www.", "")
                    except Exception:
                        domain = "web"

                    source = DiscoveredSource(
                        title=res.get("title") or "Web Source",
                        url=raw_url,
                        snippet=res.get("body") or "",
                        domain=domain,
                        subtask_id=subtask.subtask_id,
                        question=subtask.question,
                    )
                    discovered.append(source)

        subtask.discovered_urls = discovered
        logger.info(
            "Subtask [%s] discovered %d unique sources across queries",
            subtask.subtask_id, len(discovered)
        )

        # 2. Extract Document with Candidate Failover
        extracted: List[ExtractedDocument] = []
        failed_sources: List[Dict[str, Any]] = []

        if discovered:
            # Candidates to try in sequence
            candidates = [s for s in discovered if registry.register_scraped(s.url)]
            if not candidates:
                candidates = discovered[:3]

            scrape_successful = False
            for cand in candidates:
                # Check elapsed time
                if time.time() - start_time > timeout:
                    logger.warning("Subtask [%s] reached timeout limit during scraping phase", subtask.subtask_id)
                    subtask.warnings.append("Scraping phase timed out before all candidates could be probed")
                    break

                logger.info("Subtask [%s] attempting scrape for candidate: %s", subtask.subtask_id, cand.url)
                success, content_or_err, status_code = scrape_url_resilient(cand.url, timeout=SCRAPE_TIMEOUT_SECONDS)

                if success and content_or_err:
                    doc = ExtractedDocument(
                        url=cand.url,
                        title=cand.title,
                        text=content_or_err,
                        char_count=len(content_or_err),
                        subtask_id=subtask.subtask_id,
                        question=subtask.question,
                    )
                    extracted.append(doc)
                    scrape_successful = True
                    logger.info("Subtask [%s] successfully extracted document from %s (%d chars)", subtask.subtask_id, cand.url, len(content_or_err))
                    # Successfully acquired document for this subtask; break out
                    break
                else:
                    # Record failed source transparently
                    fail_rec = {
                        "url": cand.url,
                        "title": cand.title,
                        "domain": cand.domain,
                        "reason": content_or_err,
                        "status_code": status_code,
                        "subtask_id": subtask.subtask_id,
                        "timestamp": time.time(),
                    }
                    failed_sources.append(fail_rec)
                    logger.warning(
                        "Subtask [%s] candidate URL failed: %s (%s). Failing over to next candidate...",
                        subtask.subtask_id, cand.url, content_or_err
                    )

            # 3. Graceful degradation: if full-text scraping failed on all candidates, use search snippet fallback
            if not scrape_successful and discovered:
                fallback_candidate = discovered[0]
                if fallback_candidate.snippet and len(fallback_candidate.snippet) > 20:
                    fallback_text = f"[Evidence derived from search result snippet]: {fallback_candidate.snippet}"
                    doc = ExtractedDocument(
                        url=fallback_candidate.url,
                        title=f"[Search Snippet] {fallback_candidate.title}",
                        text=fallback_text,
                        char_count=len(fallback_text),
                        subtask_id=subtask.subtask_id,
                        question=subtask.question,
                    )
                    extracted.append(doc)
                    subtask.degraded = True
                    subtask.warnings.append(
                        f"All candidate URLs failed extraction for subtask {subtask.subtask_id}; gracefully degraded to verified search snippet."
                    )
                    logger.warning("Subtask [%s] DEGRADED to search snippet fallback for %s", subtask.subtask_id, fallback_candidate.url)

        subtask.extracted_documents = extracted
        subtask.failed_sources = failed_sources

        if subtask.degraded:
            subtask.status = "degraded"
        elif extracted or discovered:
            subtask.status = "completed"
        else:
            subtask.status = "completed"
            subtask.warnings.append(f"No search results or extracted documents for '{subtask.question}'")

        logger.info(
            "Subtask [%s] FINISHED (%s): %d sources, %d docs, %d failed URLs",
            subtask.subtask_id, subtask.status, len(subtask.discovered_urls),
            len(subtask.extracted_documents), len(subtask.failed_sources)
        )
        return subtask

    except Exception as e:
        logger.error("Subtask [%s] unexpected exception: %s", subtask.subtask_id, str(e), exc_info=True)
        subtask.status = "failed"
        subtask.error = str(e)
        return subtask


# -----------------------------
# Concurrent Subtask Orchestrator with Thread Isolation
# -----------------------------
def execute_subtasks_concurrently(
    subtasks: List[Subtask],
    max_concurrency: int = MAX_CONCURRENT_SUBTASKS,
    timeout: int = SUBTASK_TIMEOUT_SECONDS,
    on_subtask_progress: Optional[Callable[[Subtask], None]] = None,
) -> List[Subtask]:
    """
    Execute multiple independent research subtasks concurrently using ThreadPoolExecutor.
    Enforces thread-level isolation so individual failures never crash the batch.
    """
    if not subtasks:
        return []

    concurrency = max(1, min(max_concurrency, len(subtasks)))
    logger.info(
        "Launching %d subtasks concurrently (concurrency_limit=%d, timeout=%ds)",
        len(subtasks), concurrency, timeout
    )

    registry = URLRegistry()
    results: List[Subtask] = []

    with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="synapse-subtask") as executor:
        future_to_subtask = {
            executor.submit(execute_subtask, st, registry, timeout): st
            for st in subtasks
        }

        for future in as_completed(future_to_subtask):
            original_st = future_to_subtask[future]
            try:
                completed_st = future.result()
                results.append(completed_st)
            except Exception as e:
                logger.error("Thread execution error for subtask [%s]: %s", original_st.subtask_id, str(e))
                original_st.status = "failed"
                original_st.error = str(e)
                results.append(original_st)

            if on_subtask_progress:
                try:
                    on_subtask_progress(results[-1])
                except Exception as cb_err:
                    logger.warning("Error in progress callback: %s", str(cb_err))

    # Maintain original ordering by subtask_id
    id_order = {st.subtask_id: idx for idx, st in enumerate(subtasks)}
    results.sort(key=lambda s: id_order.get(s.subtask_id, 0))

    completed_count = sum(1 for s in results if s.status in ("completed", "degraded"))
    failed_count = sum(1 for s in results if s.status == "failed")
    logger.info(
        "All subtasks finished: %d completed/degraded, %d failed out of %d total",
        completed_count, failed_count, len(results)
    )
    return results
