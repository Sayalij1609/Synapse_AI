import json
import uuid
import os
import io
import re
import sys
import time
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select, desc, text

from db.session import get_db
from db.models import User, ResearchProject, ResearchSession, Report

from fpdf import FPDF
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from report_export import (
    StructuredReport,
    build_structured_report,
    export_to_markdown,
    export_to_docx,
    export_to_pdf,
)
from structured_logger import setup_structured_logging, get_logger, request_id_ctx

# Initialize structured logging subsystem
setup_structured_logging()
logger = get_logger("synapse.app")

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "research_history.json")
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "frontend", "dist")


# ── App setup & Lifespan ─────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Production lifespan management:
    - Startup: Runs safe migrations, establishes connection pools, checks environment
    - Shutdown: Gracefully closes DB connections, drains in-flight tasks
    """
    env_name = os.getenv("ENVIRONMENT", "development").lower()
    logger.info("SYNAPSE AI initiating startup sequence [environment=%s, python=%s]", env_name, sys.version.split()[0])

    try:
        from db.session import init_db
        from db.migration_util import migrate_history_file

        auto_migrate = os.getenv("AUTO_MIGRATE", "true").lower() in ("true", "1", "yes")
        if auto_migrate:
            init_db()
            migrate_history_file(HISTORY_FILE)
            logger.info("Database schema and historical archive verified successfully.")

        # Pre-warm transformer models, neural weights, and vector store on backend startup
        try:
            logger.info("Pre-warming transformer embedding models, neural weights, and vector store...")
            from retrieval import warmup_retrieval_models
            from planner import warmup_planner
            warmup_retrieval_models()
            warmup_planner()
            logger.info("All transformer models, neural weights, and agent clients preloaded successfully.")
        except Exception as warmup_err:
            logger.warning("Model warmup notice: %s", str(warmup_err))
    except Exception as e:
        logger.error("Database startup warning: %s", str(e), exc_info=True)

    yield

    # Graceful Shutdown
    logger.info("SYNAPSE AI initiating graceful shutdown...")
    try:
        from db.session import engine
        engine.dispose()
        logger.info("Database connection pool cleanly disposed.")
    except Exception as e:
        logger.warning("Error disposing database connection pool: %s", str(e))
    logger.info("SYNAPSE AI shutdown sequence completed.")


app = FastAPI(
    title="SYNAPSE AI",
    description="Autonomous Multi-Agent AI Research System",
    version="1.0.0",
    lifespan=lifespan,
)


# ── CORS Configuration ───────────────────────────────────────
# Configured via ALLOWED_ORIGINS environment variable for production environments
allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "").strip()
if allowed_origins_raw:
    if allowed_origins_raw == "*":
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        allowed_origins = [o.strip() for o in allowed_origins_raw.split(",") if o.strip()]
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
else:
    # Default permissive local development origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# ── Middleware: Request Logging & Timeouts ───────────────────

@app.middleware("http")
async def request_logging_and_timeout_middleware(request: Request, call_next):
    """
    Tracks request latency, attaches distributed request IDs,
    enforces request timeouts, and emits structured logs.
    """
    start_time = time.time()
    req_id = request.headers.get("x-request-id") or str(uuid.uuid4())[:8]
    token = request_id_ctx.set(req_id)

    # Resolve request timeout: long tasks (streaming SSE /run) get extended timeout
    is_streaming = request.url.path.startswith("/run")
    default_timeout = 600.0 if is_streaming else float(os.getenv("REQUEST_TIMEOUT_SECONDS", "120"))

    try:
        response = await asyncio.wait_for(call_next(request), timeout=default_timeout)
        duration_ms = round((time.time() - start_time) * 1000, 2)
        response.headers["x-request-id"] = req_id

        # Skip spamming logs on healthy health/ready polling unless an error occurs
        if request.url.path not in ["/health", "/ready"] or response.status_code >= 400:
            logger.info(
                "HTTP %s %s -> %s (%sms)",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
                extra={"extra_fields": {"duration_ms": duration_ms, "status_code": response.status_code}}
            )
        return response

    except asyncio.TimeoutError:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(
            "HTTP %s %s TIMED OUT after %ss (%sms)",
            request.method,
            request.url.path,
            default_timeout,
            duration_ms,
        )
        return JSONResponse(
            status_code=504,
            content={
                "error": "Gateway Timeout",
                "message": f"Request processing timed out after {default_timeout} seconds.",
                "request_id": req_id,
            }
        )
    except Exception as exc:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(
            "HTTP %s %s UNHANDLED ERROR: %s (%sms)",
            request.method,
            request.url.path,
            str(exc),
            duration_ms,
            exc_info=True,
        )
        raise
    finally:
        request_id_ctx.reset(token)


# ── Static SPA Delivery & Health / Readiness Endpoints ───────

if os.path.exists(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/")
    async def serve_spa():
        return HTMLResponse(open(os.path.join(FRONTEND_DIST, "index.html"), encoding="utf-8").read())
else:
    @app.get("/")
    async def root_status():
        return {
            "status": "online",
            "service": "SYNAPSE AI Research Backend API",
            "version": "1.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@app.get("/health")
async def health_check():
    """
    Liveness probe.
    Confirms HTTP worker process is alive and responsive.
    Lightweight: suitable for frequent container runtime probes.
    """
    return {
        "status": "healthy",
        "service": "synapse-ai",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
    }


@app.get("/ready")
async def readiness_check(db: Session = Depends(get_db)):
    """
    Readiness probe.
    Deep dependency verification before accepting production traffic:
    1. Database connectivity (executes SELECT 1)
    2. Model provider configuration (verifies GROQ_API_KEY presence)
    3. Storage availability
    Returns 200 OK when ready; 503 Service Unavailable when dependency is down.
    """
    checks = {}
    is_ready = True

    # 1. Database Connection Check
    try:
        db.execute(text("SELECT 1"))
        dialect = db.bind.dialect.name if db.bind else "sqlite"
        checks["database"] = {
            "status": "connected",
            "dialect": dialect,
        }
    except Exception as db_err:
        is_ready = False
        checks["database"] = {
            "status": "disconnected",
            "error": str(db_err),
        }

    # 2. LLM Provider Check
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if groq_key:
        checks["llm_provider"] = {
            "status": "configured",
            "provider": "Groq",
        }
    else:
        checks["llm_provider"] = {
            "status": "warning",
            "message": "GROQ_API_KEY is not set; running in local/fallback mode.",
        }

    # 3. Environment & Storage Check
    checks["environment"] = {
        "mode": os.getenv("ENVIRONMENT", "development"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    status_code = 200 if is_ready else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if is_ready else "not_ready",
            "checks": checks,
        }
    )


# ── Pydantic models ─────────────────────────────────────────

class ExportRequest(BaseModel):
    report: Optional[str] = None
    topic: str = "Research Report"
    session_id: Optional[str] = None
    structured_data: Optional[Dict[str, Any]] = None
    claims: Optional[Any] = None
    sources: Optional[Any] = None


class PDFRequest(ExportRequest):
    pass


class DocxRequest(ExportRequest):
    pass


class MarkdownRequest(ExportRequest):
    pass


class ProjectCreateRequest(BaseModel):
    title: str
    description: str = ""


class SessionCreateRequest(BaseModel):
    topic: str
    session_name: str = ""


class RegisterRequest(BaseModel):
    email: str
    password: str
    username: Optional[str] = None
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


# ── History & Persistence helpers ────────────────────────────

def load_history():
    """Load research history from JSON file."""
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_history(history):
    """Save research history to JSON file."""
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def add_to_history(topic, state, user_id=None):
    """
    Append a completed research to history and persist to the relational database.
    Associates the session with user_id if provided.
    Retains legacy JSON file for dual-write compatibility.
    """
    session_id = state.get("session_id") or str(uuid.uuid4())

    # 1. Persist to relational database
    try:
        from db.session import db_session
        from db.service import get_or_create_default_user, create_project, persist_complete_research_state
        from db.models import User
        from sqlalchemy import select
        with db_session() as db:
            user = None
            if user_id:
                user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
            if not user:
                user = get_or_create_default_user(db)

            project = user.projects[0] if user.projects else create_project(db, user.id, "Personal Research Workspace")

            state_dict = dict(state)
            state_dict["session_id"] = session_id
            db_session_obj = persist_complete_research_state(db, project.id, topic, state_dict)
            session_id = db_session_obj.id
    except Exception as e:
        print(f"[SYNAPSE DB Persistence Error] {e}")

    # 2. Dual-write to legacy JSON file
    history = load_history()
    entry = {
        "id": session_id,
        "topic": topic,
        "session_id": session_id,
        "timestamp": datetime.now().isoformat(),
        "report": state.get("report", ""),
        "feedback": state.get("feedback", ""),
        "search_results": state.get("search_results", ""),
        "scraped_content": state.get("scraped_content", ""),
        "evidence_briefing": state.get("evidence_briefing", ""),
        "retrieved_evidence": state.get("retrieved_evidence", []),
        "plan": state.get("plan", {}),
        "plan_markdown": state.get("plan_markdown", ""),
        "subtasks": state.get("subtasks", []),
        "subtask_results": state.get("subtask_results", []),
        "evidence_summary": state.get("evidence_summary", {}),
        "claims": state.get("claims", []),
        "sources": state.get("sources", {}),
        "grounded_claims": state.get("grounded_claims", []),
        "unsupported_claims": state.get("unsupported_claims", []),
        "citation_trace": state.get("citation_trace", {}),
        "source_quality_profiles": state.get("source_quality_profiles", []),
        "source_quality_report": state.get("evidence_summary", {}).get("source_quality", {}),
        "verification_report": state.get("verification_report", {}),
        "failed_sources": state.get("failed_sources", []),
        "degraded_modes": state.get("degraded_modes", []),
        "warnings": state.get("warnings", []),
        "thematic_analysis": state.get("thematic_analysis", []),
        "key_findings": state.get("key_findings", []),
        "research_objectives": state.get("research_objectives", []),
        "research_limitations": state.get("research_limitations", []),
        "telemetry": state.get("telemetry", {}),
        "agent_runs": state.get("agent_runs", []),
        "report_history": state.get("report_history", []),
    }
    history.insert(0, entry)
    save_history(history)
    return session_id

# ── Unified Structured Report Resolution & Adapters ──────────────

def _resolve_structured_report(data: ExportRequest, db: Optional[Session] = None) -> StructuredReport:
    """
    Construct the canonical StructuredReport object from request payload or database.
    Order of precedence:
    1. data.structured_data (provided directly by caller)
    2. Database session lookup by data.session_id (or JSON history fallback)
    3. Composite payload combining data.report, data.claims, and data.sources
    4. Plain markdown parsing from data.report
    """
    if data.structured_data:
        return build_structured_report(data.structured_data, topic=data.topic)

    if data.session_id:
        if db:
            try:
                db_session = db.query(ResearchSession).filter(ResearchSession.id == data.session_id).first()
                if db_session:
                    return build_structured_report(db_session, topic=data.topic)
            except Exception as e:
                print(f"[Export] DB session lookup warning: {e}")

        try:
            history = load_history()
            for entry in history:
                if entry.get("id") == data.session_id or entry.get("session_id") == data.session_id:
                    return build_structured_report(entry, topic=data.topic)
        except Exception as e:
            print(f"[Export] History entry lookup warning: {e}")

    raw_claims = data.claims
    if isinstance(raw_claims, dict):
        raw_claims = raw_claims.get("claims") or raw_claims.get("items") or []
    elif not isinstance(raw_claims, list):
        raw_claims = []

    raw_sources = data.sources
    if isinstance(raw_sources, dict):
        raw_sources = raw_sources.get("sources") or raw_sources.get("items") or []
    elif not isinstance(raw_sources, list):
        raw_sources = []

    if raw_claims or raw_sources:
        payload = {
            "topic": data.topic,
            "report": data.report or "",
            "claims": raw_claims,
            "sources": raw_sources,
            "grounded_claims": [c for c in raw_claims if isinstance(c, dict) and c.get("status") == "grounded"],
            "unsupported_claims": [c for c in raw_claims if isinstance(c, dict) and c.get("status") == "unsupported"],
        }
        return build_structured_report(payload, topic=data.topic)

    return build_structured_report(data.report or "", topic=data.topic)


def markdown_to_pdf(report_input: Any, topic: str = "Research Report") -> bytes:
    """Export canonical StructuredReport to professional PDF format."""
    structured = build_structured_report(report_input, topic=topic)
    return export_to_pdf(structured)


def markdown_to_docx(report_input: Any, topic: str = "Research Report") -> bytes:
    """Export canonical StructuredReport to enterprise Word (.docx) format."""
    structured = build_structured_report(report_input, topic=topic)
    return export_to_docx(structured)


def markdown_to_markdown(report_input: Any, topic: str = "Research Report") -> str:
    """Export canonical StructuredReport to clean Markdown format."""
    structured = build_structured_report(report_input, topic=topic)
    return export_to_markdown(structured)


# ── Routes ───────────────────────────────────────────────────

@app.get("/run")
async def run_pipeline(topic: str = "", token: str = "", request: Request = None):
    """SSE endpoint — streams pipeline step events as JSON, attributed to authenticated user."""
    topic = topic.strip()

    if not topic:
        return JSONResponse({"error": "No topic provided"})

    # Extract user_id from query token or Authorization header
    auth_token = token.strip()
    if not auth_token and request:
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            auth_token = auth_header[7:].strip()

    user_id = None
    if auth_token:
        try:
            from auth import decode_access_token
            payload = decode_access_token(auth_token)
            user_id = payload.get("sub")
        except Exception:
            pass

    def generate():
        try:
            from pipeline import run_research_pipeline_stream
            for event in run_research_pipeline_stream(topic):
                if event.get("step") == "complete" and "state" in event:
                    try:
                        entry_id = add_to_history(topic, event["state"], user_id=user_id)
                        event["history_id"] = entry_id
                    except Exception as hist_err:
                        print(f"[Warning: History persistence failed] {hist_err}")
                        event["history_id"] = event.get("state", {}).get("session_id", "session_unpersisted")

                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            user_msg = f"Research session encountered an unexpected failure: {str(e)}"
            yield f'data: {json.dumps({"step": "error", "error": str(e), "message": user_msg})}\n\n'

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


# ── Export Endpoints ───────────────────────────────────────────

@app.post("/download-pdf")
async def download_pdf(data: PDFRequest, db: Session = Depends(get_db)):
    """Generate and return a PDF from the unified StructuredReport."""
    if not data.report and not data.session_id and not data.structured_data:
        return JSONResponse({"error": "No report or session_id provided"}, status_code=400)

    structured_report = _resolve_structured_report(data, db=db)
    pdf_bytes = export_to_pdf(structured_report)
    buffer = io.BytesIO(pdf_bytes)
    buffer.seek(0)

    safe_name = re.sub(r'[^\w\s-]', '', structured_report.title or data.topic)[:50].strip().replace(' ', '_')
    filename = f"synapse_{safe_name}.pdf"

    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.post("/download-docx")
async def download_docx(data: DocxRequest, db: Session = Depends(get_db)):
    """Generate and return a Word (.docx) file from the unified StructuredReport."""
    if not data.report and not data.session_id and not data.structured_data:
        return JSONResponse({"error": "No report or session_id provided"}, status_code=400)

    structured_report = _resolve_structured_report(data, db=db)
    docx_bytes = export_to_docx(structured_report)
    buffer = io.BytesIO(docx_bytes)
    buffer.seek(0)

    safe_name = re.sub(r'[^\w\s-]', '', structured_report.title or data.topic)[:50].strip().replace(' ', '_')
    filename = f"synapse_{safe_name}.docx"

    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.post("/download-markdown")
async def download_markdown(data: MarkdownRequest, db: Session = Depends(get_db)):
    """Generate and return a clean Markdown document from the unified StructuredReport."""
    if not data.report and not data.session_id and not data.structured_data:
        return JSONResponse({"error": "No report or session_id provided"}, status_code=400)

    structured_report = _resolve_structured_report(data, db=db)
    md_text = export_to_markdown(structured_report)

    safe_name = re.sub(r'[^\w\s-]', '', structured_report.title or data.topic)[:50].strip().replace(' ', '_')
    filename = f"synapse_{safe_name}.md"

    return Response(
        content=md_text.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.post("/export/structured-report")
async def export_structured_report_api(data: ExportRequest, db: Session = Depends(get_db)):
    """Return the canonical StructuredReport JSON schema."""
    structured_report = _resolve_structured_report(data, db=db)
    return structured_report.model_dump()


@app.get("/sessions/{session_id}/structured-report")
async def get_session_structured_report(session_id: str, db: Session = Depends(get_db)):
    """Retrieve canonical StructuredReport JSON for a research session."""
    req = ExportRequest(session_id=session_id)
    structured_report = _resolve_structured_report(req, db=db)
    return structured_report.model_dump()


# ── Authentication API ───────────────────────────────────────

@app.post("/auth/register")
async def handle_register(req: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user account with hashed password validation."""
    from auth import register_user, create_access_token
    user = register_user(
        db=db,
        email=req.email,
        password=req.password,
        username=req.username,
        full_name=req.full_name,
    )
    token = create_access_token(user_id=user.id, email=user.email)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user.to_dict(),
    }


