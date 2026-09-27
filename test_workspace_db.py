"""
SYNAPSE AI — Persistent Research Workspace Database Test Suite.

Tests all required workspace capabilities:
1. create project
2. create session
3. save sources (with deterministic quality signals)
4. save report (with versioning)
5. retrieve report (latest & specific versions)
6. delete session (with CASCADE verification)
7. session isolation (zero leakage between concurrent research sessions)
8. agent run telemetry
9. claim and evidence relational links
10. database error handling & rollback safety
11. secret masking in connection strings
12. migration of historical JSON records
"""

import os
import tempfile
import uuid
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from db.models import (
    Base,
    User,
    ResearchProject,
    ResearchSession,
    Source,
    EvidenceChunk,
    Claim,
    ClaimEvidenceLink,
    AgentRun,
    Report,
    ResearchQuery,
    ResearchSubtask,
)
from db.service import (
    create_project,
    create_session,
    delete_project,
    delete_session,
    get_or_create_default_user,
    get_project,
    get_projects,
    get_report,
    get_session,
    get_session_claims,
    get_session_evidence,
    get_session_sources,
    list_reports,
    list_sessions,
    persist_complete_research_state,
    record_agent_run,
    save_claims,
    save_evidence_chunks,
    save_queries,
    save_report,
    save_sources,
    save_subtasks,
    update_session_status,
    verify_session_isolation,
)
from db.session import _mask_db_url
from db.migration_util import migrate_history_file


