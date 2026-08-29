"""Shared remotes fixtures. Seams: Celery ``.delay`` and GitLab host validate.

GitLab.com host rules are unit-tested. These tests use a second local git
repo as the destination, so validate is skipped. Credentials stay real:
save encrypts, the worker decrypts.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

import app.tasks.celery_tasks.knowledge_store.push_task as push_task
from app.config import config as app_config
from app.knowledge_store.engines.git import GitContentEngine
from app.knowledge_store.remote.forges.gitlab import GitlabProvider

pytestmark = pytest.mark.integration


@pytest.fixture
def knowledge_root(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ROOT", str(tmp_path))
    return tmp_path


@pytest.fixture
def celery_session_on_test_connection(db_session, monkeypatch):
    """Point the push worker's session maker at the test transaction."""
    maker = async_sessionmaker(
        bind=db_session.bind,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    monkeypatch.setattr(push_task, "get_celery_session_maker", lambda: maker)


@pytest.fixture
def delayed(monkeypatch):
    calls: list[int] = []
    monkeypatch.setattr(
        push_task.push_knowledge_store_revision, "delay", calls.append
    )
    return calls


@pytest.fixture
def local_gitlab(monkeypatch):
    monkeypatch.setattr(GitlabProvider, "validate", lambda self, spec: None)


@pytest.fixture
def dest(tmp_path) -> GitContentEngine:
    remote = GitContentEngine(tmp_path / "remote-dest", tmp_path / "remote-wc")
    remote._ensure_exists()
    return remote
