"""
SYNAPSE AI — Root Application Entrypoint Proxy.

Delegates directly to `backend.app` to provide 100% backward compatibility
for existing deployments, CLI commands (e.g. `uvicorn app:app`), Dockerfiles,
and test suites.
"""

import sys
import os

# Ensure backend and root directories are on Python search path
_current_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.join(_current_dir, "backend")
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from backend.app import *
from backend.app import (
    app,
    lifespan,
    markdown_to_pdf,
    markdown_to_docx,
    markdown_to_markdown,
)

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.app:app", host="127.0.0.1", port=port, reload=True)
