"""
SYNAPSE AI — History to PostgreSQL / Relational Database Migration Utility.

Safely migrates all existing records from research_history.json into the
new persistent workspace schema (User -> ResearchProject -> ResearchSession).
Does NOT delete or modify research_history.json.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from db.models import (
    ResearchProject,
    ResearchSession,
    User,
    generate_uuid,
    utc_now,
)
from db.service import (
    create_project,
    create_session,
    get_or_create_default_user,
    get_session,
    persist_complete_research_state,
    record_agent_run,
    save_report,
    save_sources,
)
from db.session import db_session, init_db

logger = logging.getLogger("synapse.db.migration")


def parse_iso_datetime(dt_str: Optional[str]) -> datetime:
    """Parse ISO string into datetime or return current UTC."""
    if not dt_str:
        return utc_now()
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return utc_now()


def migrate_history_file(
    json_path: str = "research_history.json",
    default_email: str = "admin@synapse.ai",
    project_title: str = "Imported Research Archive"
) -> Dict[str, Any]:
    """
    Migrate existing research_history.json into the database.
    Idempotent: skips entries whose session IDs already exist.
    """
    if not os.path.exists(json_path):
        logger.warning("History file not found at: %s", json_path)
        return {"status": "file_not_found", "migrated": 0, "skipped": 0, "errors": []}

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            history_data = json.load(f)
    except Exception as e:
        logger.error("Failed to read JSON history file: %s", str(e))
        return {"status": "read_error", "error": str(e), "migrated": 0}

    if not isinstance(history_data, list):
        return {"status": "invalid_format", "migrated": 0}

    # Ensure tables exist
    init_db()

    migrated_count = 0
    skipped_count = 0
    errors = []

    with db_session() as db:
        # 1. Ensure Default User
        user = get_or_create_default_user(db, email=default_email, username="admin")

        # 2. Ensure Migration Project
        project = None
        for p in user.projects:
            if p.title == project_title:
                project = p
                break
        if not project:
            project = create_project(
                db,
                user_id=user.id,
                title=project_title,
                description="Imported from historical JSON research archive."
            )

        # 3. Iterate through history records
        for item in history_data:
            session_id = item.get("id")
            topic = item.get("topic", "Historical Research")

            if not session_id:
                session_id = generate_uuid()

            # Check if session already exists
            existing = get_session(db, session_id)
            if existing:
                skipped_count += 1
                continue

            try:
                # Convert history entry into state dict
                state_dict = {
                    "session_id": session_id,
                    "topic": topic,
                    "report": item.get("report", ""),
                    "feedback": item.get("feedback", ""),
                    "search_results": item.get("search_results", ""),
                    "scraped_content": item.get("scraped_content", ""),
                    "evidence_briefing": item.get("evidence_briefing", ""),
                    "retrieved_evidence": item.get("retrieved_evidence", []),
                    "plan": item.get("plan", {}),
                    "subtask_results": item.get("subtask_results", []),
                    "evidence_summary": item.get("evidence_summary", {}),
                    "claims": item.get("claims", []),
                    "sources": item.get("sources", {}),
                    "source_quality_profiles": item.get("source_quality_profiles", []),
                    "citation_trace": item.get("citation_trace", {}),
                    "verification_report": item.get("verification_report", {}),
                }

                # Persist complete research state
                created_session = persist_complete_research_state(
                    db=db,
                    project_id=project.id,
                    topic=topic,
                    state=state_dict
                )

                # Fix timestamps to match original historic record
                if item.get("timestamp"):
                    orig_dt = parse_iso_datetime(item["timestamp"])
                    created_session.created_at = orig_dt
                    created_session.updated_at = orig_dt
                    for rep in created_session.reports:
                        rep.created_at = orig_dt
                    for src in created_session.sources:
                        src.created_at = orig_dt

                db.commit()
                migrated_count += 1
            except Exception as e:
                db.rollback()
                err_msg = f"Failed to migrate session {session_id} ('{topic}'): {str(e)}"
                logger.error(err_msg)
                errors.append(err_msg)

    logger.info(
        "History migration complete: %d migrated, %d skipped, %d errors",
        migrated_count, skipped_count, len(errors)
    )

    return {
        "status": "success",
        "migrated": migrated_count,
        "skipped": skipped_count,
        "errors": errors
    }
