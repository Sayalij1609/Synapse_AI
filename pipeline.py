import logging
import os
import queue
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from agents import (
    writer_chain,
    writer_chain_fallback,
    critic_chain,
    critic_chain_fallback,
    invoke_chain_resilient,
)
from citations import (
    Source,
    build_source_registry,
    format_evidence_catalog_for_writer,
    parse_writer_claims_response,
    assemble_grounded_report,
    synthesize_deterministic_grounded_claims,
)
from planner import build_planner_agent, create_fallback_plan
from resilience import SynapseBaseError, ErrorAuditor
from retrieval import get_retrieval_service, DEFAULT_TOP_K
from state import ResearchState
from subtask import (
    Subtask,
    URLRegistry,
    execute_subtask,
    execute_subtasks_concurrently,
    MAX_CONCURRENT_SUBTASKS,
    SUBTASK_TIMEOUT_SECONDS,
)
from source_quality import (
    profile_all_sources,
    rank_retrieved_evidence,
    format_source_quality_briefing,
    SourceQualityReport,
)
from verification import (
    ResearchVerificationAgent,
    VerificationResult,
    run_deterministic_verification,
    mark_unresolved_claims,
    MAX_RESEARCH_ITERATIONS,
)
from telemetry import (
    get_session_telemetry,
    SessionTelemetryCollector,
    AgentTelemetryRecord,
)

# -----------------------------
# Logger Configuration
# -----------------------------
logger = logging.getLogger("synapse.pipeline")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Global URL registry for graph runs
_global_registry = URLRegistry()


# -----------------------------
# Helper: Extract String
# -----------------------------
def _get_response(result) -> str:
    """Extract text from LangChain responses."""
    if isinstance(result, dict) and "messages" in result and result["messages"]:
        msg = result["messages"][-1]
        if isinstance(msg, tuple):
            return msg[1]
        return getattr(msg, "content", str(msg))
    if hasattr(result, "content"):
        return result.content
    return str(result)


# -----------------------------
# LangGraph Node 1: Planner
# -----------------------------
def planner_node(state: ResearchState) -> Dict[str, Any]:
    """
    Step 1: Research Planner Agent.
    Decomposes query into structured subtasks with resilient template fallback.
    Records structured telemetry without exposing secrets.
    """
    query = state.get("original_query") or state.get("topic", "")
    session_id = state.get("session_id") or f"sess_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    logger.info("Executing Planner Node for: '%s'", query)

    telemetry = get_session_telemetry(session_id, topic=query)
    planner_model = os.getenv("GROQ_PLANNER_MODEL", "llama-3.3-70b-versatile")
    rec = telemetry.start_agent_run(
        "Planner",
        iteration_number=0,
        input_payload={"topic": query},
        model_used=planner_model
    )
    t0 = time.perf_counter()
    degraded = False

    try:
        planner = build_planner_agent()
        plan = planner.plan(query)
        rec.record_tool_call(
            tool_name="decompose_into_subtasks",
            arguments={"query": query},
            result_summary=f"Generated {len(plan.subtasks)} subtasks",
            duration=time.perf_counter() - t0
        )
    except Exception as e:
        logger.warning("Planner Agent encountered error: %s. Using resilient template fallback.", str(e))
        plan = create_fallback_plan(query)
        degraded = True
        rec.record_error(str(e))
        rec.record_retry(reason="Template planner fallback engaged")
        rec.record_tool_call(
            tool_name="create_fallback_plan",
            arguments={"query": query},
            result_summary=f"Fallback plan generated with {len(plan.subtasks)} subtasks",
            duration=time.perf_counter() - t0,
            error=str(e)
        )

    rec.record_search_queries(plan.search_queries)
    subtask_dicts = [st.model_dump() for st in plan.subtasks]
    logger.info(
        "Planner generated %d independent subtasks for '%s' (degraded=%s)",
        len(subtask_dicts), plan.main_topic, degraded
    )

    degraded_modes = list(state.get("degraded_modes", []))
    if degraded and "template_planner_fallback" not in degraded_modes:
        degraded_modes.append("template_planner_fallback")

    rec.finish(
        status="degraded" if degraded else "completed",
        output_payload={
            "research_objective": plan.research_objective,
            "subtasks_count": len(subtask_dicts),
            "search_queries": plan.search_queries,
            "sub_questions": plan.sub_questions,
        }
    )

    return {
        "session_id": session_id,
        "plan": plan.model_dump(),
        "plan_markdown": plan.to_markdown(),
        "subtasks": subtask_dicts,
        "search_queries_used": plan.search_queries,
        "subtask_results": [],
        "degraded_modes": degraded_modes,
        "telemetry": telemetry.to_tree(),
        "agent_runs": [r.to_dict() for r in telemetry.get_runs()],
    }


# -----------------------------
# LangGraph Conditional Edge: Route Subtasks
# -----------------------------
def route_to_subtasks(state: ResearchState) -> List[Send]:
    """
    LangGraph fan-out: Sends each subtask to execute_subtask_node concurrently.
    """
    subtasks = state.get("subtasks", [])
    logger.info("Routing %d subtasks to parallel execution via LangGraph Send", len(subtasks))
    return [Send("execute_subtask_node", st) for st in subtasks]


