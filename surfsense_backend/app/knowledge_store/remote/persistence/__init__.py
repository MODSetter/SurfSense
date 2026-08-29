"""Postgres models and access for workspace git remotes."""

from __future__ import annotations

from app.knowledge_store.remote.persistence.models import WorkspaceGitRemotes
from app.knowledge_store.remote.persistence.repository import WorkspaceRemoteRepository

__all__ = ["WorkspaceGitRemotes", "WorkspaceRemoteRepository"]
