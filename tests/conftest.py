"""
Global Pytest Configuration and Path Setup.
Ensures root and backend directories are always in Python's search path for all test suites.
"""
import sys
import os

# Resolve paths
tests_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(tests_dir)
backend_dir = os.path.join(root_dir, "backend")

# Ensure backend and root are top-priority on sys.path
for path in [backend_dir, root_dir]:
    if path not in sys.path:
        sys.path.insert(0, path)
