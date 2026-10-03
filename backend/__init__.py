"""
SYNAPSE AI Backend Package.
Contains all autonomous research agents, pipeline orchestration, database services, and API endpoints.
"""
import sys
import os

# Ensure backend directory is in sys.path for direct imports
_backend_dir = os.path.dirname(os.path.abspath(__file__))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)
