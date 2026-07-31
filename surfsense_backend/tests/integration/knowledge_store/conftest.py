"""Integration conftest — prerequisites: Redis (``REDIS_APP_URL``) only.

Contenders normally wait 10s before giving up; tests shrink that window so
contention cases resolve quickly. The give-up behavior itself is unchanged.
"""

from __future__ import annotations

import uuid

import pytest

import app.knowledge_store.write_lock as write_lock


@pytest.fixture
def workspace_id() -> str:
    """Unique per test so runs never contend with each other or stale keys."""
    return f"it-{uuid.uuid4().hex}"


@pytest.fixture
def short_lock_wait(monkeypatch):
    monkeypatch.setattr(write_lock, "LOCK_WAIT_SECONDS", 0.2)