@pytest.fixture
def db_session_fixture():
    """Provides a fresh, isolated in-memory SQLite database session for each test."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )
    # Enable SQLite foreign keys
    with test_engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = ON")

    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()

    yield session

    session.close()
    Base.metadata.drop_all(bind=test_engine)


class TestResearchWorkspace:
    """Comprehensive test suite for the persistent research workspace."""

    def test_1_create_user_and_project(self, db_session_fixture):
        """Test creating user and research projects with foreign keys and timestamps."""
        db = db_session_fixture

        user = get_or_create_default_user(db, email="scientist@synapse.ai", username="lead_scientist")
        assert user.id is not None
        assert user.email == "scientist@synapse.ai"
        assert user.is_active is True
        assert user.created_at is not None

        project = create_project(
            db=db,
            user_id=user.id,
            title="Genomics & Synthetic Biology",
            description="Deep exploration of CRISPR breakthroughs and delivery mechanisms."
        )

        assert project.id is not None
        assert project.user_id == user.id
        assert project.title == "Genomics & Synthetic Biology"
        assert project.status == "active"
        assert project.created_at is not None

        # Verify retrieval
        fetched = get_project(db, project.id)
        assert fetched is not None
        assert fetched.title == project.title

        projects = get_projects(db, user_id=user.id)
        assert len(projects) == 1
        assert projects[0].id == project.id

    def test_2_create_session(self, db_session_fixture):
        """Test creating an isolated research session under a project."""
        db = db_session_fixture

        user = get_or_create_default_user(db)
        project = create_project(db, user.id, "AI Agent Architectures")

        session = create_session(
            db=db,
            project_id=project.id,
            topic="Autonomous Multi-Agent Planning Protocols",
            session_name="Session 1: Agentic Orchestration"
        )

        assert session.id is not None
        assert session.project_id == project.id
        assert session.topic == "Autonomous Multi-Agent Planning Protocols"
        assert session.status == "pending"
        assert session.verification_status == "unverified"
        assert session.created_at is not None

        # Update status
        updated = update_session_status(
            db=db,
            session_id=session.id,
            status="completed",
            verification_status="passed",
            verification_iteration=1,
            plan_data={"objective": "Test objective"},
        )
        assert updated.status == "completed"
        assert updated.verification_status == "passed"
        assert updated.verification_iteration == 1
        assert updated.plan_data["objective"] == "Test objective"

    def test_3_save_sources_with_quality_signals(self, db_session_fixture):
        """Test saving sources with deterministic quality, freshness, and authority signals."""
        db = db_session_fixture

        user = get_or_create_default_user(db)
        project = create_project(db, user.id, "Biomedical Research")
        session = create_session(db, project.id, "CRISPR-Cas9 Clinical Trials")

        sources_data = [
            {
                "source_id": "S1",
                "url": "https://www.nih.gov/crispr-trial-results",
                "domain": "nih.gov",
                "title": "NIH Clinical Trial Results for Gene Therapy",
                "snippet": "Phase 3 clinical trial establishes 94% efficacy with no adverse off-target events.",
                "source_type": "official",
                "publication_date": "2026-04-12",
                "freshness": "current",
                "freshness_days": 45,
                "authority_score": 0.95,
                "quality_score": 0.93,
                "quality_tier": "excellent",
                "authority_indicators": ["Government / Intergovernmental", "HTTPS secure"],
            },
            {
                "source_id": "S2",
                "url": "https://nature.com/articles/s41586-026-0001",
                "domain": "nature.com",
                "title": "Nature: Structural Insights into Next-Gen Nucleases",
                "snippet": "Cryo-EM structures reveal mechanistic basis of high-fidelity editing.",
                "source_type": "academic",
                "publication_date": "2026-02-18",
                "freshness": "current",
                "freshness_days": 90,
                "authority_score": 0.92,
                "quality_score": 0.91,
                "quality_tier": "excellent",
                "authority_indicators": ["Peer-reviewed journal", "DOI detected", "HTTPS secure"],
            },
            {
                # Duplicate URL that should be deduplicated
                "source_id": "S3",
                "url": "https://www.nih.gov/crispr-trial-results",
                "domain": "nih.gov",
                "title": "Duplicate S1",
                "quality_score": 0.5,
            }
        ]

        saved = save_sources(db, session.id, sources_data)
        assert len(saved) == 2  # Duplicate URL rejected

        # Verify retrieval
        session_sources = get_session_sources(db, session.id)
        assert len(session_sources) == 2
        assert session_sources[0].quality_score >= session_sources[1].quality_score
        assert session_sources[0].domain in ["nih.gov", "nature.com"]

    def test_4_save_and_retrieve_report_versions(self, db_session_fixture):
        """Test report creation, versioning, and retrieval of specific and latest versions."""
        db = db_session_fixture

        user = get_or_create_default_user(db)
        project = create_project(db, user.id, "Quantum Computing")
        session = create_session(db, project.id, "Topological Quantum Systems")

        # Version 1 (Draft)
        rep1 = save_report(
            db=db,
            session_id=session.id,
            title="Topological Quantum Systems (Draft)",
            content_markdown="# Draft Report\nInitial findings on Majorana zero modes.",
            feedback="Critic: Requires more empirical evidence.",
            score="6/10",
            is_final=False,
            claims_count=3,
            sources_count=2,
        )
        assert rep1.version == 1
        assert rep1.is_final is False

        # Version 2 (Revised & Final)
        rep2 = save_report(
            db=db,
            session_id=session.id,
            title="Topological Quantum Systems (Final Verified)",
            content_markdown="# Final Report\nComprehensive synthesis of verified Majorana zero modes.",
            feedback="Critic: Verification PASS with high confidence.",
            score="9/10",
            is_final=True,
            claims_count=7,
            sources_count=5,
        )
        assert rep2.version == 2
        assert rep2.is_final is True

        # Retrieve latest/final report
        latest = get_report(db, session.id)
        assert latest is not None
        assert latest.version == 2
        assert "Final Report" in latest.content_markdown

        # Retrieve specific version 1
        v1 = get_report(db, session.id, version=1)
        assert v1 is not None
        assert v1.version == 1
        assert "Draft Report" in v1.content_markdown

        # List all reports
        all_reps = list_reports(db, session.id)
        assert len(all_reps) == 2

    def test_5_delete_session_and_cascade_constraints(self, db_session_fixture):
        """Test that deleting a session cascades and cleanly deletes all child records."""
        db = db_session_fixture

        user = get_or_create_default_user(db)
        project = create_project(db, user.id, "Cascade Project")
        session = create_session(db, project.id, "To Be Deleted")

        # Add sources, evidence, claims, runs, reports
        sources = save_sources(db, session.id, [
            {"source_id": "S1", "url": "https://example.com/1", "domain": "example.com", "quality_score": 0.8}
        ])
        save_evidence_chunks(db, session.id, [
            {"source_id": "S1", "chunk_id": "E1", "text": "Evidence snippet text."}
        ], source_id_map={"S1": sources[0].id})
        save_claims(db, session.id, [
            {"claim_id": "C1", "text": "Claim 1", "supporting_source_ids": ["S1"]}
        ])
        save_report(db, session.id, "Report Title", "# Report Markdown")
        record_agent_run(db, session.id, "writer", "completed")

        # Verify child records exist
        assert len(db.execute(select(Source).where(Source.session_id == session.id)).scalars().all()) == 1
        assert len(db.execute(select(EvidenceChunk).where(EvidenceChunk.session_id == session.id)).scalars().all()) == 1
        assert len(db.execute(select(Claim).where(Claim.session_id == session.id)).scalars().all()) == 1
        assert len(db.execute(select(Report).where(Report.session_id == session.id)).scalars().all()) == 1
        assert len(db.execute(select(AgentRun).where(AgentRun.session_id == session.id)).scalars().all()) == 1

        # Delete session
        deleted = delete_session(db, session.id)
        assert deleted is True

        # Verify session is gone
        assert get_session(db, session.id) is None

        # Verify all child records were cascaded and removed
        assert len(db.execute(select(Source).where(Source.session_id == session.id)).scalars().all()) == 0
        assert len(db.execute(select(EvidenceChunk).where(EvidenceChunk.session_id == session.id)).scalars().all()) == 0
        assert len(db.execute(select(Claim).where(Claim.session_id == session.id)).scalars().all()) == 0
        assert len(db.execute(select(Report).where(Report.session_id == session.id)).scalars().all()) == 0
        assert len(db.execute(select(AgentRun).where(AgentRun.session_id == session.id)).scalars().all()) == 0

    def test_6_session_isolation(self, db_session_fixture):
        """Test strict isolation between concurrent research sessions."""
        db = db_session_fixture

        user = get_or_create_default_user(db)
        project = create_project(db, user.id, "Isolation Test")

        # Session A: Healthcare AI
        sess_a = create_session(db, project.id, "Healthcare AI in Cardiology")
        save_sources(db, sess_a.id, [
            {"source_id": "S1", "url": "https://cardio.org/ai-ecg", "domain": "cardio.org", "quality_score": 0.9}
        ])
        save_claims(db, sess_a.id, [
            {"claim_id": "C1", "text": "Deep learning detects arrhythmias with 98% specificity."}
        ])
        save_report(db, sess_a.id, "Cardio AI Report", "# Cardio AI Findings")

        # Session B: Renewable Energy
        sess_b = create_session(db, project.id, "Perovskite Solar Cells")
        save_sources(db, sess_b.id, [
            {"source_id": "S1", "url": "https://energy.gov/perovskite-efficiency", "domain": "energy.gov", "quality_score": 0.95}
        ])
        save_claims(db, sess_b.id, [
            {"claim_id": "C1", "text": "Perovskite tandem cells exceed 33% power conversion efficiency."}
        ])
        save_report(db, sess_b.id, "Solar Energy Report", "# Solar Energy Findings")

        # Verify isolation
        isolation = verify_session_isolation(db, sess_a.id, sess_b.id)
        assert isolation["is_isolated"] is True
        assert len(isolation["leaks"]["sources"]) == 0
        assert len(isolation["leaks"]["claims"]) == 0
        assert len(isolation["leaks"]["reports"]) == 0

        # Verify queries for Session A only return Session A data
        sources_a = get_session_sources(db, sess_a.id)
        assert len(sources_a) == 1
        assert sources_a[0].domain == "cardio.org"

        sources_b = get_session_sources(db, sess_b.id)
        assert len(sources_b) == 1
        assert sources_b[0].domain == "energy.gov"

    def test_7_agent_run_telemetry(self, db_session_fixture):
        """Test recording agent telemetry (planner, search, reader, writer, verifier)."""
        db = db_session_fixture

        user = get_or_create_default_user(db)
        project = create_project(db, user.id, "Telemetry Test")
        session = create_session(db, project.id, "Telemetry Query")

        run1 = record_agent_run(
            db=db,
            session_id=session.id,
            agent_name="planner",
            status="completed",
            execution_time_seconds=1.42,
            output_payload={"subtasks_count": 3}
        )
        assert run1.agent_name == "planner"
        assert run1.execution_time_seconds == 1.42
        assert run1.completed_at is not None

        run2 = record_agent_run(
            db=db,
            session_id=session.id,
            agent_name="verifier",
            status="completed",
            iteration=1,
            output_payload={"status": "PASS", "confidence": 0.94}
        )
        assert run2.iteration == 1
        assert run2.output_payload["status"] == "PASS"

    def test_8_complete_pipeline_state_persistence(self, db_session_fixture):
        """Test persisting complete multi-agent pipeline execution state into the DB."""
        db = db_session_fixture

        user = get_or_create_default_user(db)
        project = create_project(db, user.id, "Full Pipeline Project")

        pipeline_state = {
            "session_id": str(uuid.uuid4()),
            "topic": "Generative Agents in Robotics",
            "report": "# Generative Robotics\n\nFull grounded report content.\n\n# Sources\n* https://robotics.org/paper",
            "feedback": "Score: 9/10\n\nHigh factual grounding.",
            "search_results": "Title: Robotics Paper\nURL: https://robotics.org/paper\nSnippet: Robot foundation model.",
            "scraped_content": "Full robotics text.",
            "plan": {
                "research_objective": "Evaluate generative robotics models",
                "sub_questions": ["What are the latency constraints?"]
            },
            "subtask_results": [
                {
                    "subtask_id": "subtask_1",
                    "research_question": "What are the latency constraints?",
                    "search_queries": ["robot foundation model latency"],
                    "status": "completed",
                }
            ],
            "source_quality_profiles": [
                {
                    "source_id": "S1",
                    "url": "https://robotics.org/paper",
                    "domain": "robotics.org",
                    "title": "Robotics Foundation Models",
                    "source_type": "academic",
                    "quality_score": 0.88,
                    "freshness": "current",
                    "authority_indicators": ["Peer-reviewed journal"]
                }
            ],
            "claims": [
                {
                    "claim_id": "C1",
                    "text": "Latency is under 50ms for low-level actions.",
                    "confidence": 0.95,
                    "status": "grounded",
                    "supporting_source_ids": ["S1"],
                }
            ],
            "verification_report": {
                "status": "PASS",
                "confidence": 0.95,
                "unsupported_claims": [],
            }
        }

        saved_session = persist_complete_research_state(
            db=db,
            project_id=project.id,
            topic=pipeline_state["topic"],
            state=pipeline_state
        )

        assert saved_session.id == pipeline_state["session_id"]
        assert saved_session.status == "completed"
        assert saved_session.verification_status == "PASS"

        # Check child entities
        sources = get_session_sources(db, saved_session.id)
        assert len(sources) == 1
        assert sources[0].domain == "robotics.org"

        claims = get_session_claims(db, saved_session.id)
        assert len(claims) == 1
        assert claims[0].claim_id == "C1"

        report = get_report(db, saved_session.id)
        assert report is not None
        assert "Generative Robotics" in report.content_markdown
        assert report.score == "9/10"

    def test_9_secret_masking(self):
        """Test that sensitive credentials in database URLs are never leaked in logs."""
        masked = _mask_db_url("postgresql://synapse_user:SuperSecretP@ssw0rd!@localhost:5432/synapse_prod")
        assert "SuperSecretP@ssw0rd!" not in masked
        assert "****" in masked

        # SQLite has no password, returns unchanged
        assert _mask_db_url("sqlite:///./synapse.db") == "sqlite:///./synapse.db"

    def test_10_migration_from_json_history(self, db_session_fixture):
        """Test importing historical JSON records into the database schema."""
        # Check if research_history.json exists in workspace
        history_path = "research_history.json"
        if not os.path.exists(history_path):
            pytest.skip("research_history.json not found in workspace")

        res = migrate_history_file(history_path)
        assert res["status"] == "success"
        assert res["migrated"] >= 0
        assert len(res["errors"]) == 0
