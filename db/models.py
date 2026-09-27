"""
SYNAPSE AI — Persistent Research Workspace SQLAlchemy Models.

Defines 10 core workspace entities with:
- Strict foreign-key constraints (CASCADE deletes)
- Indexes on frequently queried lookup and filter fields
- Comprehensive timestamp tracking (UTC)
- Robust JSON metadata storage
- Serialization helper methods
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


def generate_uuid() -> str:
    """Generate a clean UUID string."""
    return str(uuid.uuid4())


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


# =====================================================================
# 1. User
# =====================================================================
class User(Base):
    """
    User entity representing a research owner or analyst.
    """
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=True, index=True)
    full_name = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    projects = relationship(
        "ResearchProject",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="desc(ResearchProject.created_at)",
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "email": self.email,
            "username": self.username,
            "full_name": self.full_name,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "projects_count": len(self.projects) if self.projects else 0,
        }


# =====================================================================
# 2. ResearchProject
# =====================================================================
class ResearchProject(Base):
    """
    Research Project grouping related research topics, sessions, and artifacts.
    """
    __tablename__ = "research_projects"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="active", nullable=False, index=True)  # active | archived | completed
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    user = relationship("User", back_populates="projects")
    sessions = relationship(
        "ResearchSession",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="desc(ResearchSession.created_at)",
    )

    __table_args__ = (
        Index("ix_project_user_status", "user_id", "status"),
        Index("ix_project_created", "created_at"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "sessions_count": len(self.sessions) if self.sessions else 0,
        }


# =====================================================================
# 3. ResearchSession
# =====================================================================
class ResearchSession(Base):
    """
    Core research session isolating a specific topic inquiry, subtasks,
    retrieved evidence, and verified reports.
    """
    __tablename__ = "research_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    session_name = Column(String(255), nullable=False)
    topic = Column(Text, nullable=False, index=True)
    status = Column(String(50), default="pending", nullable=False, index=True)  # pending|running|completed|failed|verified
    verification_status = Column(String(50), default="unverified", nullable=False, index=True)  # unverified|passed|research_required|max_iterations
    verification_iteration = Column(Integer, default=0, nullable=False)
    plan_data = Column(JSON, nullable=True)
    evidence_summary = Column(JSON, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    project = relationship("ResearchProject", back_populates="sessions")
    queries = relationship("ResearchQuery", back_populates="session", cascade="all, delete-orphan")
    subtasks = relationship("ResearchSubtask", back_populates="session", cascade="all, delete-orphan")
    sources = relationship("Source", back_populates="session", cascade="all, delete-orphan")
    evidence_chunks = relationship("EvidenceChunk", back_populates="session", cascade="all, delete-orphan")
    claims = relationship("Claim", back_populates="session", cascade="all, delete-orphan")
    agent_runs = relationship("AgentRun", back_populates="session", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_session_project_status", "project_id", "status"),
        Index("ix_session_created", "created_at"),
    )

    def to_dict(self, include_details: bool = False) -> Dict[str, Any]:
        data = {
            "id": self.id,
            "project_id": self.project_id,
            "session_name": self.session_name,
            "topic": self.topic,
            "status": self.status,
            "verification_status": self.verification_status,
            "verification_iteration": self.verification_iteration,
            "plan_data": self.plan_data,
            "evidence_summary": self.evidence_summary,
            "metadata_json": self.metadata_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "sources_count": len(self.sources) if self.sources else 0,
            "reports_count": len(self.reports) if self.reports else 0,
            "claims_count": len(self.claims) if self.claims else 0,
        }
        if include_details:
            data.update({
                "subtasks": [s.to_dict() for s in (self.subtasks or [])],
                "sources": [s.to_dict() for s in (self.sources or [])],
                "reports": [r.to_dict() for r in (self.reports or [])],
                "claims": [c.to_dict() for c in (self.claims or [])],
                "agent_runs": [a.to_dict() for a in (self.agent_runs or [])],
            })
        return data


# =====================================================================
# 4. ResearchQuery
# =====================================================================
class ResearchQuery(Base):
    """
    Search queries generated by Planner, Search Agent, or Verifier gaps.
    """
    __tablename__ = "research_queries"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    query_text = Column(Text, nullable=False)
    query_type = Column(String(50), default="initial", nullable=False, index=True)  # initial | subtask | follow_up | verification_gap
    is_executed = Column(Boolean, default=False, nullable=False)
    results_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    session = relationship("ResearchSession", back_populates="queries")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "query_text": self.query_text,
            "query_type": self.query_type,
            "is_executed": self.is_executed,
            "results_count": self.results_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# =====================================================================
# 5. ResearchSubtask
# =====================================================================
class ResearchSubtask(Base):
    """
    Independent research subtask decomposed by the Planner and executed concurrently.
    """
    __tablename__ = "research_subtasks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    subtask_id = Column(String(100), nullable=False, index=True)  # e.g. subtask_1
    research_question = Column(Text, nullable=False)
    search_queries = Column(JSON, default=list, nullable=False)
    status = Column(String(50), default="pending", nullable=False, index=True)  # pending|in_progress|completed|failed
    discovered_count = Column(Integer, default=0, nullable=False)
    extracted_count = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    session = relationship("ResearchSession", back_populates="subtasks")

    __table_args__ = (
        Index("ix_subtask_session_id", "session_id", "subtask_id"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "subtask_id": self.subtask_id,
            "research_question": self.research_question,
            "search_queries": self.search_queries,
            "status": self.status,
            "discovered_count": self.discovered_count,
            "extracted_count": self.extracted_count,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# =====================================================================
# 6. Source
# =====================================================================
class Source(Base):
    """
    Discovered web source with deterministic quality, authority, and freshness profiles.
    """
    __tablename__ = "sources"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id = Column(String(100), nullable=False, index=True)  # S1, S2, src_abc
    url = Column(Text, nullable=False, index=True)
    domain = Column(String(255), nullable=False, index=True)
    title = Column(Text, default="Web Source", nullable=False)
    snippet = Column(Text, nullable=True)
    full_text = Column(Text, nullable=True)
    source_type = Column(String(50), default="unknown", nullable=False, index=True)  # official|academic|news|industry|company|general|unknown
    publication_date = Column(String(50), default="N/A", nullable=False)
    retrieval_date = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    freshness = Column(String(50), default="undated", nullable=False, index=True)  # current|recent|aging|stale|undated
    freshness_days = Column(Integer, default=-1, nullable=False)
    authority_score = Column(Float, default=0.0, nullable=False)
    quality_score = Column(Float, default=0.0, nullable=False, index=True)
    quality_tier = Column(String(50), default="adequate", nullable=False, index=True)  # excellent|good|adequate|low|poor
    is_duplicate = Column(Boolean, default=False, nullable=False, index=True)
    duplicate_of = Column(String(100), nullable=True)
    subtask_id = Column(String(100), nullable=True)
    authority_indicators = Column(JSON, default=list, nullable=False)
    penalties = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    session = relationship("ResearchSession", back_populates="sources")
    evidence_chunks = relationship("EvidenceChunk", back_populates="source", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_source_session_quality", "session_id", "quality_score"),
        Index("ix_source_session_type", "session_id", "source_type"),
        Index("ix_source_domain", "domain"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "source_id": self.source_id,
            "url": self.url,
            "domain": self.domain,
            "title": self.title,
            "snippet": self.snippet,
            "source_type": self.source_type,
            "publication_date": self.publication_date,
            "freshness": self.freshness,
            "freshness_days": self.freshness_days,
            "authority_score": self.authority_score,
            "quality_score": self.quality_score,
            "quality_tier": self.quality_tier,
            "is_duplicate": self.is_duplicate,
            "duplicate_of": self.duplicate_of,
            "subtask_id": self.subtask_id,
            "authority_indicators": self.authority_indicators,
            "penalties": self.penalties,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# =====================================================================
# 7. EvidenceChunk
# =====================================================================
class EvidenceChunk(Base):
    """
    Extracted text chunk indexed into the semantic vector store (ChromaDB)
    and mapped back to the origin source.
    """
    __tablename__ = "evidence_chunks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id = Column(String(36), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_id = Column(String(100), nullable=False, index=True)  # E1, E2, chunk_abc_0
    chunk_index = Column(Integer, default=0, nullable=False)
    text = Column(Text, nullable=False)
    char_count = Column(Integer, default=0, nullable=False)
    token_count = Column(Integer, default=0, nullable=False)
    chroma_id = Column(String(255), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    session = relationship("ResearchSession", back_populates="evidence_chunks")
    source = relationship("Source", back_populates="evidence_chunks")
    claim_links = relationship("ClaimEvidenceLink", back_populates="evidence_chunk", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_chunk_session_chunkid", "session_id", "chunk_id"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "source_id": self.source_id,
            "chunk_id": self.chunk_id,
            "chunk_index": self.chunk_index,
            "text": self.text,
            "char_count": self.char_count,
            "token_count": self.token_count,
            "chroma_id": self.chroma_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# =====================================================================
# 8. Claim
# =====================================================================
class Claim(Base):
    """
    Factual claim synthesized in the report with explicit evidence grounding.
    """
    __tablename__ = "claims"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    claim_id = Column(String(100), nullable=False, index=True)  # C1, C2
    text = Column(Text, nullable=False)
    confidence = Column(Float, default=1.0, nullable=False)
    status = Column(String(50), default="grounded", nullable=False, index=True)  # grounded | unsupported | insufficient
    supporting_source_ids = Column(JSON, default=list, nullable=False)
    evidence_chunk_ids = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    session = relationship("ResearchSession", back_populates="claims")
    evidence_links = relationship("ClaimEvidenceLink", back_populates="claim", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_claim_session_status", "session_id", "status"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "claim_id": self.claim_id,
            "text": self.text,
            "confidence": self.confidence,
            "status": self.status,
            "supporting_source_ids": self.supporting_source_ids,
            "evidence_chunk_ids": self.evidence_chunk_ids,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# =====================================================================
# 9. ClaimEvidenceLink (Association / Relationship)
# =====================================================================
class ClaimEvidenceLink(Base):
    """
    Explicit relational mapping connecting a Claim to its supporting EvidenceChunk and Source.
    """
    __tablename__ = "claim_evidence_links"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    claim_id = Column(String(36), ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_chunk_id = Column(String(36), ForeignKey("evidence_chunks.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id = Column(String(36), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    claim = relationship("Claim", back_populates="evidence_links")
    evidence_chunk = relationship("EvidenceChunk", back_populates="claim_links")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "claim_id": self.claim_id,
            "evidence_chunk_id": self.evidence_chunk_id,
            "source_id": self.source_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# =====================================================================
# 10. AgentRun
# =====================================================================
class AgentRun(Base):
    """
    Execution run telemetry for individual agents (planner, search, reader, writer, verifier).
    """
    __tablename__ = "agent_runs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_name = Column(String(100), nullable=False, index=True)  # planner|search|reader|writer|verifier
    status = Column(String(50), default="running", nullable=False, index=True)  # running|completed|failed|skipped
    iteration = Column(Integer, default=0, nullable=False)
    execution_time_seconds = Column(Float, default=0.0, nullable=False)
    input_payload = Column(JSON, nullable=True)
    output_payload = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    metrics = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    session = relationship("ResearchSession", back_populates="agent_runs")

    __table_args__ = (
        Index("ix_agentrun_session_agent", "session_id", "agent_name"),
        Index("ix_agentrun_created", "created_at"),
    )

    def to_dict(self) -> Dict[str, Any]:
        m = self.metrics or {}
        start_iso = self.created_at.isoformat() if self.created_at else None
        end_iso = self.completed_at.isoformat() if self.completed_at else None
        errs = m.get("errors") or ([self.error_message] if self.error_message else [])
        
        data = {
            "run_id": self.id,
            "id": self.id,
            "session_id": self.session_id,
            "agent_name": self.agent_name,
            "start_time": m.get("start_time") or start_iso,
            "end_time": m.get("end_time") or end_iso,
            "duration": round(float(self.execution_time_seconds or 0.0), 3),
            "execution_time_seconds": round(float(self.execution_time_seconds or 0.0), 3),
            "status": self.status,
            "retry_count": int(m.get("retry_count", 0)),
            "tool_calls": m.get("tool_calls", []),
            "search_queries": m.get("search_queries", []),
            "urls_discovered": m.get("urls_discovered", []),
            "urls_extracted": m.get("urls_extracted", []),
            "evidence_chunks_created": int(m.get("evidence_chunks_created", 0)),
            "model_used": m.get("model_used") or m.get("model"),
            "token_usage": m.get("token_usage"),
            "errors": errs,
            "iteration_number": self.iteration,
            "iteration": self.iteration,
            "input_payload": self.input_payload,
            "output_payload": self.output_payload,
            "error_message": self.error_message,
            "metrics": m,
            "created_at": start_iso,
            "completed_at": end_iso,
        }
        try:
            from telemetry import sanitize_telemetry
            return sanitize_telemetry(data)
        except Exception:
            return data


# =====================================================================
# 11. Report
# =====================================================================
class Report(Base):
    """
    Grounded research report versions with citation trace and quality review feedback.
    """
    __tablename__ = "reports"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, default=1, nullable=False, index=True)
    title = Column(String(255), nullable=False, index=True)
    content_markdown = Column(Text, nullable=False)
    feedback = Column(Text, nullable=True)  # Critic / Verification review
    score = Column(String(50), nullable=True)
    is_final = Column(Boolean, default=True, nullable=False, index=True)
    claims_count = Column(Integer, default=0, nullable=False)
    sources_count = Column(Integer, default=0, nullable=False)
    citation_trace = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    session = relationship("ResearchSession", back_populates="reports")

    __table_args__ = (
        Index("ix_report_session_version", "session_id", "version"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "version": self.version,
            "title": self.title,
            "content_markdown": self.content_markdown,
            "feedback": self.feedback,
            "score": self.score,
            "is_final": self.is_final,
            "claims_count": self.claims_count,
            "sources_count": self.sources_count,
            "citation_trace": self.citation_trace,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
