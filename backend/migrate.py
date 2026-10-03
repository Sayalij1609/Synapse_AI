"""
SYNAPSE AI — Safe Production Database Migration Runner.

Usage:
    python migrate.py

Performs:
1. Validates database connectivity and resolves dialect (PostgreSQL / SQLite).
2. Runs Alembic forward migrations (alembic upgrade head) within a safe transaction.
3. Synchronizes historical JSON archives (idempotent, skips existing session IDs).
4. Emits structured status codes for CI/CD, Render preDeployCommand, or container entrypoint.
"""

import os
import sys
import logging
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from db.session import get_database_url, engine, _mask_db_url
from db.migration_util import migrate_history_file

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [synapse.migration] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("synapse.migration")


def run_safe_migrations() -> bool:
    """Execute forward database migrations safely."""
    db_url = get_database_url()
    logger.info("Initiating database migration for target: %s", _mask_db_url(db_url))

    # 1. Connectivity Check
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connectivity check succeeded.")
    except Exception as conn_err:
        logger.error("Failed database connectivity check: %s", str(conn_err))
        return False

    # 2. Alembic Forward Migration
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        alembic_ini_path = os.path.join(project_root, "alembic.ini")
        if not os.path.exists(alembic_ini_path):
            alembic_ini_path = os.path.join(os.path.dirname(__file__), "alembic.ini")

        alembic_cfg = Config(alembic_ini_path)
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)

        logger.info("Executing 'alembic upgrade head'...")
        command.upgrade(alembic_cfg, "head")
        logger.info("Alembic schema migrations completed successfully.")
    except Exception as alembic_err:
        logger.error("Alembic migration failed: %s", str(alembic_err), exc_info=True)
        return False

    # 3. Synchronize Historical JSON Archive if Present
    history_file = os.path.join(project_root, "research_history.json")
    if not os.path.exists(history_file):
        history_file = os.path.join(os.path.dirname(__file__), "research_history.json")
    if os.path.exists(history_file):
        try:
            logger.info("Checking historical archive '%s' for pending import...", history_file)
            stats = migrate_history_file(history_file)
            logger.info("Historical sync: %s sessions imported, %s skipped.", stats.get("migrated", 0), stats.get("skipped", 0))
        except Exception as hist_err:
            logger.warning("Historical sync encountered non-fatal warning: %s", str(hist_err))

    logger.info("Database migration sequence completed without errors.")
    return True


if __name__ == "__main__":
    success = run_safe_migrations()
    sys.exit(0 if success else 1)
