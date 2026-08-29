"""Value objects the git-remote facade speaks."""

from __future__ import annotations

from app.knowledge_store.remote.schemas.credentials import RemoteCredentials
from app.knowledge_store.remote.schemas.spec import (
    GithubSpec,
    GitlabSpec,
    RemoteProviderName,
    RemoteSpec,
)
from app.knowledge_store.remote.schemas.status import RemoteStatus

__all__ = [
    "GithubSpec",
    "GitlabSpec",
    "RemoteCredentials",
    "RemoteProviderName",
    "RemoteSpec",
    "RemoteStatus",
]
