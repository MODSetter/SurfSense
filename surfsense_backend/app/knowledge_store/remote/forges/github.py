"""GitHub.com App: installation token as HTTPS password."""

from __future__ import annotations

import time
from urllib.parse import quote, urlsplit

import httpx
import jwt

from app.config import config
from app.knowledge_store.remote.exceptions import RemoteError
from app.knowledge_store.remote.forges.base import RemoteProvider
from app.knowledge_store.remote.schemas import GithubSpec, RemoteCredentials, RemoteSpec

_GITHUB_API = "https://api.github.com"


class GithubProvider(RemoteProvider):
    """``github.com`` HTTPS + GitHub App installation token."""

    def validate(self, spec: RemoteSpec) -> None:
        """``GithubSpec`` with a github.com HTTPS clone URL and an installation id."""
        if not isinstance(spec, GithubSpec):
            raise RemoteError("invalid_spec", "not a GitHub remote")
        if not spec.installation_id.strip():
            raise RemoteError("invalid_spec", "GitHub App installation id is required")
        host = urlsplit(spec.url).hostname or ""
        if urlsplit(spec.url).scheme != "https" or host not in {
            "github.com",
            "www.github.com",
        }:
            raise RemoteError("invalid_spec", "url must be https://github.com/...")

    async def credentials(self, spec: RemoteSpec) -> RemoteCredentials:
        """Mint a 1h installation token; username is ``x-access-token``."""
        if not isinstance(spec, GithubSpec) or not spec.installation_id.strip():
            raise RemoteError("invalid_spec", "GitHub App installation id is required")
        token = await self._installation_token(spec.installation_id)
        return RemoteCredentials(username="x-access-token", password=token)

    def install_url(self, *, state: str) -> str:
        """GitHub App install page, ``state`` round-tripped on the callback."""
        slug = (config.GITHUB_APP_SLUG or "").strip()
        if not slug:
            raise RemoteError("forge", "GITHUB_APP_SLUG is not configured")
        return (
            f"https://github.com/apps/{slug}/installations/new"
            f"?state={quote(state, safe='')}"
        )

    async def list_repos(self, installation_id: str) -> list[dict[str, str]]:
        """Repos this installation can write: ``full_name`` + clone ``url``."""
        token = await self._installation_token(installation_id)
        repos: list[dict[str, str]] = []
        url = f"{_GITHUB_API}/installation/repositories"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            while url:
                response = await client.get(url, headers=headers)
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    raise RemoteError("forge", "could not list GitHub repositories") from exc
                payload = response.json()
                for repo in payload.get("repositories", []):
                    clone = repo.get("clone_url") or ""
                    if not clone:
                        continue
                    repos.append(
                        {
                            "full_name": repo.get("full_name") or "",
                            "url": clone,
                        }
                    )
                url = _next_link(response.headers.get("link"))
        return repos

    async def _installation_token(self, installation_id: str) -> str:
        """POST /app/installations/{id}/access_tokens. Lives ~1 hour."""
        app_jwt = _app_jwt()
        url = f"{_GITHUB_API}/app/installations/{installation_id}/access_tokens"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RemoteError("forge", "could not mint GitHub installation token") from exc
            token = response.json().get("token")
            if not token:
                raise RemoteError("forge", "GitHub installation token missing")
            return token


def _app_jwt() -> str:
    app_id = (config.GITHUB_APP_ID or "").strip()
    pem = (config.GITHUB_APP_PRIVATE_KEY or "").strip().replace("\\n", "\n")
    if not app_id or not pem:
        raise RemoteError("forge", "GITHUB_APP_ID / GITHUB_APP_PRIVATE_KEY not configured")
    now = int(time.time())
    return jwt.encode(
        {"iat": now - 60, "exp": now + 540, "iss": app_id},
        pem,
        algorithm="RS256",
    )


def _next_link(header: str | None) -> str | None:
    if not header:
        return None
    for part in header.split(","):
        if 'rel="next"' in part:
            start = part.find("<") + 1
            end = part.find(">")
            if start > 0 and end > start:
                return part[start:end]
    return None
