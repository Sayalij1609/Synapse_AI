# 🐳 Production Docker Deployment — SYNAPSE AI

SYNAPSE AI is containerized for production using an optimized multi-stage build, non-root user security model, managed PostgreSQL database integration, and health/readiness observation probes.

---

## 1. Production Container Architecture

```text
 ┌──────────────────────────────────────────────────────────────┐
 │                  Docker Host / Cloud Runtime                 │
 │                                                              │
 │  ┌────────────────────────────────────────────────────────┐  │
 │  │             Container: synapse_app (Non-Root)          │  │
 │  │                                                        │  │
 │  │   FastAPI (uvicorn) :8000                              │  │
 │  │    ├── GET /health (Liveness)                          │  │
 │  │    ├── GET /ready (Readiness & DB Check)               │  │
 │  │    ├── Structured Logging (JSON / Masked Secrets)      │  │
 │  │    └── Static React SPA (/app/frontend/dist)           │  │
 │  │                                                        │  │
 │  │   Multi-Agent Research Pipeline (LangGraph/LangChain)  │  │
 │  │    └── Vector Store & Deduplication Engine             │  │
 │  └───────────────────────────┬────────────────────────────┘  │
 │                              │ Internal Network              │
 │                              ▼ (synapse_net)                 │
 │  ┌────────────────────────────────────────────────────────┐  │
 │  │           Container: synapse_postgres (PostgreSQL 16)  │  │
 │  │                                                        │  │
 │  │   Persistent Volume: synapse_postgres_data             │  │
 │  │   Port: 5432                                           │  │
 │  └────────────────────────────────────────────────────────┘  │
 └──────────────────────────────────────────────────────────────┘
```

---

## 2. Multi-Stage Build Pipeline

The `Dockerfile` isolates the frontend build environment from the lean runtime container:

```text
 Stage 1: frontend-builder (node:20-alpine)
   1. Cache frontend/package*.json
   2. npm ci (clean reproducible install)
   3. npm run build → outputs /app/frontend/dist

                           │ (Static bundle copied)
                           ▼
 Stage 2: runner (python:3.12-slim)
   1. Install minimal OS runtime (curl, libpq5)
   2. Create non-root user 'appuser' (UID: 1001, GID: 1001)
   3. pip install -r requirements.txt
   4. COPY backend python code, alembic migrations & schema
   5. COPY --from=frontend-builder /app/frontend/dist
   6. USER appuser
   7. HEALTHCHECK CMD curl -f http://localhost:${PORT}/health
   8. CMD exec uvicorn app:app --timeout-keep-alive 65 --graceful-timeout 30
```

### Security & Operational Highlights
- **Non-Root Execution**: Runs strictly as unprivileged user `appuser` (UID 1001).
- **Zero Secrets Baked**: API keys and passwords are NEVER copied into the image. All configuration is injected via environment variables at runtime.
- **Graceful Shutdown**: Starts with `exec uvicorn` so Linux signals (`SIGTERM`) pass directly to the ASGI server with a 30-second graceful drain window.
- **Resource Constraints**: Pre-configured CPU and memory limits preventing noisy neighbor resource exhaustion.

---

## 3. Quick Start with Docker Compose

The fastest way to test production-like behavior locally is via `docker-compose.yml`.

### Prerequisites
- Docker Engine 24+ and Docker Compose v2.
- A valid Groq API key (`GROQ_API_KEY`).

### Step 1: Configure Environment
Copy `.env.example` to `.env` (or pass variables via CLI):

```bash
cp .env.example .env
```

Ensure `GROQ_API_KEY` is set in your `.env`:
```ini
GROQ_API_KEY=gsk_your_actual_key_here
```

### Step 2: Build and Start Stack
```bash
docker compose up -d --build
```

Docker Compose will:
1. Build the multi-stage image.
2. Spin up PostgreSQL 16 Alpine and wait for health status (`pg_isready`).
3. Run forward database migrations (`AUTO_MIGRATE=true`).
4. Start SYNAPSE AI on `http://localhost:8000`.

### Step 3: Verify Liveness & Readiness
```bash
# Liveness probe
curl http://localhost:8000/health
# {"status":"healthy","service":"synapse-ai","version":"1.0.0"}

# Readiness probe (verifies database & provider readiness)
curl http://localhost:8000/ready
# {"status":"ready","checks":{"database":{"status":"connected","dialect":"postgresql"}}}
```

### Step 4: Stop Stack
```bash
# Stop containers (preserves database volume)
docker compose down

# Stop and wipe persistent volume data
docker compose down -v
```

---

## 4. Standalone Docker Run (Without Compose)

### Build the Image
```bash
docker build -t synapse-ai:latest .
```

### Run with Local SQLite (Development Container)
```bash
docker run -d \
  --name synapse-ai \
  -p 8000:8000 \
  -e GROQ_API_KEY="gsk_your_key_here" \
  -e ENVIRONMENT="production" \
  -e LOG_LEVEL="INFO" \
  synapse-ai:latest
```

### Run with External PostgreSQL
```bash
docker run -d \
  --name synapse-ai \
  -p 8000:8000 \
  -e GROQ_API_KEY="gsk_your_key_here" \
  -e DATABASE_URL="postgresql://user:password@db-host:5432/synapse_db" \
  -e JWT_SECRET_KEY="secure_random_hex_key" \
  -e ALLOWED_ORIGINS="https://yourdomain.com" \
  synapse-ai:latest
```

---

## 5. Production Resource Allocation Guidelines

| Component | Minimum Reservation | Recommended Limit | Notes |
|---|---|---|---|
| **synapse_app** | 512 MB RAM / 0.5 CPU | 2048 MB RAM / 2.0 CPU | ChromaDB embedding index & PDF/DOCX compiler |
| **synapse_postgres** | 256 MB RAM / 0.2 CPU | 1024 MB RAM / 1.0 CPU | PostgreSQL connection pool & transaction log |
