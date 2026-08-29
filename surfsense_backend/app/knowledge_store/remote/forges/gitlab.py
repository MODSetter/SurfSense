"""GitLab.com: PAT as HTTPS password."""

from __future__ import annotations

from urllib.parse import urlsplit

from app.knowledge_store.remote.exceptions import RemoteError
from app.knowledge_store.remote.forges.base import RemoteProvider
from app.knowledge_store.remote.schemas import GitlabSpec, RemoteCredentials, RemoteSpec


class GitlabProvider(RemoteProvider):
    """``gitlab.com`` HTTPS + PAT."""

    def validate(self, spec: RemoteSpec) -> None:
        if not isinstance(spec, GitlabSpec):
            raise RemoteError("invalid_spec", "not a GitLab remote")
        if not spec.token.strip():
            raise RemoteError("invalid_spec", "GitLab PAT is required")
        host = urlsplit(spec.url).hostname or ""
        if urlsplit(spec.url).scheme != "https" or host not in {
            "gitlab.com",
            "www.gitlab.com",
        }:
            raise RemoteError("invalid_spec", "url must be https://gitlab.com/...")

    async def credentials(self, spec: RemoteSpec) -> RemoteCredentials:
        if not isinstance(spec, GitlabSpec) or not spec.token.strip():
            raise RemoteError("invalid_spec", "GitLab PAT is required")
        return RemoteCredentials(username="oauth2", password=spec.token)