@app.post("/auth/login")
async def handle_login(req: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user with email and password, returning JWT access token."""
    from auth import authenticate_user, create_access_token
    user = authenticate_user(db=db, email=req.email, password=req.password)
    token = create_access_token(user_id=user.id, email=user.email)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user.to_dict(),
    }


# ── Protected Authentication Profile ─────────────────────────

from auth import (
    get_current_user,
    get_optional_current_user,
    verify_project_ownership,
    verify_session_ownership,
)


@app.get("/auth/me")
async def get_my_profile(current_user: User = Depends(get_current_user)):
    """Return profile for the currently logged in user."""
    return {"user": current_user.to_dict()}


@app.post("/auth/logout")
async def handle_logout():
    """Client-side token invalidation confirmation."""
    return {"ok": True, "message": "Logged out successfully."}


# ── Persistent Research Workspace & History API ──────────────

@app.get("/history")
async def get_history(
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Return list of past research (summary only).
    If authenticated, returns strictly the user's research sessions.
    Falls back gracefully to historical archive if unauthenticated.
    """
    if current_user:
        # User-specific sessions across user's projects
        user_project_ids = [p.id for p in current_user.projects]
        stmt = (
            select(ResearchSession)
            .where(ResearchSession.project_id.in_(user_project_ids))
            .order_by(desc(ResearchSession.created_at))
            .limit(100)
        )
        sessions = list(db.execute(stmt).scalars().all())
        return [
            {
                "id": s.id,
                "topic": s.topic,
                "timestamp": s.created_at.isoformat() if s.created_at else "",
                "status": s.status,
                "verification_status": s.verification_status,
            }
            for s in sessions
        ]

    # Unauthenticated / Legacy Fallback
    try:
        from db.service import list_sessions
        sessions = list_sessions(db, limit=100)
        if sessions:
            return [
                {
                    "id": s.id,
                    "topic": s.topic,
                    "timestamp": s.created_at.isoformat() if s.created_at else "",
                    "status": s.status,
                    "verification_status": s.verification_status,
                }
                for s in sessions
            ]
    except Exception as e:
        print(f"[DB /history error: {e}]")

    history = load_history()
    return [
        {"id": h["id"], "topic": h["topic"], "timestamp": h["timestamp"]}
        for h in history
    ]


@app.get("/history/{entry_id}")
async def get_history_entry(
    entry_id: str,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """Return full details of a specific research entry from DB (with JSON fallback)."""
    try:
        from db.service import (
            get_session,
            get_report,
            get_session_sources,
            get_session_claims,
            get_session_telemetry_tree,
        )
        session = get_session(db, entry_id)
        if session:
            # If user is authenticated and session has a project, enforce ownership
            if current_user and session.project:
                verify_session_ownership(session, current_user)

            report = get_report(db, entry_id)
            sources = get_session_sources(db, entry_id)
            claims = get_session_claims(db, entry_id)
            telemetry_tree = get_session_telemetry_tree(db, entry_id)
            agent_runs = [r.to_dict() for r in (session.agent_runs or [])]
            return {
                "id": session.id,
                "topic": session.topic,
                "session_id": session.id,
                "timestamp": session.created_at.isoformat() if session.created_at else "",
                "status": session.status,
                "verification_status": session.verification_status,
                "report": report.content_markdown if report else "",
                "feedback": report.feedback if report else "",
                "plan": session.plan_data or {},
                "evidence_summary": session.evidence_summary or {},
                "sources": [s.to_dict() for s in sources],
                "source_quality_profiles": [s.to_dict() for s in sources],
                "claims": [c.to_dict() for c in claims],
                "reports": [r.to_dict() for r in (session.reports or [])],
                "telemetry": telemetry_tree,
                "agent_runs": agent_runs,
            }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DB /history/{entry_id} error: {e}]")

    # Fallback to JSON history
    history = load_history()
    for h in history:
        if h["id"] == entry_id:
            return h
    return JSONResponse({"error": "Not found"}, status_code=404)


@app.get("/sessions/{session_id}/telemetry")
async def get_session_telemetry_endpoint(
    session_id: str,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Expose structured agent execution telemetry hierarchy:
    Research Session
     ├── Planner
     ├── Search
     ├── Reader
     ├── Retrieval
     ├── Writer
     └── Verification
    """
    try:
        from db.service import get_session, get_session_telemetry_tree
        session = get_session(db, session_id)
        if session and current_user and session.project:
            verify_session_ownership(session, current_user)
        if session:
            tree = get_session_telemetry_tree(db, session_id)
            return tree
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Telemetry endpoint error: {e}]")

    # In-memory collector fallback
    try:
        from telemetry import get_session_telemetry
        collector = get_session_telemetry(session_id)
        if collector.get_runs():
            return collector.to_tree()
    except Exception:
        pass

    # JSON history fallback
    history = load_history()
    for h in history:
        if h.get("id") == session_id or h.get("session_id") == session_id:
            if h.get("telemetry"):
                return h["telemetry"]

    return JSONResponse({"error": "Telemetry not found for session"}, status_code=404)


@app.get("/history/{entry_id}/telemetry")
async def get_history_telemetry_endpoint(
    entry_id: str,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """Return structured agent telemetry tree for a research history entry."""
    return await get_session_telemetry_endpoint(entry_id, current_user, db)


@app.delete("/history/{entry_id}")
async def delete_history_entry(
    entry_id: str,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """Delete a specific research entry with authorization."""
    try:
        from db.service import get_session, delete_session
        session = get_session(db, entry_id)
        if session and current_user and session.project:
            verify_session_ownership(session, current_user)
        if session:
            delete_session(db, entry_id)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DB delete error: {e}]")

    history = load_history()
    history = [h for h in history if h["id"] != entry_id]
    save_history(history)
    return {"ok": True}


# ── Protected Research Workspace Projects & Sessions API ─────

@app.get("/projects")
async def list_workspace_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all research workspace projects owned by the authenticated user."""
    from db.service import get_projects
    projects = get_projects(db, user_id=current_user.id)
    return [p.to_dict() for p in projects]


@app.post("/projects")
async def create_workspace_project(
    req: ProjectCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new research project workspace owned by the authenticated user."""
    from db.service import create_project
    project = create_project(
        db=db,
        user_id=current_user.id,
        title=req.title,
        description=req.description,
    )
    return project.to_dict()


@app.get("/projects/{project_id}")
async def get_workspace_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve research project workspace with strict backend ownership verification."""
    from db.service import get_project
    project = get_project(db, project_id)
    verify_project_ownership(project, current_user)
    data = project.to_dict()
    data["sessions"] = [s.to_dict() for s in (project.sessions or [])]
    return data


@app.delete("/projects/{project_id}")
async def delete_workspace_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a research project with strict backend ownership verification."""
    from db.service import get_project, delete_project
    project = get_project(db, project_id)
    verify_project_ownership(project, current_user)
    delete_project(db, project_id)
    return {"ok": True, "deleted_project_id": project_id}


@app.get("/projects/{project_id}/sessions")
async def list_project_sessions(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all research sessions within an owned project."""
    from db.service import get_project, list_sessions
    project = get_project(db, project_id)
    verify_project_ownership(project, current_user)
    sessions = list_sessions(db, project_id=project_id)
    return [s.to_dict() for s in sessions]


@app.post("/projects/{project_id}/sessions")
async def create_project_session(
    project_id: str,
    req: SessionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new research session under an owned project."""
    from db.service import get_project, create_session
    project = get_project(db, project_id)
    verify_project_ownership(project, current_user)
    session = create_session(
        db=db,
        project_id=project_id,
        topic=req.topic,
        session_name=req.session_name,
    )
    return session.to_dict()


@app.get("/sessions/{session_id}")
async def get_workspace_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve session details with strict backend ownership verification."""
    from db.service import get_session
    session = get_session(db, session_id)
    verify_session_ownership(session, current_user)
    return session.to_dict(include_details=True)


@app.delete("/sessions/{session_id}")
async def delete_workspace_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a research session with strict backend ownership verification."""
    from db.service import get_session, delete_session
    session = get_session(db, session_id)
    verify_session_ownership(session, current_user)
    delete_session(db, session_id)
    return {"ok": True, "deleted_session_id": session_id}


@app.get("/sessions/{session_id}/reports")
async def get_session_report_versions(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve report versions with strict backend ownership verification."""
    from db.service import get_session, list_reports
    session = get_session(db, session_id)
    verify_session_ownership(session, current_user)
    reports = list_reports(db, session_id)
    return [r.to_dict() for r in reports]


@app.get("/sessions/{session_id}/dossier")
async def get_session_dossier_endpoint(
    session_id: str,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Export comprehensive session dossier:
    - Metadata, research plan, subtasks
    - Executive report and version history
    - Claims with evidence citations
    - Source quality and freshness ratings
    - Agent telemetry tree
    - Consolidated Markdown dossier
    """
    from db.service import get_session, export_session_dossier
    session = get_session(db, session_id)
    if session:
        if current_user and session.project:
            verify_session_ownership(session, current_user)
        dossier = export_session_dossier(db, session_id)
        if dossier:
            return dossier

    # Fallback to history entry if DB not populated
    history = load_history()
    for h in history:
        if h.get("id") == session_id or h.get("session_id") == session_id:
            topic = h.get("topic", "Research Session")
            report = h.get("report", "")
            return {
                "session_id": session_id,
                "topic": topic,
                "status": "completed",
                "verification_status": "verified" if h.get("feedback") else "unverified",
                "created_at": h.get("timestamp"),
                "report": {"content_markdown": report, "feedback": h.get("feedback")},
                "sources": h.get("source_quality_profiles") or h.get("sources") or [],
                "claims": h.get("grounded_claims") or [],
                "telemetry": h.get("telemetry"),
                "dossier_markdown": f"# SYNAPSE AI — Research Dossier\n**Topic**: {topic}\n\n## Report\n\n{report}",
            }

    raise HTTPException(status_code=404, detail="Session dossier not found")


@app.get("/history/{entry_id}/dossier")
async def get_history_dossier_endpoint(
    entry_id: str,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """Export comprehensive research dossier for a historical entry."""
    return await get_session_dossier_endpoint(entry_id, current_user, db)



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
