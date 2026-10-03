"""
SYNAPSE AI — Root Database Migration Runner Proxy.

Delegates directly to `backend.migrate` for backward compatibility
with deployment platforms (Render, Docker, CI/CD) and existing test suites.
"""

import sys
import os

_current_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.join(_current_dir, "backend")
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from backend.migrate import run_safe_migrations

if __name__ == "__main__":
    success = run_safe_migrations()
    sys.exit(0 if success else 1)
