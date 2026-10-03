# ⚡ SYNAPSE AI — Autonomous Multi-Agent Research System

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19.0-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-6.x-646CFF?style=for-the-badge&logo=vite&logoColor=white)](https://vitejs.dev)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-FF6F00?style=for-the-badge)](https://langchain-ai.github.io/langgraph/)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector_Store-red?style=for-the-badge)](https://www.trychroma.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

An enterprise-grade, autonomous multi-agent AI research intelligence platform. SYNAPSE AI orchestrates a synchronized collective of specialized AI agents to execute deep, empirical research across the live web. It decomposes complex research topics, gathers and verifies real-time web intelligence, semantically indexes evidence chunks, audits factual grounding, and synthesizes publication-grade executive dossiers downloadable in **PDF**, **Microsoft Word (`.docx`)**, and **Markdown (`.md`)**.

---

## 📑 Table of Contents

- [✨ Core Capabilities](#-core-capabilities)
- [🤖 Multi-Agent Architecture](#-multi-agent-architecture)
- [🛡️ Citation Integrity & Verification Loop](#️-citation-integrity--verification-loop)
- [📁 Project Workspaces & Multi-Tenancy](#-project-workspaces--multi-tenancy)
- [📄 Unified Multi-Format Export Suite](#-unified-multi-format-export-suite)
- [🎨 Design System & User Interface](#-design-system--user-interface)
- [🏗️ System Architecture](#️-system-architecture)
- [🚀 Quick Start & Installation](#-quick-start--installation)
  - [Backend Setup](#1-backend-setup)
  - [Frontend Setup](#2-frontend-setup)
  - [Environment Variables](#3-environment-variables)
- [🔌 API Reference](#-api-reference)
- [🧪 Automated Test Suite](#-automated-test-suite)
- [🏭 Production Deployment (Docker & Cloud)](#-production-deployment-docker--cloud)
- [📄 License](#-license)

---

## ✨ Core Capabilities

- **Deep Autonomous Research Cycles**: Decomposes open-ended prompts into parallel subtasks with multi-iteration search, extraction, and self-correction loops.
- **Strict Evidence Grounding (Zero Hallucination Guarantee)**: Every single claim statement is cryptographically mapped to direct source vector chunks and canonical live URLs.
- **Enterprise Multi-Format Exporter**: Single-source-of-truth export engine producing publication-grade PDFs with native tables, executive Word (`.docx`) files with live hyperlinks, and Markdown files.
- **Dedicated Strategic Conclusion & Outlook**: Automatically synthesizes actionable executive conclusions with 2026–2030 technology roadmap projections and industry implications.
- **Isolated Multi-Tenant Workspaces**: User accounts, project organizations, and private research sessions with JWT authentication and row-level authorization.
- **Resilient Fault Tolerance**: Multi-tier graceful degradation (Tavily search fallback, Groq Llama-3.3 fallback models, and deterministic grounding synthesis) ensuring 100% operational uptime.
- **Full Observability & Telemetry**: Hierarchical timing breakdown, token consumption tracking, tool invocation logs, and per-cycle report diffs.

---

## 🤖 Multi-Agent Architecture

SYNAPSE AI coordinates six autonomous agents governed by a stateful **LangGraph** execution graph:

| Agent | Core Role & Responsibilities | Technologies |
|---|---|---|
| 🎯 **Planner Agent** | Decomposes high-level research objectives into concurrent subtasks with specialized queries and target domains. | Groq Llama-3.3 / Qwen, LangGraph |
| 🔍 **Search Agent** | High-concurrency live web search engine with deduplication, quality filtering, and domain authority scoring. | DuckDuckGo Search, Tavily API |
| 📖 **Reader Agent** | Deep-scrapes search results, extracts semantic article text, strips HTML boilerplate, and computes content hashes. | BeautifulSoup4, Trafilatura |
| 🧠 **Retrieval Engine** | Splits text into overlapping semantic chunks, generates dense vector embeddings, and performs similarity search. | `all-MiniLM-L6-v2`, ChromaDB |
| ✍️ **Writer Agent** | Synthesizes comprehensive reports: Executive Summary, Key Findings, Thematic Analysis, Comparative Tables, and Strategic Conclusion. | Groq Llama-3.3-70b-versatile |
| 🛡️ **Verification Agent** | Executes an 11-rule audit verifying claims against source excerpts. Triggers autonomous re-research loops if evidence is insufficient. | Cross-Encoder NLI, Rule Auditor |
| ⭐ **Critic Agent** | Evaluates final synthesis on factual rigor, structural balance, and clarity, providing an objective quality scorecard. | Groq Llama-3.3 Critic Prompt |

---

## 🛡️ Citation Integrity & Verification Loop

SYNAPSE AI enforces verifiable research provenance through its automated Grounding Engine:

1. **Vector Evidence Attribution**: Content retrieved by the Reader Agent is segmented and assigned unique chunk IDs (`sess_xxx_src_yyy_chunk_zzz`).
2. **Claim-to-Source Mapping**: Every factual assertion generated by the Writer Agent must cite supporting evidence chunk IDs and source IDs.
3. **Auditor Verdict Badging**:
   - `[Grounded] ✅`: Claim is directly supported by retrieved text excerpts (confidence $\ge 85\%$).
   - `[Insufficient] ⚠️`: Partial evidence discovered; flagged for supplemental review.
   - `[Unsupported] ❌`: No supporting evidence identified; pruned or explicitly badged in audit matrix.
4. **Autonomous Re-Research**: If unsupported claims are detected, the system autonomously drafts targeted search queries, re-executes search and retrieval, and re-audits the report.

---

## 📁 Project Workspaces & Multi-Tenancy

Organize research sessions into structured, collaborative workspaces:

- **Isolated User Accounts**: Secure password hashing with `bcrypt` and signed JWT access tokens.
- **Projects & Sessions**: Group research topics under client or domain folders with real-time session counts and timestamps.
- **Multi-Cycle Version History**: Switch between intermediate audit drafts and final verified reports.
- **Comprehensive Research Dossiers**: Export full research archives bundling executive summaries, research strategy plans, vector evidence citations, and source quality ratings into a single consolidated package.

---

## 📄 Unified Multi-Format Export Suite

Exports are powered by a centralized **Single-Source-of-Truth** model ([`StructuredReport`](backend/report_export.py)) that guarantees zero LLM drift or re-synthesis during download:

```
                          ┌────────────────────────┐
                          │    StructuredReport    │
                          │ (Canonical Data Model) │
                          └───────────┬────────────┘
               ┌──────────────────────┼──────────────────────┐
               ▼                      ▼                      ▼
      ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
      │  PDF Exporter   │    │  DOCX Exporter  │    │Markdown Exporter│
      │  (fpdf2 Engine) │    │  (python-docx)  │    │  (Clean GitHub) │
      └─────────────────┘    └─────────────────┘    └─────────────────┘
```

- **Publication-Grade PDF (`.pdf`)**:
  - Deep Electric Cobalt (`#1E40AF`) styling with Slate (`#0F172A`) typography.
  - Native graphical tables for claims and source catalogs with alternating row fills.
  - Running headers, page counters (`Page X of Y`), and clickable external hyperlinks.
  - Universal Latin-1 Unicode sanitization preventing encoding exceptions.
- **Enterprise Microsoft Word (`.docx`)**:
  - Proper heading hierarchy, 1-inch margins, and styled callout blocks.
  - Clickable document-level `w:hyperlink` XML runs.
  - Dynamic Word footer fields (`PAGE` of `NUMPAGES`).
- **Research Markdown (`.md`)**:
  - Standard GitHub Flavored Markdown with clean tables and inline references.

---

## 🎨 Design System & User Interface

- **Curated Executive Palette**:
  - **Electric Cobalt** (`#2563EB` / `#1E40AF`): Authoritative primary actions and badge accents.
  - **Polar Seafoam** (`#0D9488`): Verification audit badges and grounded status indicators.
  - **Slate & Deep Charcoal** (`#0F172A` / `#1E293B`): Crisp high-readability typography.
- **Dual-Theme Engine**: Seamless one-click toggle between **Sleek Dark Mode** and **Crisp Light Mode** with persistent theme preferences.
- **Ambient Visual Effects**: Subtle radial glows and coordinate grid overlays for an immersive, modern workspace experience.
- **Dynamic Trending Chips**: One-click quick-launch topics covering quantum computing, AI clinical diagnostics, solid-state batteries, and next-gen superconductors.

---

## 🏗️ System Architecture

```
                               ┌─────────────────────────────────┐
                               │       SYNAPSE Web Frontend      │
                               │  (React 19 + Vite + Modern CSS) │
                               └────────────────┬────────────────┘
                                                │ REST API / SSE Streams
                                                ▼
                               ┌─────────────────────────────────┐
                               │         FastAPI Backend         │
                               │   Auth, Workspace, Export APIs  │
                               └────────────────┬────────────────┘
                                                │
                     ┌──────────────────────────┼──────────────────────────┐
                     ▼                          ▼                          ▼
          ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
          │   LangGraph Engine  │    │   PostgreSQL / DB   │    │   ChromaDB Engine   │
          │  Multi-Agent Cycle  │    │  Projects, Sessions │    │  Dense Vector Store │
          └──────────┬──────────┘    └─────────────────────┘    └─────────────────────┘
                     │
       ┌─────────────┴─────────────┐
       ▼                           ▼
┌──────────────┐            ┌──────────────┐
│  Groq LLMs   │            │ Live Search  │
│ (Llama 3.3)  │            │ (DDG/Tavily) │
└──────────────┘            └──────────────┘
```

---

## 📂 Project Structure

SYNAPSE AI adopts a clean, modular directory structure cleanly separating backend services, frontend assets, database migrations, and automated test suites:

```text
├── backend/                        # Modular Python Backend Package
│   ├── db/                         # Database models, connection pool, migrations
│   │   ├── models.py               # SQLAlchemy ORM models (Users, Projects, Sessions, Reports)
│   │   ├── session.py              # PostgreSQL/SQLite engine & connection pooling
│   │   ├── service.py              # Multi-tenant workspace data access layer
│   │   └── migration_util.py       # JSON-to-database migration synchronization
│   ├── evaluation/                 # Autonomous evaluation & benchmark suite
│   │   ├── runner.py               # Benchmark runner against gold datasets
│   │   ├── metrics.py              # RAG, factual precision, & citation metrics
│   │   ├── dataset.py              # Research evaluation dataset schemas
│   │   └── config.py               # Thresholds & target benchmarks
│   ├── agents.py                   # Specialized agent prompts & graph nodes
│   ├── app.py                      # FastAPI application with routes, SSE, & middleware
│   ├── auth.py                     # JWT token generation, verification, & password hashing
│   ├── citations.py                # 11-point citation integrity & vector lineage engine
│   ├── evaluate.py                 # CLI entrypoint for evaluation benchmarks
│   ├── migrate.py                  # Production migration runner (Alembic + JSON sync)
│   ├── pipeline.py                 # LangGraph multi-agent cyclical workflow graph
│   ├── planner.py                  # Subtask decomposition & dynamic planning
│   ├── report_export.py            # Canonical StructuredReport & PDF/DOCX/MD builders
│   ├── resilience.py               # Circuit breaker, exponential backoff, rate limiters
│   ├── retrieval.py                # ChromaDB vector embedding & cosine retrieval
│   ├── source_quality.py           # Source credibility, freshness & domain scoring
│   ├── state.py                    # LangGraph typed state schema
│   ├── structured_logger.py        # Request-scoped JSON structured logging subsystem
│   ├── subtask.py                  # Dynamic subtask execution engine
│   ├── telemetry.py                # Prometheus-compatible latency & token metrics
│   ├── tools.py                    # Live search tools (DuckDuckGo, Tavily)
│   └── verification.py             # Claim extraction & factual grounding verification
├── frontend/                       # Modern React 19 Frontend
│   ├── src/                        # React components, state, hooks, & views
│   │   ├── components/             # Reusable UI widgets (AgentCards, Workspace, etc.)
│   │   ├── App.jsx                 # Main application dashboard
│   │   ├── index.css               # Design system tokens, light/dark themes
│   │   └── api.js                  # Axios client for backend API communication
│   ├── package.json                # Frontend dependencies
│   └── vite.config.js              # Vite bundler configuration & dev server proxy
├── tests/                          # Comprehensive Automated Test Suites
│   ├── conftest.py                 # Pytest path configuration & test fixtures
│   ├── test_auth_workspace.py      # Multi-tenant auth, workspace isolation tests
│   ├── test_citations.py           # Citation attribution & chunk lineage tests
│   ├── test_evaluation.py          # Grounding, latency, & evaluation pipeline tests
│   ├── test_fault_tolerance.py     # Fallback reasoning & circuit breaker tests
│   ├── test_observability_telemetry.py # Structured logging & Prometheus metrics tests
│   ├── test_production_readiness.py# Healthcheck, CORS, middleware, & deployment tests
│   ├── test_report_export.py       # PDF, DOCX, & Markdown export validation
│   ├── test_retrieval.py           # Vector embedding, indexing, & retrieval tests
│   ├── test_source_quality.py      # Freshness penalty & domain trust scoring tests
│   ├── test_verification.py        # Claim verification & hallucination guardrail tests
│   └── test_workspace_db.py        # Database operations & historical JSON migration tests
├── alembic/                        # Alembic database migration revisions
├── alembic.ini                     # Alembic configuration
├── app.py                          # Root entrypoint proxy (uvicorn app:app)
├── migrate.py                      # Root migration runner proxy (python migrate.py)
├── Dockerfile                      # Multi-stage production container build
├── docker-compose.yml              # Production container stack with PostgreSQL
├── Procfile                        # Heroku/Render process configuration
├── render.yaml                     # Render Infrastructure-as-Code Blueprint
├── requirements.txt                # Python backend dependencies
└── pytest.ini                      # Pytest runner configuration
```

---

## 🚀 Quick Start & Installation

### Prerequisites

- **Python 3.12+**
- **Node.js 18+ & npm**
- **Groq API Key** ([Get free API key](https://console.groq.com))
- *(Optional)* PostgreSQL 16 (SQLite used automatically as local fallback)

---

### 1. Backend Setup

```bash
# 1. Clone repository
git clone https://github.com/Sayalij1609/Synapse_AI.git
cd "Multi Agent AI Research System"

# 2. Create and activate virtual environment
python -m venv .venv

# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env and set your GROQ_API_KEY

# 5. Initialize database
python migrate.py

# 6. Start the FastAPI server
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

---

### 2. Frontend Setup

In a separate terminal:

```bash
cd frontend

# 1. Install dependencies
npm install

# 2. Start Vite development server
npm run dev
```

Open your browser at **`http://localhost:5173`**.

---

### 3. Environment Variables

Create a `.env` file in the root directory:

```ini
# ── LLM Engine (Required) ──
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_PLANNER_MODEL=llama-3.3-70b-versatile
GROQ_WRITER_MODEL=llama-3.3-70b-versatile
GROQ_CRITIC_MODEL=llama-3.3-70b-versatile

# ── Optional Secondary Search Provider ──
TAVILY_API_KEY=tvly-your_tavily_key_optional

# ── Database Configuration ──
# Omit DATABASE_URL to automatically use local SQLite (sqlite:///./synapse.db)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/synapse_db
AUTO_MIGRATE=true

# ── Security & Authentication ──
JWT_SECRET_KEY=generate_a_secure_random_32_character_secret_key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# ── Server & CORS ──
PORT=8000
ENVIRONMENT=development
ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

---

## 🔌 API Reference

### Research & Intelligence Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/run?topic=...&token=...` | **SSE Stream**: Real-time research agent execution pipeline. |
| `POST` | `/download-pdf` | Generates publication-grade PDF report from structured data. |
| `POST` | `/download-docx` | Generates enterprise Word (`.docx`) document with hyperlinks. |
| `POST` | `/download-markdown` | Exports cleaned, formatted Markdown document. |
| `POST` | `/export/structured-report` | Exports canonical `StructuredReport` JSON payload. |

### Workspace & Projects Endpoints (Authenticated)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/register` | Register a new user account. |
| `POST` | `/auth/login` | Authenticate and obtain JWT access token. |
| `GET` | `/auth/me` | Fetch authenticated user profile. |
| `GET` | `/projects` | List all research projects owned by the user. |
| `POST` | `/projects` | Create a new research project folder. |
| `GET` | `/projects/{id}/sessions` | List all research sessions inside a project. |
| `POST` | `/projects/{id}/sessions` | Create a research session attached to a project. |
| `GET` | `/sessions/{id}` | Retrieve research session details, report, and claims. |
| `GET` | `/sessions/{id}/dossier` | Export comprehensive research dossier for a session. |
| `GET` | `/sessions/{id}/telemetry` | Retrieve hierarchical agent execution telemetry tree. |

### Health & Monitoring Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Lightweight service liveness check (`{"status": "ok"}`). |
| `GET` | `/ready` | Deep readiness probe verifying database connectivity & LLM client. |

---

## 🧪 Automated Test Suite

SYNAPSE AI features comprehensive test coverage verifying multi-tenant authorization, citation integrity, fault tolerance, and report exports:

```bash
# Run all test suites
pytest

# Run specific functional suites
pytest tests/test_report_export.py       # Canonical StructuredReport & multi-format exports
pytest tests/test_citations.py           # 11-point citation integrity & vector chunk lineage
pytest tests/test_auth_workspace.py      # Multi-tenant isolation & ownership enforcement
pytest tests/test_fault_tolerance.py     # Deterministic grounding & graceful degradation
```

---

## 🏭 Production Deployment (Docker & Cloud)

### 1. Docker Compose (Full Stack)

The included `docker-compose.yml` provisions a production-hardened environment with non-root security:

```bash
# Build and run FastAPI + PostgreSQL 16
docker compose up -d --build

# Inspect logs
docker compose logs -f
```

### 2. Render Cloud Blueprint

Deploy directly with Render using the provided [`render.yaml`](render.yaml):

1. Connect your GitHub repository to Render.
2. Select **New > Blueprint** and link the repository.
3. Configure your `GROQ_API_KEY` under environment settings.
4. Render automatically spins up the managed PostgreSQL instance, runs `python migrate.py`, and launches the containerized web service.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
