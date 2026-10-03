import hashlib
import logging
import os
import re
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import chromadb
from pydantic import BaseModel, Field

# -----------------------------
# Logger Configuration
# -----------------------------
logger = logging.getLogger("synapse.retrieval")
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
# Configuration
# -----------------------------
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", os.path.join(os.path.dirname(__file__), "chroma_db"))
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
DEFAULT_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "16"))
CHUNK_SIZE = int(os.getenv("EVIDENCE_CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("EVIDENCE_CHUNK_OVERLAP", "150"))
COLLECTION_NAME = "synapse_evidence_chunks"


# -----------------------------
# Data Models
# -----------------------------
class SourceChunk(BaseModel):
    """Metadata and content for a single indexed evidence chunk."""
    chunk_id: str
    source_id: str
    session_id: str
    subtask_id: str
    url: str
    title: str
    domain: str
    source_type: str
    publication_date: str
    retrieval_timestamp: str
    text: str
    chunk_index: int
    char_count: int


class RetrievedEvidence(BaseModel):
    """Result of semantic retrieval from the vector store."""
    chunk_id: str
    source_id: str
    session_id: str
    subtask_id: str
    url: str
    title: str
    domain: str
    source_type: str
    publication_date: str
    text: str
    similarity_score: float  # Normalized score (higher is more similar)


# -----------------------------
# Document Cleaning & Helpers
# -----------------------------
def clean_boilerplate(text: str) -> str:
    """Remove boilerplate phrases, navigation residue, and normalize whitespace."""
    if not text:
        return ""

    # Common website boilerplate patterns (non-greedy to prevent stripping real body content)
    noise_patterns = [
        r"(?i)\baccept all cookies\b[^\.\n]*[\.\n]?",
        r"(?i)\bcookie policy\b[^\.\n]*[\.\n]?",
        r"(?i)\bprivacy preferences\b[^\.\n]*[\.\n]?",
        r"(?i)\bsign up for (our )?newsletter\b[^\.\n]*[\.\n]?",
        r"(?i)\ball rights reserved\b[^\.\n]*[\.\n]?",
        r"(?i)\bsubscribe to newsletter\b[^\.\n]*[\.\n]?",
        r"(?i)\bshare on (facebook|twitter|linkedin)\b",
        r"(?i)\bfollow us on (twitter|facebook|linkedin|instagram)\b",
    ]
    cleaned = text
    for pattern in noise_patterns:
        cleaned = re.sub(pattern, " ", cleaned)

    # Normalize whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def extract_domain(url: str) -> str:
    """Extract domain from URL, with fallback for scheme-less strings."""
    if not url:
        return "web"
    try:
        if "://" not in url and not url.startswith("//"):
            url_to_parse = f"http://{url}"
        else:
            url_to_parse = url
        parsed = urlparse(url_to_parse)
        netloc = parsed.netloc or parsed.path.split("/")[0]
        domain = netloc.replace("www.", "").lower()
        if "." in domain:
            return domain
        return "web"
    except Exception:
        return "web"


def infer_source_type(url: str, domain: str) -> str:
    """Classify source type based on URL and domain indicators."""
    lower_domain = domain.lower()
    lower_url = url.lower()

    if any(lower_domain.endswith(t) for t in [".gov", ".gov.in", "who.int", "cdc.gov", "nih.gov", "niti.gov.in"]):
        return "official"
    if any(k in lower_domain for k in [".edu", ".ac.", "arxiv.org", "ncbi.nlm.nih.gov", "nature.com", "sciencedirect.com", "biorxiv.org", "pubmed", "cell.com"]):
        return "academic"
    if any(k in lower_domain for k in ["reuters.com", "bloomberg.com", "bbc.com", "thehindu.com", "techcrunch.com", "forbes.com", "economist.com", "nytimes.com", "wsj.com"]):
        return "news"
    if any(k in lower_domain for k in ["mckinsey.com", "gartner.com", "deloitte.com", "pwc.com", "statista.com", "accenture.com"]):
        return "industry"
    return "general"


def extract_publication_date(text: str) -> str:
    """Attempt heuristic extraction of publication dates (e.g. YYYY-MM-DD or Month DD, YYYY)."""
    # Look for ISO date: 2024-05-12
    iso_match = re.search(r"\b(20[12]\d[-/.](?:0[1-9]|1[0-2])[-/.](?:0[1-9]|[12]\d|3[01]))\b", text[:1000])
    if iso_match:
        return iso_match.group(1)

    # Look for verbal date: May 15, 2024 or 15 May 2024
    verbal_match = re.search(
        r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+20[12]\d\b",
        text[:1000],
        re.IGNORECASE
    )
    if verbal_match:
        return verbal_match.group(0)

    return "N/A"


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP
) -> List[str]:
    """
    Split text into meaningful, overlapping chunks.
    Respects sentence and paragraph boundaries wherever possible.
    """
    cleaned = clean_boilerplate(text)
    if not cleaned:
        return []

    if len(cleaned) <= chunk_size:
        return [cleaned]

    # Split into candidate sentences/segments
    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    chunks: List[str] = []
    current_chunk = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        if not current_chunk:
            current_chunk = sentence
        elif len(current_chunk) + len(sentence) + 1 <= chunk_size:
            current_chunk += " " + sentence
        else:
            chunks.append(current_chunk)
            # Apply overlap from the tail of current_chunk
            overlap_prefix = current_chunk[-chunk_overlap:] if len(current_chunk) > chunk_overlap else current_chunk
            current_chunk = overlap_prefix + " " + sentence

    if current_chunk and (not chunks or current_chunk != chunks[-1]):
        chunks.append(current_chunk)

    # Filter out empty or trivially tiny fragments
    valid_chunks = [c.strip() for c in chunks if len(c.strip()) >= 50]
    return valid_chunks or [cleaned[:chunk_size]]


# -----------------------------
# Dedicated Evidence Retrieval Service
# -----------------------------
class EvidenceRetrievalService:
    """
    Persistent Evidence Retrieval Layer for SYNAPSE AI.
    Handles embedding generation, ChromaDB vector indexing, metadata preservation,
    duplicate prevention, and session-isolated semantic retrieval.
    """

    _instance = None
    _lock = threading.Lock()

    def __init__(self, persist_dir: Optional[str] = None, enable_embeddings: Optional[bool] = None):
        self.persist_dir = persist_dir or CHROMA_PERSIST_DIR
        self._embedder: Optional[Any] = None
        self._chroma_client: Optional[chromadb.PersistentClient] = None
        self._collection = None
        self._init_failed = False
        self._init_error = None
        self._memory_chunks: Dict[str, List[SourceChunk]] = {}
        self._is_degraded = False
        if enable_embeddings is None:
            enable_embeddings = os.getenv("ENABLE_EMBEDDINGS", "1").lower() not in ("0", "false", "no", "off")
        self._enable_embeddings = enable_embeddings
        self._initialize()

    def _initialize(self):
        """Initialize ChromaDB and SentenceTransformer with graceful fallback."""
        if not self._enable_embeddings:
            logger.info("Embeddings disabled via configuration. Using in-memory lexical retrieval.")
            return

        try:
            logger.info("Initializing ChromaDB PersistentClient at '%s'...", self.persist_dir)
            os.makedirs(self.persist_dir, exist_ok=True)
            self._chroma_client = chromadb.PersistentClient(path=self.persist_dir)
            self._collection = self._chroma_client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"description": "SYNAPSE AI Persistent Evidence Store"}
            )

            logger.info("Loading SentenceTransformer model '%s'...", EMBEDDING_MODEL_NAME)
            from sentence_transformers import SentenceTransformer
            try:
                # Fast path: load from local cache first (0.3s) without blocking on HuggingFace network checks
                self._embedder = SentenceTransformer(EMBEDDING_MODEL_NAME, local_files_only=True)
            except Exception:
                # Fallback to online download if model isn't yet cached locally
                self._embedder = SentenceTransformer(EMBEDDING_MODEL_NAME)
            logger.info("Evidence Retrieval Service initialized successfully.")
        except Exception as e:
            self._init_failed = True
            self._init_error = str(e)
            self._is_degraded = True
            logger.error("Failed to initialize vector store or embedder: %s. Fallback mode enabled.", str(e))

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding vector for a string with timeout and error protection."""
        if self._embedder is None or self._init_failed:
            return None
        try:
            from resilience import execute_with_timeout, EmbeddingError
            def _encode():
                emb = self._embedder.encode(text, convert_to_numpy=True)
                return emb.tolist()
            return execute_with_timeout(_encode, timeout_seconds=10.0, operation_name="Embedding Encode", timeout_exception_cls=EmbeddingError)
        except Exception as e:
            logger.warning("Embedding generation timed out or failed: %s. Proceeding without embedding.", str(e))
            return None

    def index_document(
        self,
        url: str,
        title: str,
        text: str,
        session_id: str,
        subtask_id: str = "general",
        publication_date: Optional[str] = None,
    ) -> List[SourceChunk]:
        """
        Process, chunk, embed, and index a single document into ChromaDB.
        Guarantees duplicate prevention and metadata preservation.
        """
        if not text or not url:
            return []

        domain = extract_domain(url)
        source_id = hashlib.sha256(url.strip().lower().encode("utf-8")).hexdigest()[:16]
        source_type = infer_source_type(url, domain)
        pub_date = publication_date or extract_publication_date(text)
        retrieval_timestamp = datetime.now().isoformat()

        # Check for duplicate document in this session
        if self._collection is not None:
            try:
                existing = self._collection.get(
                    where={"$and": [{"session_id": session_id}, {"source_id": source_id}]}
                )
                if existing and existing.get("ids"):
                    logger.info("Document '%s' already indexed for session '%s'. Skipping duplicate.", url, session_id)
                    return []
            except Exception as e:
                logger.warning("Duplicate check failed: %s. Proceeding with indexing.", str(e))

        # Split into chunks
        raw_chunks = chunk_text(text)
        if not raw_chunks:
            return []

        created_chunks: List[SourceChunk] = []
        ids_to_add: List[str] = []
        docs_to_add: List[str] = []
        metadatas_to_add: List[Dict[str, Any]] = []
        embeddings_to_add: List[List[float]] = []

        for idx, chunk_str in enumerate(raw_chunks):
            chunk_id = f"{session_id}_{source_id}_chunk_{idx}"
            chunk_obj = SourceChunk(
                chunk_id=chunk_id,
                source_id=source_id,
                session_id=session_id,
                subtask_id=subtask_id,
                url=url,
                title=title or "Web Document",
                domain=domain,
                source_type=source_type,
                publication_date=pub_date,
                retrieval_timestamp=retrieval_timestamp,
                text=chunk_str,
                chunk_index=idx,
                char_count=len(chunk_str),
            )
            created_chunks.append(chunk_obj)

            ids_to_add.append(chunk_id)
            docs_to_add.append(chunk_str)
            metadatas_to_add.append({
                "chunk_id": chunk_id,
                "source_id": source_id,
                "session_id": session_id,
                "subtask_id": subtask_id,
                "url": url,
                "title": title or "Web Document",
                "domain": domain,
                "source_type": source_type,
                "publication_date": pub_date,
                "retrieval_timestamp": retrieval_timestamp,
                "chunk_index": idx,
                "char_count": len(chunk_str),
            })

            # Generate embedding
            emb = self._get_embedding(chunk_str)
            if emb:
                embeddings_to_add.append(emb)

        # Upsert into ChromaDB
        if self._collection is not None and ids_to_add:
            try:
                if len(embeddings_to_add) == len(ids_to_add):
                    self._collection.upsert(
                        ids=ids_to_add,
                        documents=docs_to_add,
                        embeddings=embeddings_to_add,
                        metadatas=metadatas_to_add
                    )
                else:
                    self._collection.upsert(
                        ids=ids_to_add,
                        documents=docs_to_add,
                        metadatas=metadatas_to_add
                    )
                logger.info("Successfully indexed %d chunks for '%s' in session '%s'", len(ids_to_add), url, session_id)
            except Exception as e:
                self._is_degraded = True
                logger.error("Failed to insert chunks into ChromaDB: %s. Using in-memory fallback.", str(e))

        # Guarantee all chunks are stored in in-memory session index for fallback
        self._memory_chunks.setdefault(session_id, []).extend(created_chunks)
        return created_chunks

    def index_extracted_documents(
        self,
        extracted_docs: List[Dict[str, Any]],
        session_id: str
    ) -> List[SourceChunk]:
        """Bulk index multiple extracted documents from concurrent subtasks."""
        all_chunks = []
        for doc in extracted_docs:
            chunks = self.index_document(
                url=doc.get("url", ""),
                title=doc.get("title", ""),
                text=doc.get("text", ""),
                session_id=session_id,
                subtask_id=doc.get("subtask_id", "general"),
                publication_date=doc.get("publication_date"),
            )
            all_chunks.extend(chunks)
        return all_chunks

    def _lexical_fallback_retrieve(
        self,
        query: str,
        session_id: str,
        top_k: int = DEFAULT_TOP_K,
        subtask_id: Optional[str] = None
    ) -> List[RetrievedEvidence]:
        """
        Graceful degradation: performs token overlap keyword retrieval
        over in-memory chunks when ChromaDB or embedding model is unavailable.
        """
        chunks = self._memory_chunks.get(session_id, [])
        if not chunks:
            return []

        if subtask_id:
            chunks = [c for c in chunks if c.subtask_id == subtask_id]

        query_tokens = set(re.findall(r"\b\w{3,}\b", query.lower()))
        scored_chunks = []

        for ch in chunks:
            ch_tokens = set(re.findall(r"\b\w{3,}\b", ch.text.lower()))
            overlap = len(query_tokens & ch_tokens)
            score = round(overlap / max(1, len(query_tokens)), 4) if query_tokens else 0.5
            scored_chunks.append((score, ch))

        # Sort descending by overlap score
        scored_chunks.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, ch in scored_chunks[:top_k]:
            results.append(RetrievedEvidence(
                chunk_id=ch.chunk_id,
                source_id=ch.source_id,
                session_id=ch.session_id,
                subtask_id=ch.subtask_id,
                url=ch.url,
                title=ch.title,
                domain=ch.domain,
                source_type=ch.source_type,
                publication_date=ch.publication_date,
                text=ch.text,
                similarity_score=max(0.1, score),
            ))

        logger.info(
            "Retrieved %d evidence chunks using in-memory lexical fallback for session '%s'",
            len(results), session_id
        )
        return results

    def retrieve_evidence(
        self,
        query: str,
        session_id: str,
        top_k: int = DEFAULT_TOP_K,
        subtask_id: Optional[str] = None
    ) -> List[RetrievedEvidence]:
        """
        Perform semantic search against ChromaDB filtered strictly by session_id.
        Degrades gracefully to lexical keyword search if ChromaDB is unavailable.
        """
        if not query or not session_id:
            return []

        if self._collection is None or not self._enable_embeddings:
            return self._lexical_fallback_retrieve(query, session_id, top_k, subtask_id)

        # Enforce session isolation filter
        where_filter: Dict[str, Any] = {"session_id": session_id}
        if subtask_id:
            where_filter = {
                "$and": [
                    {"session_id": session_id},
                    {"subtask_id": subtask_id}
                ]
            }

        try:
            query_emb = self._get_embedding(query)
            query_kwargs: Dict[str, Any] = {
                "n_results": max(1, top_k),
                "where": where_filter,
            }

            if query_emb:
                query_kwargs["query_embeddings"] = [query_emb]
            else:
                query_kwargs["query_texts"] = [query]

            results = self._collection.query(**query_kwargs)

            retrieved: List[RetrievedEvidence] = []
            if results and results.get("ids") and results["ids"][0]:
                chunk_ids = results["ids"][0]
                documents = results.get("documents", [[]])[0]
                metadatas = results.get("metadatas", [[]])[0]
                distances = results.get("distances", [[]])[0] if results.get("distances") else [0.0] * len(chunk_ids)

                for cid, doc_text, meta, dist in zip(chunk_ids, documents, metadatas, distances):
                    sim_score = round(1.0 / (1.0 + float(dist)), 4) if dist is not None else 1.0

                    evidence = RetrievedEvidence(
                        chunk_id=cid,
                        source_id=meta.get("source_id", ""),
                        session_id=meta.get("session_id", session_id),
                        subtask_id=meta.get("subtask_id", "general"),
                        url=meta.get("url", ""),
                        title=meta.get("title", "Web Document"),
                        domain=meta.get("domain", ""),
                        source_type=meta.get("source_type", "general"),
                        publication_date=meta.get("publication_date", "N/A"),
                        text=doc_text,
                        similarity_score=sim_score,
                    )
                    retrieved.append(evidence)

            if retrieved:
                logger.info(
                    "Retrieved %d evidence chunks for query '%s' in session '%s'",
                    len(retrieved), query[:50], session_id
                )
                return retrieved

            # If Chroma returned 0 results, fall back to lexical
            return self._lexical_fallback_retrieve(query, session_id, top_k, subtask_id)

        except Exception as e:
            logger.warning("ChromaDB evidence retrieval failed: %s. Using lexical fallback.", str(e))
            return self._lexical_fallback_retrieve(query, session_id, top_k, subtask_id)

    def format_evidence_briefing(self, evidence_list: List[RetrievedEvidence]) -> str:
        """
        Format retrieved evidence chunks into a clean, attributed briefing for the Writer Agent.
        Guarantees that the Writer does not consume raw messy text blindly.
        """
        if not evidence_list:
            return "No verified semantic evidence retrieved from vector store."

        blocks = []
        for i, ev in enumerate(evidence_list, 1):
            blocks.append(
                f"### [EVIDENCE CHUNK {i}] from {ev.title}\n"
                f"- **Source URL:** {ev.url}\n"
                f"- **Domain & Type:** {ev.domain} ({ev.source_type})\n"
                f"- **Subtask Attribution:** {ev.subtask_id}\n"
                f"- **Relevance Score:** {ev.similarity_score}\n"
                f"- **Verified Content Excerpt:**\n"
                f"\"{ev.text}\"\n"
            )
        return "\n".join(blocks)

    def clear_session(self, session_id: str) -> int:
        """Purge all chunks associated with a specific research session."""
        if self._collection is None or not session_id:
            return 0
        try:
            res = self._collection.get(where={"session_id": session_id})
            ids = res.get("ids", [])
            if ids:
                self._collection.delete(ids=ids)
                logger.info("Purged %d evidence chunks for session '%s'", len(ids), session_id)
            return len(ids)
        except Exception as e:
            logger.error("Failed to delete session evidence: %s", str(e))
            return 0


# Singleton accessor
_service_instance: Optional[EvidenceRetrievalService] = None

def get_retrieval_service() -> EvidenceRetrievalService:
    """Get or create singleton instance of EvidenceRetrievalService."""
    global _service_instance
    if _service_instance is None:
        with threading.Lock():
            if _service_instance is None:
                _service_instance = EvidenceRetrievalService()
    return _service_instance


def warmup_retrieval_models():
    """
    Preload and warm up SentenceTransformer model and ChromaDB client on backend startup.
    Ensures that when a user triggers a query, models are already loaded in memory.
    """
    logger.info("Pre-warming Evidence Retrieval Service and SentenceTransformer...")
    service = get_retrieval_service()
    if service._embedder is not None and not service._init_failed:
        service._get_embedding("SYNAPSE AI Warmup Embedding Query")
        logger.info("SentenceTransformer model '%s' and ChromaDB vector store pre-warmed.", EMBEDDING_MODEL_NAME)
    return service

