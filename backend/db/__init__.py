"""
SYNAPSE AI — Persistent Research Workspace Database Package.
Provides SQLAlchemy ORM models, session management, and workspace services.
"""

from db.models import (
    Base,
    User,
    ResearchProject,
    ResearchSession,
    ResearchQuery,
    ResearchSubtask,
    Source,
    EvidenceChunk,
    Claim,
    ClaimEvidenceLink,
    AgentRun,
    Report,
)
from db.session import (
    get_db,
    db_session,
    init_db,
    engine,
    SessionLocal,
    get_database_url,
)

__all__ = [
    "Base",
    "User",
    "ResearchProject",
    "ResearchSession",
    "ResearchQuery",
    "ResearchSubtask",
    "Source",
    "EvidenceChunk",
    "Claim",
    "ClaimEvidenceLink",
    "AgentRun",
    "Report",
    "get_db",
    "db_session",
    "init_db",
    "engine",
    "SessionLocal",
    "get_database_url",
]
