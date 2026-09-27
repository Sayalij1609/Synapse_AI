"""
SYNAPSE AI — Database Engine & Session Management.
Supports PostgreSQL (production) with automatic fallback to SQLite (local/testing).
Enforces foreign-key constraints, connection pooling, and safe transactional contexts.
"""

import logging
import os
import re
from contextlib import contextmanager
from typing import Generator
from urllib.parse import urlparse

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker, Session

load_dotenv()

logger = logging.getLogger("synapse.db.session")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def _mask_db_url(url: str) -> str:
    """Mask password in database URL for safe logging."""
    if not url:
        return ""
    try:
        # Regex to mask :password@
        return re.sub(r":([^/@:]+)@", ":****@", url)
    except Exception:
        return "<masked_url>"


def get_database_url() -> str:
    """
    Resolve and normalize the database URL from environment variables.
    Order of precedence:
    1. DATABASE_URL environment variable (auto-converts postgres:// to postgresql://)
    2. Discrete environment variables: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB
    3. Defaults to sqlite:///./synapse.db if no PostgreSQL configuration is found
    """
    raw_url = os.getenv("DATABASE_URL", "").strip()

    if raw_url:
        # Handle Heroku / older style postgres://
        if raw_url.startswith("postgres://"):
            raw_url = raw_url.replace("postgres://", "postgresql://", 1)
        return raw_url

    # Check discrete PostgreSQL variables
    pg_host = os.getenv("POSTGRES_HOST", "").strip()
    if pg_host:
        pg_user = os.getenv("POSTGRES_USER", "postgres")
        pg_password = os.getenv("POSTGRES_PASSWORD", "")
        pg_port = os.getenv("POSTGRES_PORT", "5432")
        pg_db = os.getenv("POSTGRES_DB", "synapse_db")
        auth = f"{pg_user}:{pg_password}" if pg_password else pg_user
        constructed_url = f"postgresql://{auth}@{pg_host}:{pg_port}/{pg_db}"
        logger.info("Constructed PostgreSQL URL from discrete environment variables for host: %s", pg_host)
        return constructed_url

    default_sqlite = "sqlite:///./synapse.db"
    logger.info("DATABASE_URL not set; using local SQLite storage: %s", default_sqlite)
    return default_sqlite


DATABASE_URL = get_database_url()
is_sqlite = DATABASE_URL.startswith("sqlite")

# Engine configuration with appropriate pooling
engine_kwargs = {
    "echo": False,  # Prevent leaking query data/secrets to stdout
}

if is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
        "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "1800")),
    })

try:
    engine: Engine = create_engine(DATABASE_URL, **engine_kwargs)
    logger.info("Database engine initialized: %s", _mask_db_url(DATABASE_URL))
except Exception as e:
    logger.error("Failed to initialize database engine for %s: %s", _mask_db_url(DATABASE_URL), str(e))
    # Fallback to local SQLite if remote PostgreSQL connection fails at engine creation
    DATABASE_URL = "sqlite:///./synapse.db"
    is_sqlite = True
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    logger.warning("Fell back to local SQLite engine: %s", DATABASE_URL)


# Enable SQLite Foreign Key constraints
if is_sqlite:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions with automatic commit/rollback.
    Usage:
        with db_session() as session:
            session.add(obj)
    """
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error("Database transaction rolled back due to error: %s", str(e))
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session.
    Automatically commits on normal return and rolls back on exception.
    """
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error("Request database session rolled back: %s", str(e))
        raise
    finally:
        session.close()


def init_db() -> None:
    """Create all database tables if they do not already exist."""
    from db.models import Base
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified/created successfully.")
    except Exception as e:
        logger.error("Database schema creation failed: %s", str(e))
        raise
