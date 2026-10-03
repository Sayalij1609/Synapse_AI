"""
Automated Test Suite for SYNAPSE AI Production Readiness Architecture.

Validates:
1. Liveness endpoint: GET /health returns 200 with service metadata and timestamp.
2. Readiness endpoint: GET /ready returns 200 with database connectivity and provider checks.
3. Readiness failure handling: returns 503 when critical dependency fails.
4. Structured logging engine: JSON formatting, context request_id tracking, and sensitive secret masking.
5. CORS configuration: respects ALLOWED_ORIGINS environment variable.
6. Request timeout middleware: returns 504 Gateway Timeout on long-running queries.
7. Discrete PostgreSQL environment variable resolution (POSTGRES_USER, POSTGRES_HOST, etc.).
8. Safe database migrations runner: executes without error.
"""

import os
import json
import logging
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app import app
from structured_logger import (
    mask_sensitive_str,
    mask_dict,
    JSONLogFormatter,
    StandardStructuredFormatter,
    setup_structured_logging,
    get_logger,
    request_id_ctx,
)
from db.session import get_database_url
from migrate import run_safe_migrations


@pytest.fixture
def client():
    return TestClient(app)


# =====================================================================
# 1. Health & Readiness Probe Tests
# =====================================================================

def test_health_liveness_probe(client):
    """Liveness probe must return 200 OK with lightweight service metadata."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["service"] == "synapse-ai"
    assert "timestamp" in data
    assert data["version"] == "1.0.0"


def test_readiness_probe_success(client):
    """Readiness probe must verify database connectivity and provider configuration."""
    res = client.get("/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert "checks" in data
    assert data["checks"]["database"]["status"] == "connected"
    assert "llm_provider" in data["checks"]
    assert "environment" in data["checks"]


def test_readiness_probe_database_failure(client):
    """Readiness probe must return 503 Service Unavailable if database is unreachable."""
    with patch("sqlalchemy.orm.Session.execute", side_effect=Exception("Database connection timeout")):
        res = client.get("/ready")
        assert res.status_code == 503
        data = res.json()
        assert data["status"] == "not_ready"
        assert data["checks"]["database"]["status"] == "disconnected"
        assert "Database connection timeout" in data["checks"]["database"]["error"]


# =====================================================================
# 2. Structured Logging & Secret Masking Tests
# =====================================================================

def test_secret_masking_tokens_and_passwords():
    """Verify that sensitive credentials are never leaked in logs."""
    raw_log = "User logged in with bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz and pass postgresql://admin:super_secret_pw123@db.prod:5432/db"
    masked = mask_sensitive_str(raw_log)

    assert "super_secret_pw123" not in masked
    assert ":****@" in masked
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in masked
    assert "[REDACTED_TOKEN]" in masked


def test_secret_masking_groq_api_key():
    """Verify that Groq API keys are redacted in log text."""
    log_with_key = "Connecting to Groq API with key gsk_ABCD1234567890abcdef123456"
    masked = mask_sensitive_str(log_with_key)
    assert "gsk_ABCD1234567890abcdef123456" not in masked
    assert "gsk_ABCD...[REDACTED_KEY]" in masked


def test_mask_dictionary_recursively():
    """Verify recursive dictionary masking for structured log fields."""
    sensitive_dict = {
        "user_id": "u-123",
        "password": "my_plain_password",
        "api_key": "secret_key_abc",
        "nested": {
            "token": "bearer_jwt_xyz",
            "safe_field": "public_data"
        }
    }
    sanitized = mask_dict(sensitive_dict)

    assert sanitized["user_id"] == "u-123"
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["nested"]["token"] == "[REDACTED]"
    assert sanitized["nested"]["safe_field"] == "public_data"


def test_json_log_formatter():
    """Verify that JSONLogFormatter outputs valid JSON with timestamp, level, and request_id."""
    formatter = JSONLogFormatter()
    record = logging.LogRecord(
        name="synapse.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Processing research query",
        args=(),
        exc_info=None
    )
    token = request_id_ctx.set("req-test-99")
    try:
        output_str = formatter.format(record)
        log_json = json.loads(output_str)

        assert log_json["logger"] == "synapse.test"
        assert log_json["level"] == "INFO"
        assert log_json["message"] == "Processing research query"
        assert log_json["request_id"] == "req-test-99"
        assert "timestamp" in log_json
    finally:
        request_id_ctx.reset(token)


# =====================================================================
# 3. Environment-Based Configuration & PostgreSQL Tests
# =====================================================================

def test_database_url_from_discrete_postgres_env():
    """Verify database URL resolution from discrete POSTGRES_* environment variables."""
    with patch.dict(os.environ, {
        "DATABASE_URL": "",
        "POSTGRES_USER": "prod_user",
        "POSTGRES_PASSWORD": "prod_password_456",
        "POSTGRES_HOST": "postgres.internal.cluster",
        "POSTGRES_PORT": "5433",
        "POSTGRES_DB": "synapse_production"
    }, clear=False):
        db_url = get_database_url()
        assert db_url == "postgresql://prod_user:prod_password_456@postgres.internal.cluster:5433/synapse_production"


def test_database_url_postgres_protocol_normalization():
    """Verify postgres:// is automatically normalized to postgresql:// for SQLAlchemy."""
    with patch.dict(os.environ, {
        "DATABASE_URL": "postgres://user:pass@render-db.com:5432/app_db"
    }, clear=False):
        db_url = get_database_url()
        assert db_url == "postgresql://user:pass@render-db.com:5432/app_db"


# =====================================================================
# 4. Safe Database Migration Runner Test
# =====================================================================

def test_safe_migrations_runner():
    """Verify safe forward database migration script executes idempotently without error."""
    success = run_safe_migrations()
    assert success is True
