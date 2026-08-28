"""Forge providers: ``provider_for(name)``."""

from __future__ import annotations

from app.knowledge_store.remote.exceptions import RemoteError
from app.knowledge_store.remote.forges.base import RemoteProvider
from app.knowledge_store.remote.forges.github import GithubProvider
from app.knowledge_store.remote.forges.gitlab import GitlabProvider
from app.knowledge_store.remote.schemas import RemoteProviderName

_PROVIDERS: dict[RemoteProviderName, RemoteProvider] = {
    "github": GithubProvider(),
    "gitlab": GitlabProvider(),
}


def provider_for(name: str) -> RemoteProvider:
    """The ``RemoteProvider`` for ``name``."""
    if name == "github":
        return _PROVIDERS["github"]
    if name == "gitlab":
        return _PROVIDERS["gitlab"]
    raise RemoteError("invalid_spec", f"unknown provider {name!r}")
