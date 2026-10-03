"""
SYNAPSE AI — Persistent Research Workspace Service Layer.

Provides clean transactional operations for:
- User and ResearchProject management
- ResearchSession lifecycle (queries, subtasks, sources, evidence, claims, runs, reports)
- Full isolation between concurrent sessions
- Comprehensive error handling with atomic rollback
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from db.models import (
    AgentRun,
    Claim,
    ClaimEvidenceLink,
    EvidenceChunk,
    Report,
    ResearchProject,
    ResearchQuery,
    ResearchSession,
    ResearchSubtask,
    Source,
    User,
    generate_uuid,
    utc_now,
)

logger = logging.getLogger("synapse.db.service")


# =====================================================================
# User & Project Operations
# =====================================================================

def get_or_create_default_user(
    db: Session,
    email: str = "admin@synapse.ai",
    username: str = "admin",
    full_name: str = "SYNAPSE Administrator"
) -> User:
    """Retrieve the primary user or create one if none exists."""
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if not user:
        user = User(
            id=generate_uuid(),
            email=email,
            username=username,
            full_name=full_name,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("Created default user: %s (id: %s)", email, user.id)
    return user


def create_project(
    db: Session,
    user_id: str,
    title: str,
    description: Optional[str] = None
) -> ResearchProject:
    """Create a new research project workspace."""
    project = ResearchProject(
        id=generate_uuid(),
        user_id=user_id,
        title=title.strip(),
        description=description.strip() if description else None,
        status="active",
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    logger.info("Created research project: '%s' (id: %s)", project.title, project.id)
    return project


def get_projects(db: Session, user_id: Optional[str] = None) -> List[ResearchProject]:
    """List research projects, optionally filtered by user."""
    stmt = select(ResearchProject)
    if user_id:
        stmt = stmt.where(ResearchProject.user_id == user_id)
    stmt = stmt.order_by(desc(ResearchProject.created_at))
    return list(db.execute(stmt).scalars().all())


def get_project(db: Session, project_id: str) -> Optional[ResearchProject]:
    """Retrieve a single research project by ID."""
    return db.execute(
        select(ResearchProject).where(ResearchProject.id == project_id)
    ).scalar_one_or_none()


def delete_project(db: Session, project_id: str) -> bool:
    """Delete a research project and cascade all its sessions."""
    project = get_project(db, project_id)
    if not project:
        return False
    db.delete(project)
    db.commit()
    logger.info("Deleted research project id: %s", project_id)
    return True


# =====================================================================
# Research Session Lifecycle Operations
# =====================================================================

def create_session(
    db: Session,
    project_id: str,
    topic: str,
    session_name: Optional[str] = None,
    session_id: Optional[str] = None
) -> ResearchSession:
    """Create a new research session isolating a specific topic inquiry."""
    name = session_name.strip() if session_name else f"Research: {topic[:60].strip()}"
    session = ResearchSession(
        id=session_id or generate_uuid(),
        project_id=project_id,
        session_name=name,
        topic=topic.strip(),
        status="pending",
        verification_status="unverified",
        verification_iteration=0,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    logger.info("Created research session: '%s' (id: %s)", session.session_name, session.id)
    return session


def get_session(db: Session, session_id: str) -> Optional[ResearchSession]:
    """Retrieve a single research session by ID."""
    return db.execute(
        select(ResearchSession).where(ResearchSession.id == session_id)
    ).scalar_one_or_none()


def list_sessions(
    db: Session,
    project_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[ResearchSession]:
    """List research sessions with pagination."""
    stmt = select(ResearchSession)
    if project_id:
        stmt = stmt.where(ResearchSession.project_id == project_id)
    stmt = stmt.order_by(desc(ResearchSession.created_at)).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars().all())


def update_session_status(
    db: Session,
    session_id: str,
    status: str,
    verification_status: Optional[str] = None,
    verification_iteration: Optional[int] = None,
    plan_data: Optional[Dict] = None,
    evidence_summary: Optional[Dict] = None,
    metadata_json: Optional[Dict] = None
) -> Optional[ResearchSession]:
    """Update research session execution state."""
    session = get_session(db, session_id)
    if not session:
        return None

    session.status = status
    if verification_status is not None:
        session.verification_status = verification_status
    if verification_iteration is not None:
        session.verification_iteration = verification_iteration
    if plan_data is not None:
        session.plan_data = plan_data
    if evidence_summary is not None:
        session.evidence_summary = evidence_summary
    if metadata_json is not None:
        session.metadata_json = metadata_json

    session.updated_at = utc_now()
    db.commit()
    db.refresh(session)
    return session


def delete_session(db: Session, session_id: str) -> bool:
    """Delete a research session and cascade all related child records."""
    session = get_session(db, session_id)
    if not session:
        return False
    db.delete(session)
    db.commit()
    logger.info("Deleted research session id: %s and all associated artifacts", session_id)
    return True


# =====================================================================
# Telemetry: Agent Runs
# =====================================================================

def record_agent_run(
    db: Session,
    session_id: str,
    agent_name: str,
    status: str = "completed",
    execution_time_seconds: float = 0.0,
    input_payload: Optional[Any] = None,
    output_payload: Optional[Any] = None,
    error_message: Optional[str] = None,
    metrics: Optional[Dict] = None,
    iteration: int = 0,
    run_id: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    retry_count: int = 0,
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    search_queries: Optional[List[str]] = None,
    urls_discovered: Optional[List[str]] = None,
    urls_extracted: Optional[List[str]] = None,
    evidence_chunks_created: int = 0,
    model_used: Optional[str] = None,
    token_usage: Optional[Dict[str, Any]] = None,
    errors: Optional[List[str]] = None,
) -> AgentRun:
    """Record comprehensive telemetry for an individual agent execution run."""
    from telemetry import sanitize_telemetry

    m = dict(metrics or {})
    if start_time:
        m["start_time"] = start_time
    if end_time:
        m["end_time"] = end_time
    if retry_count:
        m["retry_count"] = retry_count
    if tool_calls is not None:
        m["tool_calls"] = tool_calls
    if search_queries is not None:
        m["search_queries"] = search_queries
    if urls_discovered is not None:
        m["urls_discovered"] = urls_discovered
    if urls_extracted is not None:
        m["urls_extracted"] = urls_extracted
    if evidence_chunks_created:
        m["evidence_chunks_created"] = evidence_chunks_created
    if model_used:
        m["model_used"] = model_used
    if token_usage is not None:
        m["token_usage"] = token_usage
    if errors is not None:
        m["errors"] = errors
    elif error_message:
        m["errors"] = [error_message]

    # Sanitize inputs, outputs and metrics
    safe_input = sanitize_telemetry(input_payload)
    safe_output = sanitize_telemetry(output_payload)
    safe_metrics = sanitize_telemetry(m)

    run = AgentRun(
        id=run_id or generate_uuid(),
        session_id=session_id,
        agent_name=agent_name,
        status=status,
        iteration=iteration,
        execution_time_seconds=float(execution_time_seconds or 0.0),
        input_payload=safe_input,
        output_payload=safe_output,
        error_message=sanitize_telemetry(error_message),
        metrics=safe_metrics,
        completed_at=utc_now() if status in ("completed", "failed", "skipped", "degraded") else None,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def save_agent_telemetry(
    db: Session,
    session_id: str,
    records: List[Dict[str, Any]]
) -> List[AgentRun]:
    """Persist a batch of structured agent telemetry records."""
    saved = []
    for r in records:
        run = record_agent_run(
            db=db,
            session_id=session_id,
            agent_name=r.get("agent_name", "Agent"),
            status=r.get("status", "completed"),
            execution_time_seconds=r.get("duration", r.get("execution_time_seconds", 0.0)),
            input_payload=r.get("input_payload"),
            output_payload=r.get("output_payload"),
            error_message=r.get("error_message") or (r.get("errors", [""])[0] if r.get("errors") else None),
            metrics=r.get("metrics"),
            iteration=r.get("iteration_number", r.get("iteration", 0)),
            run_id=r.get("run_id", r.get("id")),
            start_time=r.get("start_time"),
            end_time=r.get("end_time"),
            retry_count=r.get("retry_count", 0),
            tool_calls=r.get("tool_calls"),
            search_queries=r.get("search_queries"),
            urls_discovered=r.get("urls_discovered"),
            urls_extracted=r.get("urls_extracted"),
            evidence_chunks_created=r.get("evidence_chunks_created", 0),
            model_used=r.get("model_used"),
            token_usage=r.get("token_usage"),
            errors=r.get("errors"),
        )
        saved.append(run)
    return saved


def get_session_telemetry_tree(db: Session, session_id: str) -> Dict[str, Any]:
    """
    Retrieve structured telemetry tree for a session from database.
    Reconstructs the 6-agent hierarchy:
    Research Session
     ├── Planner
     ├── Search
     ├── Reader
     ├── Retrieval
     ├── Writer
     └── Verification
    """
    from telemetry import SessionTelemetryCollector
    session = get_session(db, session_id)
    topic = session.topic if session else ""

    collector = SessionTelemetryCollector(session_id, topic=topic)

    runs = db.execute(
        select(AgentRun)
        .where(AgentRun.session_id == session_id)
        .order_by(AgentRun.created_at.asc())
    ).scalars().all()

    if runs:
        for r in runs:
            d = r.to_dict()
            rec = collector.start_agent_run(
                agent_name=d.get("agent_name", "Agent"),
                iteration_number=d.get("iteration_number", 0),
                input_payload=d.get("input_payload"),
                model_used=d.get("model_used")
            )
            rec.run_id = d.get("run_id") or rec.run_id
            rec.start_time = d.get("start_time") or rec.start_time
            rec.end_time = d.get("end_time")
            rec.duration = d.get("duration", 0.0)
            rec.status = d.get("status", "completed")
            rec.retry_count = d.get("retry_count", 0)
            rec.tool_calls = d.get("tool_calls", [])
            rec.search_queries = d.get("search_queries", [])
            rec.urls_discovered = d.get("urls_discovered", [])
            rec.urls_extracted = d.get("urls_extracted", [])
            rec.evidence_chunks_created = d.get("evidence_chunks_created", 0)
            rec.token_usage = d.get("token_usage")
            rec.errors = d.get("errors", [])
            rec.output_payload = d.get("output_payload")
            rec.metrics = d.get("metrics", {})
        return collector.to_tree()

    # Fallback to synthesizing tree from session data if no direct agent_run records exist
    if session:
        # Planner
        if session.plan_data:
            collector.start_agent_run("Planner", input_payload={"topic": topic}).finish(
                status="completed",
                output_payload={"objective": session.plan_data.get("research_objective", "")}
            )
        # Search & Reader
        subtasks = session.subtasks or []
        disc_urls = []
        ext_urls = []
        for st in subtasks:
            disc_urls.extend(st.discovered_urls or [])
            ext_urls.extend(st.extracted_urls or [])
        collector.start_agent_run("Search").finish(
            status="completed",
            output_payload={"discovered_count": len(disc_urls), "urls": disc_urls[:10]}
        )
        collector.start_agent_run("Reader").finish(
            status="completed",
            output_payload={"extracted_count": len(ext_urls), "urls": ext_urls[:10]}
        )
        # Retrieval
        ev_sum = session.evidence_summary or {}
        collector.start_agent_run("Retrieval").finish(
            status="completed",
            output_payload=ev_sum
        )
        # Writer
        reports = session.reports or []
        writer_out = {"report_words": len(reports[0].content_markdown.split())} if reports else {}
        collector.start_agent_run("Writer").finish(
            status="completed",
            output_payload=writer_out
        )
        # Verification
        v_status = session.verification_status or "PASS"
        collector.start_agent_run("Verification").finish(
            status="completed" if v_status == "PASS" else "degraded",
            output_payload={"status": v_status}
        )
        return collector.to_tree()

    return collector.to_tree()


# =====================================================================
# Subtasks & Queries
# =====================================================================

def save_subtasks(
    db: Session,
    session_id: str,
    subtasks_data: List[Dict[str, Any]]
) -> List[ResearchSubtask]:
    """Persist structured subtasks created by the Research Planner Agent."""
    results = []
    for item in subtasks_data:
        subtask = ResearchSubtask(
            id=generate_uuid(),
            session_id=session_id,
            subtask_id=str(item.get("subtask_id", f"subtask_{len(results) + 1}")),
            research_question=item.get("research_question", ""),
            search_queries=item.get("search_queries", []),
            status=item.get("status", "completed"),
            discovered_count=item.get("discovered_count", len(item.get("discovered_urls", []))),
            extracted_count=item.get("extracted_count", len(item.get("extracted_documents", []))),
            error_message=item.get("error_message") or item.get("error"),
        )
        db.add(subtask)
        results.append(subtask)
    db.commit()
    return results


def save_queries(
    db: Session,
    session_id: str,
    queries: List[str],
    query_type: str = "subtask"
) -> List[ResearchQuery]:
    """Persist search queries executed during research."""
    records = []
    for q in queries:
        if not q or not q.strip():
            continue
        record = ResearchQuery(
            id=generate_uuid(),
            session_id=session_id,
            query_text=q.strip(),
            query_type=query_type,
            is_executed=True,
        )
        db.add(record)
        records.append(record)
    db.commit()
    return records


# =====================================================================
# Sources & Evidence Chunks
# =====================================================================

def save_sources(
    db: Session,
    session_id: str,
    sources_data: List[Dict[str, Any]]
) -> List[Source]:
    """
    Persist discovered and profiled research sources with deterministic quality signals.
    Prevents duplicate URLs within the same session.
    """
    saved_sources = []
    seen_urls = set()

    for item in sources_data:
        url = item.get("url", "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)

        src = Source(
            id=generate_uuid(),
            session_id=session_id,
            source_id=item.get("source_id", f"S{len(saved_sources) + 1}"),
            url=url,
            domain=item.get("domain", "web"),
            title=item.get("title", "Web Source"),
            snippet=item.get("snippet", ""),
            full_text=item.get("full_text") or item.get("text", ""),
            source_type=item.get("source_type", "unknown"),
            publication_date=item.get("publication_date", "N/A"),
            freshness=item.get("freshness", "undated"),
            freshness_days=item.get("freshness_days", -1),
            authority_score=float(item.get("authority_score", 0.0)),
            quality_score=float(item.get("quality_score", 0.0)),
            quality_tier=item.get("quality_tier", "adequate"),
            is_duplicate=bool(item.get("is_duplicate", False)),
            duplicate_of=item.get("duplicate_of"),
            subtask_id=item.get("subtask_id"),
            authority_indicators=item.get("authority_indicators", []),
            penalties=item.get("penalties", []),
        )
        db.add(src)
        saved_sources.append(src)

    db.commit()
    for s in saved_sources:
        db.refresh(s)
    return saved_sources


def save_evidence_chunks(
    db: Session,
    session_id: str,
    chunks_data: List[Dict[str, Any]],
    source_id_map: Optional[Dict[str, str]] = None
) -> List[EvidenceChunk]:
    """
    Persist chunked evidence indexed into ChromaDB.
    source_id_map maps human-readable source_id (e.g. 'S1') or URL to internal Source.id UUID.
    """
    saved_chunks = []
    for item in chunks_data:
        # Determine foreign key source_id
        raw_source_ref = item.get("source_id", "")
        fk_source_id = None
        if source_id_map:
            fk_source_id = source_id_map.get(raw_source_ref) or source_id_map.get(item.get("url", ""))

        if not fk_source_id:
            # Fallback query
            src = db.execute(
                select(Source).where(
                    and_(
                        Source.session_id == session_id,
                        (Source.source_id == raw_source_ref) | (Source.url == item.get("url", ""))
                    )
                )
            ).scalars().first()
            if src:
                fk_source_id = src.id

        if not fk_source_id:
            # If no source matched, skip or create placeholder
            continue

        text = item.get("text", "")
        chunk = EvidenceChunk(
            id=generate_uuid(),
            session_id=session_id,
            source_id=fk_source_id,
            chunk_id=item.get("chunk_id", f"E{len(saved_chunks) + 1}"),
            chunk_index=int(item.get("chunk_index", len(saved_chunks))),
            text=text,
            char_count=len(text),
            token_count=int(item.get("token_count", len(text.split()))),
            chroma_id=item.get("chroma_id"),
        )
        db.add(chunk)
        saved_chunks.append(chunk)

    db.commit()
    for c in saved_chunks:
        db.refresh(c)
    return saved_chunks


def get_session_sources(db: Session, session_id: str) -> List[Source]:
    """Retrieve all sources for a specific session ordered by quality score."""
    stmt = (
        select(Source)
        .where(Source.session_id == session_id)
        .order_by(desc(Source.quality_score))
    )
    return list(db.execute(stmt).scalars().all())


def get_session_evidence(db: Session, session_id: str) -> List[EvidenceChunk]:
    """Retrieve all evidence chunks for a session."""
    stmt = (
        select(EvidenceChunk)
        .where(EvidenceChunk.session_id == session_id)
        .order_by(EvidenceChunk.chunk_index)
    )
    return list(db.execute(stmt).scalars().all())


# =====================================================================
# Claims & Grounding
# =====================================================================

def save_claims(
    db: Session,
    session_id: str,
    claims_data: List[Dict[str, Any]]
) -> List[Claim]:
    """Persist structured claims and their citation-grounded evidence links."""
    saved_claims = []
    for item in claims_data:
        text = item.get("text", "").strip()
        if not text:
            continue

        claim = Claim(
            id=generate_uuid(),
            session_id=session_id,
            claim_id=item.get("claim_id", f"C{len(saved_claims) + 1}"),
            text=text,
            confidence=float(item.get("confidence", 1.0)),
            status=item.get("status", "grounded"),
            supporting_source_ids=item.get("supporting_source_ids", []),
            evidence_chunk_ids=item.get("evidence_chunk_ids", []),
        )
        db.add(claim)
        saved_claims.append(claim)

    db.commit()
    for c in saved_claims:
        db.refresh(c)
    return saved_claims


def get_session_claims(db: Session, session_id: str) -> List[Claim]:
    """Retrieve claims synthesized for a research session."""
    stmt = select(Claim).where(Claim.session_id == session_id)
    return list(db.execute(stmt).scalars().all())


# =====================================================================
# Report Versioning
# =====================================================================

def save_report(
    db: Session,
    session_id: str,
    title: str,
    content_markdown: str,
    feedback: Optional[str] = None,
    score: Optional[str] = None,
    is_final: bool = True,
    citation_trace: Optional[Dict] = None,
    claims_count: int = 0,
    sources_count: int = 0
) -> Report:
    """
    Save a new report version for the session.
    Automatically increments version number.
    """
    latest = db.execute(
        select(Report)
        .where(Report.session_id == session_id)
        .order_by(desc(Report.version))
    ).scalars().first()

    version = (latest.version + 1) if latest else 1

    # If new report is marked final, unset earlier finals
    if is_final:
        earlier_finals = db.execute(
            select(Report).where(and_(Report.session_id == session_id, Report.is_final == True))
        ).scalars().all()
        for ef in earlier_finals:
            ef.is_final = False

    report = Report(
        id=generate_uuid(),
        session_id=session_id,
        version=version,
        title=title.strip(),
        content_markdown=content_markdown.strip(),
        feedback=feedback.strip() if feedback else None,
        score=score.strip() if score else None,
        is_final=is_final,
        claims_count=claims_count,
        sources_count=sources_count,
        citation_trace=citation_trace,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    logger.info("Saved report version %d for session %s (id: %s)", version, session_id, report.id)
    return report


def get_report(
    db: Session,
    session_id: str,
    version: Optional[int] = None
) -> Optional[Report]:
    """Retrieve a specific version of a report, or the latest/final version."""
    stmt = select(Report).where(Report.session_id == session_id)
    if version is not None:
        stmt = stmt.where(Report.version == version)
    else:
        # Prefer final, else highest version
        stmt = stmt.order_by(desc(Report.is_final), desc(Report.version))
    return db.execute(stmt).scalars().first()


def list_reports(db: Session, session_id: str) -> List[Report]:
    """List all report versions for a session."""
    stmt = (
        select(Report)
        .where(Report.session_id == session_id)
        .order_by(desc(Report.version))
    )
    return list(db.execute(stmt).scalars().all())


# =====================================================================
# Session Isolation Verification
# =====================================================================

def verify_session_isolation(
    db: Session,
    session_a_id: str,
    session_b_id: str
) -> Dict[str, Any]:
    """
    Verify complete strict isolation between two research sessions.
    Validates that:
    - Sources belong strictly to their parent session
    - Evidence chunks belong strictly to their parent session
    - Claims belong strictly to their parent session
    - Reports belong strictly to their parent session
    """
    sources_a = set(db.execute(select(Source.id).where(Source.session_id == session_a_id)).scalars().all())
    sources_b = set(db.execute(select(Source.id).where(Source.session_id == session_b_id)).scalars().all())

    chunks_a = set(db.execute(select(EvidenceChunk.id).where(EvidenceChunk.session_id == session_a_id)).scalars().all())
    chunks_b = set(db.execute(select(EvidenceChunk.id).where(EvidenceChunk.session_id == session_b_id)).scalars().all())

    claims_a = set(db.execute(select(Claim.id).where(Claim.session_id == session_a_id)).scalars().all())
    claims_b = set(db.execute(select(Claim.id).where(Claim.session_id == session_b_id)).scalars().all())

    reports_a = set(db.execute(select(Report.id).where(Report.session_id == session_a_id)).scalars().all())
    reports_b = set(db.execute(select(Report.id).where(Report.session_id == session_b_id)).scalars().all())

    sources_leak = sources_a.intersection(sources_b)
    chunks_leak = chunks_a.intersection(chunks_b)
    claims_leak = claims_a.intersection(claims_b)
    reports_leak = reports_a.intersection(reports_b)

    is_isolated = not (sources_leak or chunks_leak or claims_leak or reports_leak)

    return {
        "is_isolated": is_isolated,
        "session_a": {
            "sources_count": len(sources_a),
            "chunks_count": len(chunks_a),
            "claims_count": len(claims_a),
            "reports_count": len(reports_a),
        },
        "session_b": {
            "sources_count": len(sources_b),
            "chunks_count": len(chunks_b),
            "claims_count": len(claims_b),
            "reports_count": len(reports_b),
        },
        "leaks": {
            "sources": list(sources_leak),
            "chunks": list(chunks_leak),
            "claims": list(claims_leak),
            "reports": list(reports_leak),
        }
    }


# =====================================================================
# Complete Pipeline State Persistence
# =====================================================================

def persist_complete_research_state(
    db: Session,
    project_id: str,
    topic: str,
    state: Dict[str, Any]
) -> ResearchSession:
    """
    Save complete execution state from the multi-agent pipeline into the relational database.
    Creates or updates the ResearchSession, Sources, Claims, Subtasks, AgentRuns, and Reports.
    """
    session_id = state.get("session_id")
    session = None
    if session_id:
        session = get_session(db, session_id)

    if not session:
        session = create_session(
            db=db,
            project_id=project_id,
            topic=topic,
            session_id=session_id
        )

    # 1. Update session metadata
    plan = state.get("plan")
    evidence_summary = state.get("evidence_summary")
    verification_report = state.get("verification_report") or {}
    v_status = verification_report.get("status", "passed" if state.get("report") else "unverified")

    update_session_status(
        db=db,
        session_id=session.id,
        status="completed" if state.get("report") else "failed",
        verification_status=v_status,
        verification_iteration=state.get("verification_iteration", 0),
        plan_data=plan if isinstance(plan, dict) else None,
        evidence_summary=evidence_summary if isinstance(evidence_summary, dict) else None,
        metadata_json={
            "session_id": session.id,
            "verification_confidence": verification_report.get("confidence", 1.0),
        }
    )

    # 2. Persist Subtasks
    subtasks_data = state.get("subtask_results", [])
    if subtasks_data:
        save_subtasks(db, session.id, subtasks_data)

    # 3. Persist Sources
    sources_to_save = []
    # Profiles from source quality engine
    if state.get("source_quality_profiles"):
        sources_to_save.extend(state["source_quality_profiles"])
    # Fallback to sources registry
    if not sources_to_save and state.get("sources"):
        raw_sources = state["sources"]
        if isinstance(raw_sources, dict):
            sources_to_save.extend(raw_sources.values())
        elif isinstance(raw_sources, list):
            sources_to_save.extend(raw_sources)

    created_sources = []
    if sources_to_save:
        created_sources = save_sources(db, session.id, sources_to_save)

    # Build source lookup map: human id -> UUID
    source_id_map = {s.source_id: s.id for s in created_sources}
    for s in created_sources:
        source_id_map[s.url] = s.id

    # 4. Persist Evidence Chunks
    retrieved_evidence = state.get("retrieved_evidence", [])
    if retrieved_evidence:
        save_evidence_chunks(db, session.id, retrieved_evidence, source_id_map)

    # 5. Persist Claims
    claims_to_save = []
    if state.get("claims"):
        claims_to_save.extend(state["claims"])
    elif state.get("grounded_claims"):
        claims_to_save.extend(state["grounded_claims"])
    if state.get("unsupported_claims"):
        for uc in state["unsupported_claims"]:
            if isinstance(uc, dict):
                uc_copy = dict(uc)
                uc_copy["status"] = "unsupported"
                claims_to_save.append(uc_copy)

    if claims_to_save:
        save_claims(db, session.id, claims_to_save)

    # 6. Persist Agent Runs Telemetry
    if state.get("agent_runs") and isinstance(state["agent_runs"], list):
        save_agent_telemetry(db, session.id, state["agent_runs"])
    elif state.get("telemetry") and isinstance(state["telemetry"], dict) and state["telemetry"].get("agents"):
        save_agent_telemetry(db, session.id, state["telemetry"]["agents"])
    else:
        # Fallback to recording canonical agent runs
        if state.get("plan"):
            record_agent_run(
                db, session.id, "planner", "completed",
                output_payload={"objective": (plan or {}).get("research_objective", "")}
            )
        if state.get("search_results"):
            record_agent_run(db, session.id, "search", "completed")
        if state.get("scraped_content"):
            record_agent_run(db, session.id, "reader", "completed")
        if state.get("evidence_summary"):
            record_agent_run(
                db, session.id, "retrieval", "completed",
                output_payload=state.get("evidence_summary")
            )
        if state.get("report"):
            record_agent_run(
                db, session.id, "writer", "completed",
                output_payload={"words": len(state["report"].split())}
            )
        if state.get("verification_report"):
            record_agent_run(
                db, session.id, "verifier", "completed",
                output_payload=state["verification_report"],
                iteration=state.get("verification_iteration", 0)
            )

    # 7. Persist Report
    report_text = state.get("report", "")
    if report_text:
        feedback = state.get("feedback", "")
        # Extract score if present
        score = None
        if "Score:" in feedback:
            try:
                score = feedback.split("Score:")[1].split("\n")[0].strip()
            except Exception:
                pass

        save_report(
            db=db,
            session_id=session.id,
            title=f"Report: {topic[:80].strip()}",
            content_markdown=report_text,
            feedback=feedback,
            score=score,
            is_final=True,
            citation_trace=state.get("citation_trace"),
            claims_count=len(claims_to_save),
            sources_count=len(created_sources),
        )

    db.refresh(session)
    return session


# =====================================================================
# Research Dossier Export
# =====================================================================

def export_session_dossier(db: Session, session_id: str) -> Dict[str, Any]:
    """
    Generate a comprehensive research session dossier.
    Packages:
    - Session metadata (topic, status, timestamps, verification cycle)
    - Associated Project metadata
    - Research Plan (objective, subtasks, queries, strategy)
    - Latest Report & Version History
    - Evidence & Claim Lineage (Claim -> Evidence -> Source -> URL)
    - Source Quality Registry (domain, publication date, freshness, type, scores)
    - Agent Telemetry & Execution Tree
    - Fully consolidated Markdown dossier document
    """
    session = get_session(db, session_id)
    if not session:
        return {}

    project = session.project
    report = get_report(db, session_id)
    all_reports = list_reports(db, session_id)
    sources = list(session.sources or [])
    claims = list(session.claims or [])
    subtasks = list(session.subtasks or [])
    chunks = list(session.evidence_chunks or [])
    telemetry = get_session_telemetry_tree(db, session_id)

    # Format Markdown dossier
    lines = [
        f"# SYNAPSE AI — Research Dossier",
        f"**Topic**: {session.topic}",
        f"**Session ID**: `{session.id}`",
        f"**Project**: {project.title if project else 'Standalone Session'}",
        f"**Status**: {session.status.upper() if session.status else 'UNKNOWN'}",
        f"**Verification Status**: {session.verification_status.upper() if session.verification_status else 'UNKNOWN'} (Cycle {session.verification_iteration})",
        f"**Generated At**: {session.created_at.strftime('%Y-%m-%d %H:%M:%S UTC') if session.created_at else 'N/A'}",
        "",
        "---",
        "",
        "## 1. Executive Research Report",
        "",
        report.content_markdown if report else "*No report content synthesized for this session.*",
        "",
        "---",
        "",
        "## 2. Research Plan & Subtask Strategy",
        "",
    ]

    plan = session.plan_data or {}
    if plan:
        lines.append(f"**Objective**: {plan.get('research_objective', session.topic)}")
        if plan.get("strategy"):
            lines.append(f"\n**Strategy**: {plan.get('strategy')}\n")
    if subtasks:
        lines.append("### Subtasks Decomposed:")
        for idx, st in enumerate(subtasks, 1):
            q_text = getattr(st, 'research_question', None) or getattr(st, 'question', f"Subtask {idx}")
            lines.append(f"{idx}. **{q_text}** [Status: {st.status}]")
            if st.search_queries:
                lines.append(f"   *Queries*: {', '.join(st.search_queries)}")
    lines.append("\n---\n")

    lines.append("## 3. Verified Claims & Grounding Lineage")
    lines.append("")
    if claims:
        grounded = [c for c in claims if c.status == "grounded"]
        unsupported = [c for c in claims if c.status == "unsupported"]
        insufficient = [c for c in claims if c.status == "insufficient"]
        lines.append(f"*Summary: {len(grounded)} grounded, {len(insufficient)} insufficient, {len(unsupported)} unsupported claims.*\n")

        for idx, c in enumerate(claims, 1):
            icon = "✅" if c.status == "grounded" else "⚠️" if c.status == "insufficient" else "❌"
            conf = f"{int(c.confidence * 100)}%" if c.confidence is not None else "N/A"
            lines.append(f"### Claim {idx}: {c.text}")
            lines.append(f"- **Status**: {icon} {c.status.capitalize()} (Confidence: {conf})")
            if c.verification_notes:
                lines.append(f"- **Verification Notes**: {c.verification_notes}")
            if c.evidence_links:
                lines.append("- **Supporting Evidence Links**:")
                for el in c.evidence_links:
                    lines.append(f"  - Chunk `{el.chunk_id}` (similarity: {el.similarity_score:.2f})")
            lines.append("")
    else:
        lines.append("*No claim audit records logged.*")

    lines.append("\n---\n")
    lines.append("## 4. Source Quality & Freshness Registry")
    lines.append("")
    if sources:
        lines.append("| Title | Domain | Type | Freshness | Published | Quality Score |")
        lines.append("|-------|--------|------|-----------|-----------|---------------|")
        for s in sources:
            fresh = s.freshness or "undated"
            pub = s.publication_date or "N/A"
            score = f"{s.composite_score:.2f}" if s.composite_score is not None else "—"
            lines.append(f"| [{s.title or s.url}]({s.url}) | {s.domain or '—'} | {s.source_type or '—'} | {fresh} | {pub} | {score} |")
    else:
        lines.append("*No sources indexed.*")

    lines.append("\n---\n")
    lines.append("## 5. Report Version Audit Trail")
    lines.append("")
    if all_reports:
        for r in all_reports:
            lines.append(f"- **Version {r.version}** ({'Final' if r.is_final else 'Draft'}): Words: {r.word_count}, Confidence: {int(r.confidence_score * 100)}%, Created: {r.created_at}")
            if r.feedback:
                lines.append(f"  *Verification Feedback*: {r.feedback}")
    else:
        lines.append("*No version history logged.*")

    lines.append("\n---\n")
    lines.append("## 6. Multi-Agent Telemetry Summary")
    lines.append("")
    if telemetry and telemetry.get("agents"):
        for a in telemetry["agents"]:
            lines.append(f"- **Agent `{a.get('name')}`**: Status: {a.get('status')}, Duration: {a.get('duration')}s, Retries: {a.get('retry_count')}, Tools: {len(a.get('tool_calls', []))}")
            if a.get("errors"):
                for err in a["errors"]:
                    lines.append(f"  - ⚠️ Error: {err.get('message')}")

    dossier_md = "\n".join(lines)

    return {
        "session_id": session.id,
        "topic": session.topic,
        "status": session.status,
        "verification_status": session.verification_status,
        "verification_iteration": session.verification_iteration,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "project": project.to_dict() if project else None,
        "plan": session.plan_data or {},
        "subtasks": [st.to_dict() for st in subtasks],
        "report": report.to_dict() if report else None,
        "report_versions": [r.to_dict() for r in all_reports],
        "claims": [c.to_dict() for c in claims],
        "sources": [s.to_dict() for s in sources],
        "evidence_chunks": [ec.to_dict() for ec in chunks],
        "telemetry": telemetry,
        "dossier_markdown": dossier_md,
    }

