"""E2E test harness root.

This package is loaded only by the test entrypoints
(`tests/e2e/run_backend.py`, `tests/e2e/run_celery.py`). It is excluded
from the production Docker image via `surfsense_backend/.dockerignore`,
so production binaries never see this code.
"""
