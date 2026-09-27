# ⚡ SYNAPSE AI — Autonomous Multi-Agent Research System

An enterprise-grade, multi-agent AI research intelligence platform that automates complex web research workflows. Four specialized AI agents collaborate in real-time — **searching** live web intelligence, **extracting & scraping** content, **synthesizing** structured executive reports, and **auditing** quality — producing downloadable **Word (.docx)**, **PDF**, and **Markdown** reports with verified sources.

![React](https://img.shields.io/badge/React-19.0-61DAFB?logo=react&logoColor=black)
![Vite](https://img.shields.io/badge/Vite-6.x-646CFF?logo=vite&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-0.3-1C3C3C?logo=langchain)
![License](https://img.shields.io/badge/License-MIT-green.svg)

---

## ✨ Key Features & Capabilities

- 🤖 **4 Specialized Autonomous AI Agents**:
  - 🔍 **Search Agent**: Queries live web search via DuckDuckGo & extracts source URLs.
  - 📄 **Reader Agent**: Scrapes web content and strips noise for deep analysis.
  - ✍️ **Writer Agent**: Synthesizes executive research reports with structured sections.
  - ⭐ **Critic Agent**: Audits report quality, scores factual completeness (X/10), and details key strengths.
- 📄 **Multi-Format Export Suite**:
  - 📘 **Microsoft Word (`.docx`)**: Custom styled Word documents with proper headings, lists, and formatting (`python-docx`).
  - 📕 **PDF Document (`.pdf`)**: Formatted PDF reports generated dynamically (`fpdf2`).
  - 📝 **Raw Markdown (`.md`)**: Instant download for note-taking tools like Obsidian or Notion.
  - 📋 **1-Click Clipboard Copy**: Instantly copy full synthesized reports.
- 🌐 **Discovered Web News & Resources Container**:
  - Interactive grid displaying domain badges, Google favicons, article snippets, 1-click URL copy, and direct external links.
- 🔬 **Multi-Tab Intelligence Hub**:
  - Structured output tabs: `📝 Executive Report`, `🌐 Web News & Sources`, `⭐ Quality Audit Review`, and `🛠️ Agent Telemetry`.
- 📜 **History Archive Modal**:
  - Integrated search-filterable archive to reload or manage past research sessions anytime.
- 🎨 **Enterprise UI Design**:
  - High-contrast Deep Indigo Plum (`#2B2554`) & Rose Pink (`#EF526E`) palette on a crisp **pure white background** at true **100% resolution scale**.

---

## 🏗️ System Architecture

```
                                  ┌───────────────────────────┐
                                  │      SYNAPSE AI UI        │
                                  │  (React 19 + Vite SPA)    │
                                  └─────────────┬─────────────┘
                                                │ REST API
                                                ▼
                                  ┌───────────────────────────┐
                                  │     FastAPI Backend       │
                                  │       (app.py)            │
                                  └─────────────┬─────────────┘
                                                │
                                                ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   Search Agent   │ ──►│   Reader Agent   │ ──►│   Writer Agent   │ ──►│   Critic Agent   │
│ (Live Web Search)│    │(Scrape & Extract)│    │(Report Synthesis)│    │ (Quality Audit)  │
└──────────────────┘    └──────────────────┘    └──────────────────┘    └──────────────────┘
```

---

## 📁 Project Structure

```
Multi Agent AI Research System/
├── app.py                     # FastAPI backend (Endpoints: /run, /history, /download-pdf, /download-docx)
├── agents.py                  # Agent prompts, chains, & LLM execution engine
├── pipeline.py                # Synchronous & SSE streaming multi-agent execution pipeline
├── tools.py                   # Search & scraping tools (DuckDuckGo, BeautifulSoup)
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Multi-stage Docker build (Node.js + Python)
├── .dockerignore              # Docker build context exclusions
├── Procfile                   # Cloud platform process start command
├── render.yaml                # Render Blueprint for deployment
├── DOCKER.md                  # Full Docker deployment guide
├── README.md                  # Project documentation
└── frontend/                  # React + Vite Single Page Application
    ├── index.html             # HTML entry point
    ├── vite.config.js         # Vite proxy configuration
    ├── package.json           # Frontend dependencies
    └── src/
        ├── App.jsx            # Main React state & view router
        ├── App.css            # Global modern design system & HSL tokens
        ├── api.js             # Frontend API client
        └── components/
            ├── Topbar.jsx         # Executive navbar with high-res brand badge & navigation
            ├── Home.jsx           # Enterprise landing page & quick-launch cards
            ├── Hero.jsx           # Lab search command panel
            ├── Pipeline.jsx       # Connected multi-agent execution track
            ├── Metrics.jsx        # Telemetry metrics bar
            ├── Results.jsx        # Multi-tab intelligence hub & export suite
            ├── NewsResources.jsx  # Web news & resources grid container
            ├── HistoryModal.jsx   # Research history modal popup
            └── Footer.jsx         # Enterprise tech footer
```

---

## 🚀 Getting Started

SYNAPSE AI supports two distinct execution modes:
1. **Local Development Mode**: Fast iteration with local SQLite storage, automatic history import, and live React HMR.
2. **Production Deployment Mode**: Hardened multi-stage container running as non-root `appuser`, managed PostgreSQL database, forward Alembic migrations, and health/readiness observation probes.

---

### 💻 Local Development Workflow

#### 1. Backend Setup
1. **Clone the repository and enter directory**:
   ```bash
   git clone https://github.com/Sayalij1609/Multi-Agent-Research-System.git
   cd "Multi Agent AI Research System"
   ```

2. **Create and activate a virtual environment**:
   - **Windows**:
     ```powershell
     python -m venv .venv
     .venv\Scripts\activate
     ```
   - **Linux / macOS**:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**:
   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
   Add your `GROQ_API_KEY`. (If `DATABASE_URL` is omitted, the system defaults to local SQLite `sqlite:///./synapse.db`).

5. **Run Database Migrations**:
   ```bash
   python migrate.py
   ```

6. **Start the FastAPI Backend**:
   ```bash
   uvicorn app:app --host 127.0.0.1 --port 8000 --reload
   ```

#### 2. Frontend Development Setup
1. In a separate terminal, navigate to `frontend`:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
2. Open your browser at **`http://localhost:5173`**.

---

### 🏭 Production Deployment Architecture

#### 1. Production Highlights
- **Non-Root Container User**: Runs strictly under `appuser` (UID 1001, GID 1001).
- **Zero Hardcoded Secrets**: Secrets injected strictly via runtime environment variables.
- **Relational PostgreSQL Support**: Connects to production PostgreSQL via `DATABASE_URL` or discrete `POSTGRES_*` variables with automatic connection pooling (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`).
- **Liveness & Readiness Probes**:
  - `GET /health`: Lightweight liveness check for container runtimes.
  - `GET /ready`: Deep readiness verification (executes `SELECT 1` on PostgreSQL and verifies provider credentials).
- **Structured Application Logging**: JSON-formatted log streams with automated credential and token masking (`[REDACTED]`).
- **Proper CORS Configuration**: Domain-whitelisted via `ALLOWED_ORIGINS`.
- **Safe Database Migrations**: Pre-deploy migrations executed via `python migrate.py` / `alembic upgrade head`.
- **Graceful Shutdown & Request Timeouts**: Handles Linux `SIGTERM` cleanly with 30s connection draining; protects against runaway requests with `REQUEST_TIMEOUT_SECONDS=120`.

#### 2. Docker Compose Deployment (Recommended for On-Prem / VM)
```bash
# 1. Set environment secrets in .env
cp .env.example .env
# Edit .env with your actual GROQ_API_KEY and secure JWT_SECRET_KEY

# 2. Build and launch full production stack (FastAPI + PostgreSQL 16)
docker compose up -d --build

# 3. Check health and readiness probes
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

#### 3. Render Cloud Deployment
SYNAPSE AI includes a production [`render.yaml`](render.yaml) Blueprint that provisions:
1. **Web Service**: Multi-stage Docker container running as non-root `appuser`.
2. **Managed Database**: Render PostgreSQL instance with persistent storage.
3. **Safe Pre-Deploy Migration**: `preDeployCommand: "python migrate.py"`.
4. **Automated Secret Generation**: Generates 256-bit `JWT_SECRET_KEY` automatically.

To deploy on Render:
1. Connect your repository to Render.
2. Select **New > Blueprint** and choose `render.yaml`.
3. Add your `GROQ_API_KEY` under Environment Variables.
4. Click **Apply Blueprint**.

---

## 🛠️ Technology Stack & Resource Allocation

| Component | Technology | Recommended Limit | Reservation |
|---|---|---|---|
| **Web Service (`synapse_app`)** | FastAPI, React 19, Uvicorn, LangGraph | 2048 MB RAM / 2.0 CPU | 512 MB RAM / 0.5 CPU |
| **Relational Database (`synapse_db`)** | PostgreSQL 16 Alpine, SQLAlchemy 2, Alembic | 1024 MB RAM / 1.0 CPU | 256 MB RAM / 0.2 CPU |
| **Vector Engine** | ChromaDB, Sentence-Transformers | Included in App memory | Included in App memory |

---

## 📝 License

This project is licensed under the [MIT License](LICENSE).
