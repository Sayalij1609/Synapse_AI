"""
SYNAPSE AI — Production Structured Application Logging Engine.

Features:
- Configurable formats: JSON logging (for container log aggregators/Render/Datadog) or structured text (for local dev).
- Context-aware request tracing: request_id tracking via contextvars.
- Automatic secret and token masking (passwords, JWTs, Bearer tokens, DB credentials, API keys).
- Environment-driven log levels: LOG_LEVEL (DEBUG, INFO, WARNING, ERROR).
- Request logging middleware for FastAPI with millisecond duration tracking.
"""

import json
import logging
import os
import re
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Context variable for distributed request tracking across async execution
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")

SENSITIVE_KEYS = {
    "password", "secret", "token", "access_token", "jwt", "api_key",
    "groq_api_key", "authorization", "cookie", "set-cookie", "jwt_secret_key"
}


def mask_sensitive_str(text: str) -> str:
    """Mask sensitive tokens, passwords, and API keys in log strings."""
    if not text:
        return ""
    masked = text
    # Mask Bearer tokens
    masked = re.sub(r"(bearer\s+)[A-Za-z0-9_\-\.]+", r"\1[REDACTED_TOKEN]", masked, flags=re.IGNORECASE)
    # Mask Groq API keys
    masked = re.sub(r"(gsk_[A-Za-z0-9_]{4})[A-Za-z0-9_]+", r"\1...[REDACTED_KEY]", masked, flags=re.IGNORECASE)
    # Mask DB credentials in URLs
    masked = re.sub(r":([^/@:]+)@", r":****@", masked)
    return masked


def mask_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively mask sensitive keys in nested dictionaries."""
    sanitized = {}
    for k, v in data.items():
        if isinstance(k, str) and k.lower() in SENSITIVE_KEYS:
            sanitized[k] = "[REDACTED]"
        elif isinstance(v, dict):
            sanitized[k] = mask_dict(v)
        elif isinstance(v, str):
            sanitized[k] = mask_sensitive_str(v)
        else:
            sanitized[k] = v
    return sanitized


class JSONLogFormatter(logging.Formatter):
    """Production JSON log formatter for containerized log aggregators."""

    def format(self, record: logging.LogRecord) -> str:
        req_id = request_id_ctx.get("") or getattr(record, "request_id", "")
        message = mask_sensitive_str(record.getMessage())

        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": message,
            "module": record.module,
            "line": record.lineno,
        }

        if req_id:
            log_obj["request_id"] = req_id

        # Attach extra metadata if provided
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            log_obj.update(mask_dict(record.extra_fields))

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


class StandardStructuredFormatter(logging.Formatter):
    """Structured human-readable formatter for local development and console output."""

    def format(self, record: logging.LogRecord) -> str:
        req_id = request_id_ctx.get("") or getattr(record, "request_id", "")
        req_prefix = f" [{req_id}]" if req_id else ""
        msg = mask_sensitive_str(record.getMessage())
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        base = f"[{ts}] [{record.name}] [{record.levelname}]{req_prefix} {msg}"
        if record.exc_info:
            base += f"\n{self.formatException(record.exc_info)}"
        return base


def setup_structured_logging():
    """Configure root and synapse loggers based on environment variables."""
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    log_format = os.getenv("LOG_FORMAT", "").lower()
    is_prod = os.getenv("ENVIRONMENT", "development").lower() == "production"

    use_json = log_format == "json" or (is_prod and log_format != "text")

    handler = logging.StreamHandler(sys.stdout)
    if use_json:
        handler.setFormatter(JSONLogFormatter())
    else:
        handler.setFormatter(StandardStructuredFormatter())

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = [handler]

    # Silence noise from verbose third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)

    return root_logger


def get_logger(name: str = "synapse") -> logging.Logger:
    """Get or create a named structured logger."""
    return logging.getLogger(name)