# -----------------------------
# LangGraph Node 2: Subtask Worker (Parallel)
# -----------------------------
def execute_subtask_node(subtask_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Individual Subtask Execution Node.
    Executes search and extraction with retry, deduplication, and error isolation.
    """
    st_obj = Subtask(**subtask_dict)
    completed_st = execute_subtask(st_obj, url_registry=_global_registry)

    # Return as list so operator.add reducer merges it
    return {
        "subtask_results": [completed_st.model_dump()]
    }


# -----------------------------
# LangGraph Node 3: Evidence Collector & Persistent Vector Indexer
# -----------------------------
def evidence_collection_node(state: ResearchState) -> Dict[str, Any]:
    """
    Step 3: Evidence Collection, Vector Indexing & Semantic Retrieval.
    - Aggregates multi-subtask discovered sources and extracted text.
    - Cleans boilerplate, chunks documents, generates embeddings, and indexes into ChromaDB.
    - Enforces strict session isolation to prevent cross-research contamination.
    - Semantically retrieves top_k evidence chunks for the research objective and sub-questions.
    - Formats a verified evidence briefing for the Writer Agent.
    """
    subtask_results = state.get("subtask_results", [])
    session_id = state.get("session_id") or f"sess_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    topic = state.get("topic", "")
    plan = state.get("plan")

    logger.info("Aggregating and indexing evidence for session '%s' across %d subtasks", session_id, len(subtask_results))

    all_discovered = []
    all_extracted = []
    seen_urls = set()
    subtask_summary = []

    # Build backward-compatible blocks for NewsResources.jsx and history
    ddg_blocks = []
    evidence_blocks = []

    all_failed_sources = []
    all_warnings = list(state.get("warnings", []))
    degraded_modes = list(state.get("degraded_modes", []))

    for st in subtask_results:
        sid = st.get("subtask_id", "subtask")
        question = st.get("question", "")
        status = st.get("status", "unknown")
        err = st.get("error")

        discovered = st.get("discovered_urls", [])
        extracted = st.get("extracted_documents", [])
        failed = st.get("failed_sources", [])
        warnings = st.get("warnings", [])

        all_failed_sources.extend(failed)
        for w in warnings:
            if w not in all_warnings:
                all_warnings.append(w)
        if st.get("degraded") and "search_snippet_evidence_fallback" not in degraded_modes:
            degraded_modes.append("search_snippet_evidence_fallback")

        subtask_summary.append({
            "subtask_id": sid,
            "question": question,
            "status": status,
            "sources_count": len(discovered),
            "docs_count": len(extracted),
            "failed_sources_count": len(failed),
            "error": err,
            "degraded": st.get("degraded", False),
        })

        # Compile discovered URLs
        for src in discovered:
            url = src.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_discovered.append(src)
                ddg_blocks.append(
                    f"\nTitle : {src.get('title', 'Web Source')}\n\n"
                    f"URL : {url}\n\n"
                    f"Snippet :\n{src.get('snippet', '')}\n"
                )

        # Compile extracted documents with subtask attribution
        evidence_blocks.append(f"### Subtask [{sid}]: {question}\nStatus: {status}")
        if extracted:
            for doc in extracted:
                # Ensure subtask_id is attached to extracted doc
                if not doc.get("subtask_id"):
                    doc["subtask_id"] = sid
                all_extracted.append(doc)
                evidence_blocks.append(
                    f"Source: [{doc.get('title')}]({doc.get('url')})\n"
                    f"Content:\n{doc.get('text', '')}\n"
                )
        elif err:
            evidence_blocks.append(f"Note: Extraction encountered an error: {err}\n")
        else:
            evidence_blocks.append("Note: No webpage text extracted.\n")

    if all_failed_sources and "partial_source_failure" not in degraded_modes:
        degraded_modes.append("partial_source_failure")

    combined_search_results = "\n-----------------------------\n".join(ddg_blocks)
    combined_scraped_content = "\n\n".join(evidence_blocks)

    # -------------------------------------------------------------
    # Telemetry: Record Search & Reader Agent execution
    # -------------------------------------------------------------
    telemetry = get_session_telemetry(session_id, topic=topic)

    # Search Agent telemetry
    search_rec = telemetry.start_agent_run("Search", model_used="DuckDuckGo Search API")
    all_search_queries = []
    for st in subtask_results:
        all_search_queries.extend(st.get("search_queries", []))
    search_rec.record_search_queries(all_search_queries)
    search_rec.record_urls_discovered(list(seen_urls))
    for s in all_discovered[:15]:
        search_rec.record_tool_call(
            "search_web_resilient",
            arguments={"title": s.get("title")},
            result_summary=f"Discovered: {s.get('url')}"
        )
    search_status = "degraded" if not all_discovered and subtask_results else "completed"
    search_rec.finish(
        status=search_status,
        output_payload={
            "queries_executed": len(all_search_queries),
            "urls_discovered": len(all_discovered),
            "unique_urls": len(seen_urls),
        }
    )

    # Reader Agent telemetry
    reader_rec = telemetry.start_agent_run("Reader", model_used="HTTP/BS4 Resilient Web Scraper")
    reader_rec.record_urls_extracted([d.get("url") for d in all_extracted if d.get("url")])
    for f in all_failed_sources:
        reader_rec.record_error(f"{f.get('url')}: {f.get('reason') or f.get('error')}")
        reader_rec.record_retry(reason=f"Candidate failover for {f.get('url')}")
    for d in all_extracted[:15]:
        reader_rec.record_tool_call(
            "scrape_url_resilient",
            arguments={"url": d.get("url")},
            result_summary=f"Extracted {len(d.get('text', ''))} chars from {d.get('url')}"
        )
    reader_status = "degraded" if all_failed_sources and not all_extracted else "completed"
    reader_rec.finish(
        status=reader_status,
        output_payload={
            "documents_extracted": len(all_extracted),
            "failed_sources": len(all_failed_sources),
            "total_characters": sum(len(d.get("text", "")) for d in all_extracted),
        }
    )

    # Retrieval Agent telemetry span
    retrieval_rec = telemetry.start_agent_run(
        "Retrieval",
        model_used="SentenceTransformers (all-MiniLM-L6-v2) + ChromaDB"
    )
    t_ret_start = time.perf_counter()

    # -------------------------------------------------------------
    # Persistent Evidence Retrieval Layer: Indexing into ChromaDB
    # -------------------------------------------------------------
    retrieval_service = get_retrieval_service()
    indexed_chunks = []
    try:
        # Fallback to discovered snippets if deep scraping returned 0 docs (e.g. 403 blocks)
        if not all_extracted and all_discovered:
            logger.info("Scraping returned 0 docs; indexing %d discovered search snippets into ChromaDB as fallback evidence", len(all_discovered))
            for src in all_discovered:
                all_extracted.append({
                    "url": src.get("url", ""),
                    "title": src.get("title", "Web Source"),
                    "text": src.get("snippet", ""),
                    "subtask_id": "search_snippet",
                })

        if all_extracted:
            indexed_chunks = retrieval_service.index_extracted_documents(
                all_extracted, session_id=session_id
            )
            logger.info(
                "Indexed %d evidence chunks into ChromaDB for session '%s'",
                len(indexed_chunks), session_id
            )
        else:
            logger.warning("No extracted documents to index for session '%s'", session_id)
    except Exception as e:
        logger.error("ChromaDB vector indexing encountered an error: %s", str(e))

    # -------------------------------------------------------------
    # Semantic Evidence Retrieval for the Research Topic & Subtasks
    # -------------------------------------------------------------
    retrieved_chunks = []
    seen_chunk_ids = set()

    obj = plan.get("research_objective", "") if isinstance(plan, dict) else ""
    primary_query = f"{topic} {obj}".strip() or topic

    try:
        # 1. Primary semantic search for overall topic & research objective
        primary_results = retrieval_service.retrieve_evidence(
            query=primary_query,
            session_id=session_id,
            top_k=DEFAULT_TOP_K
        )
        for ev in primary_results:
            if ev.chunk_id not in seen_chunk_ids:
                seen_chunk_ids.add(ev.chunk_id)
                retrieved_chunks.append(ev)

        # 2. Targeted semantic retrieval per subtask question
        if plan and isinstance(plan, dict):
            sub_questions = plan.get("sub_questions", [])
            for sq in sub_questions[:4]:
                sq_results = retrieval_service.retrieve_evidence(
                    query=sq,
                    session_id=session_id,
                    top_k=2
                )
                for ev in sq_results:
                    if ev.chunk_id not in seen_chunk_ids:
                        seen_chunk_ids.add(ev.chunk_id)
                        retrieved_chunks.append(ev)

        logger.info(
            "Semantic retriever gathered %d distinct evidence chunks for session '%s'",
            len(retrieved_chunks), session_id
        )
    except Exception as e:
        logger.error("Semantic evidence retrieval encountered an error: %s", str(e))

    evidence_briefing = retrieval_service.format_evidence_briefing(retrieved_chunks)

    # -----------------------------------------------------------------
    # Source Quality Analysis — deterministic scoring & ranking
    # -----------------------------------------------------------------
    source_profiles_for_scoring = []
    for doc in all_extracted:
        source_profiles_for_scoring.append({
            "url": doc.get("url", ""),
            "title": doc.get("title", ""),
            "text": doc.get("text", ""),
            "snippet": doc.get("snippet", ""),
            "subtask_id": doc.get("subtask_id", "general"),
            "publication_date": doc.get("publication_date", ""),
        })
    # Also include discovered sources that weren't fully extracted
    for src in all_discovered:
        url = src.get("url", "")
        if not any(d.get("url") == url for d in all_extracted):
            source_profiles_for_scoring.append({
                "url": url,
                "title": src.get("title", ""),
                "text": src.get("snippet", ""),
                "snippet": src.get("snippet", ""),
                "subtask_id": "search_snippet",
            })

    quality_report = profile_all_sources(source_profiles_for_scoring, session_id=session_id)
    logger.info(
        "Source quality analysis complete: %d sources profiled, avg quality %.1f%%, %d duplicates, %d stale",
        quality_report.total_sources, quality_report.average_quality * 100,
        quality_report.duplicate_count, quality_report.stale_count,
    )

    # Build quality lookup by source_id for evidence re-ranking
    quality_lookup = {p.source_id: p for p in quality_report.scored_sources}

    # Re-rank retrieved evidence by blending similarity (70%) + quality (30%)
    retrieved_dicts = [ev.model_dump() for ev in retrieved_chunks]
    ranked_evidence = rank_retrieved_evidence(retrieved_dicts, quality_lookup)

    # Generate quality briefing for the writer
    quality_briefing = format_source_quality_briefing(quality_report)

    evidence_summary = {
        "total_subtasks": len(subtask_results),
        "completed": sum(1 for s in subtask_results if s.get("status") == "completed"),
        "failed": sum(1 for s in subtask_results if s.get("status") == "failed"),
        "unique_sources": len(seen_urls),
        "extracted_documents": len(all_extracted),
        "indexed_chunks": len(indexed_chunks),
        "retrieved_evidence_count": len(retrieved_chunks),
        "failed_sources_count": len(all_failed_sources),
        "failed_sources": all_failed_sources,
        "warnings": all_warnings,
        "session_id": session_id,
        "subtasks_detail": subtask_summary,
        "source_quality": {
            "average_quality": quality_report.average_quality,
            "total_profiled": quality_report.total_sources,
            "type_distribution": quality_report.type_distribution,
            "freshness_distribution": quality_report.freshness_distribution,
            "quality_distribution": quality_report.quality_distribution,
            "duplicate_count": quality_report.duplicate_count,
            "undated_count": quality_report.undated_count,
            "stale_count": quality_report.stale_count,
        },
    }

    # Complete Retrieval Agent telemetry
    retrieval_rec.record_evidence_chunks(len(indexed_chunks))
    retrieval_rec.record_tool_call(
        tool_name="index_extracted_documents",
        arguments={"documents_count": len(all_extracted)},
        result_summary=f"Indexed {len(indexed_chunks)} chunks into vector store"
    )
    retrieval_rec.record_tool_call(
        tool_name="retrieve_evidence",
        arguments={"query": primary_query, "top_k": DEFAULT_TOP_K},
        result_summary=f"Retrieved {len(retrieved_chunks)} semantic chunks"
    )
    retrieval_rec.record_tool_call(
        tool_name="profile_all_sources",
        arguments={"sources_count": len(source_profiles_for_scoring)},
        result_summary=f"Profiled {quality_report.total_sources} sources (avg quality: {quality_report.average_quality*100:.1f}%)"
    )
    retrieval_rec.finish(
        status="completed",
        output_payload=evidence_summary
    )

    logger.info(
        "Evidence aggregation & retrieval complete: %d unique sources, %d docs, %d indexed chunks, %d retrieved chunks, %d failed sources",
        len(seen_urls), len(all_extracted), len(indexed_chunks), len(retrieved_chunks), len(all_failed_sources)
    )

    return {
        "session_id": session_id,
        "search_results": combined_search_results,
        "scraped_content": combined_scraped_content,
        "evidence_briefing": evidence_briefing + "\n\n" + quality_briefing,
        "retrieved_evidence": ranked_evidence,
        "evidence_summary": evidence_summary,
        "source_quality_profiles": [p.model_dump() for p in quality_report.scored_sources],
        "failed_sources": all_failed_sources,
        "warnings": all_warnings,
        "degraded_modes": degraded_modes,
        "telemetry": telemetry.to_tree(),
        "agent_runs": [r.to_dict() for r in telemetry.get_runs()],
    }


# -----------------------------
# LangGraph Node 4: Writer
# -----------------------------
def writer_node(state: ResearchState) -> Dict[str, Any]:
    """
    Step 4: Writer Agent.
    Synthesizes semantically retrieved evidence into structured factual claims
    and an executive grounded report.
    Consumes curated evidence chunks from the persistent vector store.
    Strictly verifies citations against the evidence catalog to prevent hallucination.
    Employs circuit breakers, multi-model fallback, and deterministic grounded synthesis.
    """
    topic = state.get("topic", "")
    search_results = state.get("search_results", "")
    retrieved_evidence = state.get("retrieved_evidence", [])
    plan = state.get("plan")
    degraded_modes = list(state.get("degraded_modes", []))
    session_id = state.get("session_id") or f"sess_{int(time.time())}_{uuid.uuid4().hex[:8]}"

    telemetry = get_session_telemetry(session_id, topic=topic)
    writer_model = os.getenv("GROQ_WRITER_MODEL", "llama-3.3-70b-versatile")
    writer_rec = telemetry.start_agent_run(
        "Writer",
        model_used=writer_model,
        input_payload={"topic": topic, "retrieved_evidence_count": len(retrieved_evidence)}
    )
    t_writer_start = time.perf_counter()

    logger.info("Executing Citation-Grounded Writer Node for topic: '%s'", topic)

    plan_context = ""
    if plan and isinstance(plan, dict):
        sub_qs = "\n".join(f"- {q}" for q in plan.get("sub_questions", []))
        plan_context = (
            f"RESEARCH OBJECTIVE:\n{plan.get('research_objective', '')}\n\n"
            f"CORE SUB-QUESTIONS INVESTIGATED:\n{sub_qs}\n\n"
        )

    # 1. Build Source and Evidence Chunk Registry
    sources, evidence_chunks = build_source_registry(retrieved_evidence)

    # Fallback to subtask documents or discovered sources if retrieved evidence was empty
    if not sources:
        fallback_docs = []
        for st in state.get("subtask_results", []):
            fallback_docs.extend(st.get("extracted_documents", []))
            for src in st.get("discovered_urls", []):
                fallback_docs.append({
                    "url": src.get("url", ""),
                    "title": src.get("title", "Web Source"),
                    "text": src.get("snippet", ""),
                    "subtask_id": st.get("subtask_id", "general"),
                })
        if fallback_docs:
            sources, evidence_chunks = build_source_registry(fallback_docs)

    # 2. Format Authoritative Evidence Catalog for Writer LLM
    evidence_catalog = format_evidence_catalog_for_writer(sources, evidence_chunks)

    research_payload = (
        f"{plan_context}"
        f"{evidence_catalog}\n\n"
        f"VERIFIED SEARCH SUMMARY:\n{search_results}\n"
    )

    raw_output = ""
    try:
        raw_output = invoke_chain_resilient(
            chain=writer_chain,
            fallback_chain=writer_chain_fallback,
            input_dict={"topic": topic, "research": research_payload},
            service_name="writer_llm",
            timeout=90.0,
            max_attempts=3
        )
    except Exception as e:
        logger.error("Writer LLM invocation failed across primary and fallback: %s. Engaging deterministic synthesis.", str(e))
        raw_output = ""
        if "deterministic_writer_fallback" not in degraded_modes:
            degraded_modes.append("deterministic_writer_fallback")

    # 3. Parse structured claims from LLM output
    summary, claims, conclusion = parse_writer_claims_response(raw_output, sources, evidence_chunks)

    # Resilient fallback: If LLM output was empty, malformed, or yielded 0 valid claims, synthesize grounded claims deterministically
    if not claims and (sources or evidence_chunks):
        logger.warning("No valid claims extracted from Writer LLM output. Activating deterministic grounded claims synthesis (zero fabrication).")
        det_summary, det_claims, det_conclusion = synthesize_deterministic_grounded_claims(topic, sources, evidence_chunks)
        claims = det_claims
        if not summary or summary.strip().startswith("{") or "corrupted" in summary.lower():
            summary = det_summary
        if not conclusion or conclusion.strip().startswith("{"):
            conclusion = det_conclusion
        if "deterministic_claims_fallback" not in degraded_modes:
            degraded_modes.append("deterministic_claims_fallback")

    # 4. Assemble Grounded Report with verified citations, evidence audit, and automated Sources
    grounded_report = assemble_grounded_report(
        topic=topic,
        summary=summary,
        claims=claims,
        conclusion=conclusion,
        sources=sources,
        evidence_chunks=evidence_chunks
    )

    writer_status = "degraded" if "deterministic_claims_fallback" in degraded_modes else "completed"
    words_count = len(grounded_report.markdown_report.split())
    writer_rec.record_tool_call(
        tool_name="assemble_grounded_report",
        result_summary=f"Synthesized {len(grounded_report.claims)} claims across {words_count} words",
        duration=time.perf_counter() - t_writer_start
    )
    writer_rec.finish(
        status=writer_status,
        output_payload={
            "claims_count": len(grounded_report.claims),
            "grounded_claims_count": len(grounded_report.grounded_claims),
            "unsupported_claims_count": len(grounded_report.unsupported_claims),
            "insufficient_claims_count": len(grounded_report.insufficient_claims),
            "words_count": words_count,
        }
    )

    logger.info(
        "Writer Node completed: %d claims (%d grounded, %d insufficient, %d unsupported)",
        len(grounded_report.claims),
        len(grounded_report.grounded_claims),
        len(grounded_report.insufficient_claims),
        len(grounded_report.unsupported_claims)
    )

    return {
        "report": grounded_report.markdown_report,
        "claims": [c.model_dump() for c in grounded_report.claims],
        "sources": {sid: s.model_dump() for sid, s in sources.items()},
        "grounded_claims": [c.model_dump() for c in grounded_report.grounded_claims],
        "unsupported_claims": [c.model_dump() for c in grounded_report.unsupported_claims],
        "insufficient_claims": [c.model_dump() for c in grounded_report.insufficient_claims],
        "citation_trace": grounded_report.citation_trace,
        "degraded_modes": degraded_modes,
        "telemetry": telemetry.to_tree(),
        "agent_runs": [r.to_dict() for r in telemetry.get_runs()],
    }


# -----------------------------
# LangGraph Node 5: Autonomous Verification Agent
# -----------------------------
def verifier_node(state: ResearchState) -> Dict[str, Any]:
    """
    Step 5: Autonomous Research Verification Agent.
    Audits the generated claims and report across 11 verification checks:
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

    Produces structured output:
    {
      "status": "PASS | RESEARCH_REQUIRED",
      "confidence": float,
      "unsupported_claims": [],
      "weak_claims": [],
      "contradictions": [],
      "missing_topics": [],
      "additional_queries": [],
      "reasoning_summary": ""
    }
    """
    claims = state.get("claims", [])
    report = state.get("report", "")
    plan = state.get("plan")
    retrieved_evidence = state.get("retrieved_evidence", [])
    topic = state.get("topic", "")
    iteration = state.get("verification_iteration", 1)
    session_id = state.get("session_id") or f"sess_{int(time.time())}_{uuid.uuid4().hex[:8]}"

    logger.info("Executing Autonomous Verification Node (Iteration %d) for topic: '%s'", iteration, topic)

    telemetry = get_session_telemetry(session_id, topic=topic)
    verifier_model = os.getenv("GROQ_CRITIC_MODEL", "llama-3.3-70b-versatile")
    verifier_rec = telemetry.start_agent_run(
        "Verification",
        iteration_number=iteration,
        model_used=verifier_model,
        input_payload={"iteration": iteration, "claims_count": len(claims)}
    )
    t_v_start = time.perf_counter()

    # Reconstruct or fetch source and chunk registries
    sources, evidence_chunks = build_source_registry(retrieved_evidence)
    if not sources and state.get("sources"):
        sources = {sid: Source(**s) if isinstance(s, dict) else s for sid, s in state["sources"].items()}

    agent = ResearchVerificationAgent()
    verification_res = agent.verify(
        claims=claims,
        sources=sources,
        evidence_chunks=evidence_chunks,
        retrieved_evidence=retrieved_evidence,
        report=report,
        plan=plan,
        iteration=iteration,
        topic=topic
    )

    res_dict = verification_res.to_dict()
    history = list(state.get("verification_history", []))
    history.append(res_dict)

    v_status = res_dict.get("status", "PASS")
    verifier_rec.record_tool_call(
        tool_name="verify_grounded_claims_11_checks",
        result_summary=f"Decision: {v_status} ({res_dict.get('confidence', 0.0):.1%}), {len(res_dict.get('unsupported_claims', []))} unsupported, {len(res_dict.get('additional_queries', []))} queries",
        duration=time.perf_counter() - t_v_start
    )
    if res_dict.get("additional_queries"):
        verifier_rec.record_search_queries(res_dict["additional_queries"])
    if res_dict.get("unsupported_claims"):
        for uc in res_dict["unsupported_claims"]:
            verifier_rec.record_error(f"Flagged claim: {uc}")

    verifier_rec.finish(
        status="completed" if v_status == "PASS" else "degraded",
        output_payload=res_dict
    )

    logger.info(
        "Verification Iteration %d Result: %s (Confidence: %.1f%%, %d unsupported, %d contradictions, %d missing topics, %d additional queries)",
        iteration,
        res_dict["status"],
        res_dict["confidence"] * 100,
        len(res_dict["unsupported_claims"]),
        len(res_dict["contradictions"]),
        len(res_dict["missing_topics"]),
        len(res_dict["additional_queries"])
    )

    return {
        "verification_result": res_dict,
        "additional_queries": res_dict.get("additional_queries", []),
        "verification_history": history,
        "verification_iteration": iteration,
        "feedback": res_dict.get("reasoning_summary", ""),
        "telemetry": telemetry.to_tree(),
        "agent_runs": [r.to_dict() for r in telemetry.get_runs()],
    }


# -----------------------------
# LangGraph Conditional Edge: Verification Loop Routing
# -----------------------------
def should_continue_verification(state: ResearchState) -> str:
    """
    Evaluates whether verification passed or additional research is required.
    Strictly halts at MAX_RESEARCH_ITERATIONS to prevent infinite loops.
    """
    v_res = state.get("verification_result", {})
    status = v_res.get("status", "PASS")
    iteration = state.get("verification_iteration", 1)

    if status == "PASS":
        logger.info("Autonomous Verification PASSED on iteration %d! Routing to finalize report.", iteration)
        return "finalize"

    if iteration >= MAX_RESEARCH_ITERATIONS:
        logger.warning(
            "Reached MAX_RESEARCH_ITERATIONS (%d). Exiting verification loop autonomously to finalize report.",
            MAX_RESEARCH_ITERATIONS
        )
        return "finalize"

    logger.info(
        "Verification status is 'RESEARCH_REQUIRED' (Iteration %d of %d). Routing to additional research.",
        iteration, MAX_RESEARCH_ITERATIONS
    )
    return "re_research"


# -----------------------------
# LangGraph Node 6: Additional Research (Autonomous Loop)
# -----------------------------
def re_research_node(state: ResearchState) -> Dict[str, Any]:
    """
    Additional Research Node.
    Executes when the Verification Agent identifies weak/unsupported claims or missing topics.
    Searches web for targeted additional queries, scrapes new sources, and updates evidence.
    """
    additional_queries = state.get("additional_queries", [])
    topic = state.get("topic", "")
    iteration = state.get("verification_iteration", 1)

    if not additional_queries:
        additional_queries = [f"{topic} empirical evidence data"]

    logger.info(
        "Executing Re-Research Node (Iteration %d) with %d targeted queries: %s",
        iteration, len(additional_queries), additional_queries
    )

    new_subtasks = []
    # Limit to top 3 targeted queries to prevent rate limits while ensuring thorough evidence gathering
    for i, q in enumerate(additional_queries[:3]):
        st_id = f"re_research_iter{iteration}_{i+1}"
        subtask_obj = Subtask(
            subtask_id=st_id,
            question=q,
            search_queries=[q]
        )
        try:
            completed_st = execute_subtask(subtask_obj, url_registry=_global_registry)
            new_subtasks.append(completed_st.model_dump())
        except Exception as e:
            logger.error("Re-research subtask failed for query '%s': %s", q, str(e))
            subtask_obj.status = "failed"
            subtask_obj.error = str(e)
            new_subtasks.append(subtask_obj.model_dump())

    next_iteration = iteration + 1
    logger.info(
        "Re-research completed: %d new subtasks executed. Next iteration will be %d.",
        len(new_subtasks), next_iteration
    )

    return {
        "subtask_results": new_subtasks,
        "verification_iteration": next_iteration
    }


# -----------------------------
# LangGraph Node 7: Finalize Report
# -----------------------------
def finalize_report_node(state: ResearchState) -> Dict[str, Any]:
    """
    Finalize Report Node.
    - If status == PASS: completes report with verified certification.
    - If MAX_RESEARCH_ITERATIONS reached without complete verification:
      badging unresolved claims explicitly in report text and audit section.
      NEVER fabricates evidence.
    """
    claims = state.get("claims", [])
    report = state.get("report", "")
    v_res = state.get("verification_result", {})
    iteration = state.get("verification_iteration", 1)

    status = v_res.get("status", "PASS")
    confidence = float(v_res.get("confidence", 1.0))
    summary = v_res.get("reasoning_summary", "")

    final_report = report
    unresolved_claims = []

    if status != "PASS":
        # Autonomous handling: reached maximum iterations without 100% verification
        # Explicitly badge unresolved claims
        vr_obj = VerificationResult(**v_res)
        final_report, unresolved_claims = mark_unresolved_claims(claims, report, vr_obj)
        logger.warning(
            "Finalized report with %d unresolved claims after %d verification iterations (zero fabrication).",
            len(unresolved_claims), iteration
        )
    else:
        # Append successful verification certification
        audit_note = (
            f"\n\n---\n\n## Verification & Evidence Audit\n"
            f"- **Status**: PASS ✅\n"
            f"- **Confidence**: {confidence:.1%}\n"
            f"- **Verification Iterations**: {iteration}/{MAX_RESEARCH_ITERATIONS}\n"
            f"- **Summary**: {summary}\n"
        )
        final_report += audit_note

    # Feedback formatted for UI display
    feedback_text = (
        f"## Research Verification Audit\n\n"
        f"**Decision**: `{'PASS' if status == 'PASS' else 'RESEARCH_REQUIRED (Max Iterations Reached)'}`\n\n"
        f"**Confidence**: {confidence:.1%}\n\n"
        f"**Iterations Completed**: {iteration}/{MAX_RESEARCH_ITERATIONS}\n\n"
        f"**Audit Findings**:\n{summary}\n"
    )

    if unresolved_claims:
        feedback_text += f"\n\n### Flagged Unresolved Claims ({len(unresolved_claims)})\n"
        for u in unresolved_claims:
            feedback_text += f"- **[{u['claim_id']}]**: {u['text']}\n"

    return {
        "report": final_report,
        "unresolved_claims": unresolved_claims,
        "feedback": feedback_text
    }


# -----------------------------
# Backwards-Compatible Critic Node Wrapper
# -----------------------------
def critic_node(state: ResearchState) -> Dict[str, Any]:
    """
    Backward-compatibility wrapper for legacy tests and callers.
    Routes directly through the autonomous Verification Agent.
    """
    v_out = verifier_node(state)
    return {
        "feedback": v_out.get("feedback", ""),
        "verification_result": v_out.get("verification_result", {})
    }


# -----------------------------
# LangGraph Workflow Definition
# -----------------------------
def create_research_graph():
    """
    Build and compile the LangGraph StateGraph pipeline with autonomous verification loop.
    Architecture:
    START -> planner -> [route_to_subtasks (Send in parallel)] -> execute_subtask_node
                     -> evidence_collector -> writer -> verifier
                     -> (PASS or MAX_ITERATIONS? -> finalize -> END)
                     -> (RESEARCH_REQUIRED? -> re_research -> evidence_collector -> writer -> verifier)
    """
    workflow = StateGraph(ResearchState)

    workflow.add_node("planner", planner_node)
    workflow.add_node("execute_subtask_node", execute_subtask_node)
    workflow.add_node("evidence_collector", evidence_collection_node)
    workflow.add_node("writer", writer_node)
    workflow.add_node("verifier", verifier_node)
    workflow.add_node("re_research", re_research_node)
    workflow.add_node("finalize", finalize_report_node)

    workflow.add_edge(START, "planner")
    workflow.add_conditional_edges("planner", route_to_subtasks, ["execute_subtask_node"])
    workflow.add_edge("execute_subtask_node", "evidence_collector")
    workflow.add_edge("evidence_collector", "writer")
    workflow.add_edge("writer", "verifier")

    workflow.add_conditional_edges(
        "verifier",
        should_continue_verification,
        {
            "finalize": "finalize",
            "re_research": "re_research"
        }
    )

    workflow.add_edge("re_research", "evidence_collector")
    workflow.add_edge("finalize", END)

    return workflow.compile()


# -----------------------------
# Synchronous Pipeline Runner
# -----------------------------
def run_research_pipeline(topic: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Run complete research pipeline synchronously via compiled LangGraph.
    Executes closed-loop verification autonomously.
    """
    logger.info("Starting synchronous LangGraph verification pipeline for: '%s'", topic)
    graph = create_research_graph()

    sess_id = session_id or f"sess_{int(time.time())}_{uuid.uuid4().hex[:8]}"

    initial_state: ResearchState = {
        "topic": topic,
        "original_query": topic,
        "session_id": sess_id,
        "subtask_results": [],
        "verification_iteration": 1,
        "verification_history": [],
    }

    final_state = graph.invoke(initial_state)
    telemetry = get_session_telemetry(sess_id, topic=topic)
    final_state["telemetry"] = telemetry.to_tree()
    final_state["agent_runs"] = [r.to_dict() for r in telemetry.get_runs()]
    logger.info("LangGraph verification pipeline finished successfully")
    return final_state


# -----------------------------
# Streaming version for FastAPI SSE
# -----------------------------
def run_research_pipeline_stream(topic: str, session_id: Optional[str] = None):
    """
    Generator that yields real-time SSE step events as concurrent subtasks execute
    and closed-loop verification iterations cycle autonomously.
    Maintains 100% backward compatibility with frontend expectations.
    """
    sess_id = session_id or f"sess_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    telemetry = get_session_telemetry(sess_id, topic=topic)
    state: ResearchState = {
        "topic": topic,
        "original_query": topic,
        "session_id": sess_id,
        "subtask_results": [],
        "verification_iteration": 1,
        "verification_history": [],
    }

    # Step 1: Research Planner Agent
    yield {"step": "planner", "status": "running"}
    planner_output = planner_node(state)
    state.update(planner_output)
    yield {
        "step": "planner",
        "status": "done",
        "result": state.get("plan_markdown", ""),
        "plan": state.get("plan", {}),
        "subtasks": state.get("subtasks", [])
    }
    yield {
        "step": "telemetry",
        "agent_name": "Planner",
        "telemetry": telemetry.to_tree(),
        "agent_runs": [r.to_dict() for r in telemetry.get_runs()]
    }

    # Step 2: Concurrent Subtask Execution
    subtasks_data = state.get("subtasks", [])
    subtask_objs = [Subtask(**st) for st in subtasks_data]

    yield {
        "step": "subtasks",
        "status": "running",
        "total": len(subtask_objs),
        "concurrency": MAX_CONCURRENT_SUBTASKS
    }
    yield {"step": "search", "status": "running"}
    yield {"step": "reader", "status": "running"}

    # Queue to receive progress updates from background threads
    event_queue: queue.Queue = queue.Queue()

    def progress_callback(st: Subtask):
        event_queue.put({
            "step": "subtask_progress",
            "subtask_id": st.subtask_id,
            "status": st.status,
            "question": st.question,
            "discovered_count": len(st.discovered_urls),
            "extracted_count": len(st.extracted_documents),
            "error": st.error
        })

    # Run subtasks in thread
    completed_subtasks: List[Subtask] = []
    worker_error: List[Exception] = []

    def run_workers():
        try:
            res = execute_subtasks_concurrently(
                subtask_objs,
                max_concurrency=MAX_CONCURRENT_SUBTASKS,
                timeout=SUBTASK_TIMEOUT_SECONDS,
                on_subtask_progress=progress_callback
            )
            completed_subtasks.extend(res)
        except Exception as e:
            worker_error.append(e)
        finally:
            event_queue.put(None)  # Sentinel to close queue

    t = threading.Thread(target=run_workers, daemon=True)
    t.start()

    # Stream subtask events as they happen
    while True:
        try:
            item = event_queue.get(timeout=0.2)
            if item is None:
                break
            yield item
        except queue.Empty:
            if not t.is_alive():
                break

    t.join()

    # Update state with subtask results
    state["subtask_results"] = [st.model_dump() for st in completed_subtasks]

    # Step 3: Evidence Collection & Persistent Vector Store Indexing
    yield {"step": "evidence", "status": "running"}
    evidence_output = evidence_collection_node(state)
    state.update(evidence_output)

    # Signal search and reader completion for frontend compatibility
    yield {
        "step": "search",
        "status": "done",
        "result": state.get("search_results", "")
    }
    yield {
        "step": "reader",
        "status": "done",
        "result": state.get("scraped_content", "")
    }
    yield {
        "step": "evidence",
        "status": "done",
        "summary": state.get("evidence_summary", {}),
        "evidence_briefing": state.get("evidence_briefing", ""),
        "retrieved_evidence": state.get("retrieved_evidence", []),
        "source_quality_profiles": state.get("source_quality_profiles", []),
        "failed_sources": state.get("failed_sources", []),
        "degraded_modes": state.get("degraded_modes", []),
    }
    yield {
        "step": "telemetry",
        "agent_name": "Retrieval",
        "telemetry": telemetry.to_tree(),
        "agent_runs": [r.to_dict() for r in telemetry.get_runs()]
    }

    # Step 4: Writer Chain
    yield {"step": "writer", "status": "running"}
    writer_output = writer_node(state)
    state.update(writer_output)
    yield {
        "step": "writer",
        "status": "done",
        "result": state.get("report", ""),
        "claims": state.get("claims", []),
        "grounded_claims": state.get("grounded_claims", []),
        "unsupported_claims": state.get("unsupported_claims", []),
        "insufficient_claims": state.get("insufficient_claims", []),
        "citation_trace": state.get("citation_trace", {}),
    }
    yield {
        "step": "telemetry",
        "agent_name": "Writer",
        "telemetry": telemetry.to_tree(),
        "agent_runs": [r.to_dict() for r in telemetry.get_runs()]
    }

    # Step 5: Autonomous Verification & Re-Research Closed Loop
    while True:
        curr_iter = state.get("verification_iteration", 1)
        yield {
            "step": "verifier",
            "status": "running",
            "iteration": curr_iter,
            "max_iterations": MAX_RESEARCH_ITERATIONS
        }

        verifier_output = verifier_node(state)
        state.update(verifier_output)
        v_res = state.get("verification_result", {})

        yield {
            "step": "verifier",
            "status": "done",
            "iteration": curr_iter,
            "verification_result": v_res,
            "decision": v_res.get("status")
        }
        yield {
            "step": "telemetry",
            "agent_name": "Verification",
            "telemetry": telemetry.to_tree(),
            "agent_runs": [r.to_dict() for r in telemetry.get_runs()]
        }

        # Check loop condition
        route = should_continue_verification(state)

        if route == "finalize":
            finalize_output = finalize_report_node(state)
            state.update(finalize_output)

            # Stream critic/audit result for frontend backwards compatibility
            yield {
                "step": "critic",
                "status": "done",
                "result": state.get("feedback", ""),
                "verification_result": v_res,
                "unresolved_claims": state.get("unresolved_claims", [])
            }
            break

        # Additional Research required
        add_queries = state.get("additional_queries", [])
        yield {
            "step": "re_research",
            "status": "running",
            "iteration": curr_iter,
            "queries": add_queries
        }

        re_res_output = re_research_node(state)
        state["subtask_results"].extend(re_res_output.get("subtask_results", []))
        state["verification_iteration"] = re_res_output.get("verification_iteration", curr_iter + 1)

        yield {
            "step": "re_research",
            "status": "done",
            "new_subtasks_count": len(re_res_output.get("subtask_results", [])),
            "iteration": state["verification_iteration"]
        }

        # Re-index into persistent vector store
        yield {"step": "evidence", "status": "running", "iteration": state["verification_iteration"]}
        evidence_output = evidence_collection_node(state)
        state.update(evidence_output)
        yield {
            "step": "evidence",
            "status": "done",
            "summary": state.get("evidence_summary", {}),
            "retrieved_evidence": state.get("retrieved_evidence", [])
        }

        # Re-write grounded report
        yield {"step": "writer", "status": "running", "iteration": state["verification_iteration"]}
        writer_output = writer_node(state)
        state.update(writer_output)
        yield {
            "step": "writer",
            "status": "done",
            "result": state.get("report", ""),
            "claims": state.get("claims", [])
        }

    # Final complete signal with structured telemetry tree and runs
    tree_snapshot = telemetry.to_tree()
    runs_snapshot = [r.to_dict() for r in telemetry.get_runs()]
    state["telemetry"] = tree_snapshot
    state["agent_runs"] = runs_snapshot

    yield {
        "step": "complete",
        "status": "done",
        "state": state,
        "telemetry": tree_snapshot,
        "agent_runs": runs_snapshot,
        "failed_sources": state.get("failed_sources", []),
        "degraded_modes": state.get("degraded_modes", []),
    }