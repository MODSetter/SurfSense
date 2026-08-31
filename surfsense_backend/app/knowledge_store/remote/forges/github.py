"""GitHub.com App: installation token as HTTPS password."""

from __future__ import annotations

import time
from urllib.parse import quote, urlencode, urlsplit

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

    def oauth_authorize_url(self, *, state: str) -> str:
        """User-to-server OAuth start; ``state`` round-trips to our callback.

        The redirect target is *our* backend callback, so a reconnect never
        depends on the App's global Setup URL. GitHub Apps carry permissions
        on the installation, so no ``scope`` is requested.
        """
        client_id = (config.GITHUB_APP_CLIENT_ID or "").strip()
        if not client_id:
            raise RemoteError("forge", "GITHUB_APP_CLIENT_ID is not configured")
        redirect_uri = (
            f"{config.BACKEND_URL}/api/v1/workspaces/git-remotes/github/oauth/callback"
        )
        query = urlencode(
            {"client_id": client_id, "redirect_uri": redirect_uri, "state": state}
        )
        return f"https://github.com/login/oauth/authorize?{query}"

    async def exchange_user_code(self, code: str) -> str:
        """Trade an OAuth ``code`` for a user-to-server access token."""
        client_id = (config.GITHUB_APP_CLIENT_ID or "").strip()
        client_secret = (config.GITHUB_APP_CLIENT_SECRET or "").strip()
        if not client_id or not client_secret:
            raise RemoteError(
                "forge", "GITHUB_APP_CLIENT_ID / GITHUB_APP_CLIENT_SECRET not configured"
            )
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                },
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RemoteError("forge", "could not exchange GitHub code") from exc
            return self._token_from_oauth_payload(response.json())

    async def list_user_installations(self, user_token: str) -> list[dict[str, str]]:
        """Installations of this App the signed-in user can access."""
        installations: list[dict[str, str]] = []
        url = f"{_GITHUB_API}/user/installations"
        headers = {
            "Authorization": f"Bearer {user_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            while url:
                response = await client.get(url, headers=headers)
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    raise RemoteError(
                        "forge", "could not list GitHub installations"
                    ) from exc
                installations.extend(
                    self._installations_from_payload(response.json())
                )
                url = _next_link(response.headers.get("link"))
        return installations

    async def list_tree_folders(
        self, *, installation_id: str, full_name: str, branch: str
    ) -> list[str]:
        """Folders under ``branch`` of ``full_name`` (owner/repo), recursive."""
        token = await self._installation_token(installation_id)
        url = f"{_GITHUB_API}/repos/{full_name}/git/trees/{quote(branch, safe='')}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                params={"recursive": "1"},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RemoteError("forge", "could not list repository folders") from exc
            return self._folders_from_tree(response.json())

    @staticmethod
    def _token_from_oauth_payload(payload: dict) -> str:
        token = payload.get("access_token")
        if not token:
            raise RemoteError(
                "forge",
                f"GitHub OAuth failed: {payload.get('error', 'no access_token')}",
            )
        return token

    @staticmethod
    def _installations_from_payload(payload: dict) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        for inst in payload.get("installations", []):
            account = (inst.get("account") or {}).get("login") or ""
            out.append({"id": str(inst.get("id") or ""), "account": account})
        return out

    @staticmethod
    def _folders_from_tree(payload: dict) -> list[str]:
        folders = {
            entry["path"]
            for entry in payload.get("tree", [])
            if entry.get("type") == "tree" and entry.get("path")
        }
        return sorted(folders)

    async def list_repos(self, installation_id: str) -> list[dict[str, str]]:
        """Repos this installation can write: ``full_name``, clone ``url``, default branch."""
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
                repos.extend(self._repos_from_payload(response.json()))
                url = _next_link(response.headers.get("link"))
        return repos

    async def list_branches(
        self, *, installation_id: str, full_name: str
    ) -> list[str]:
        """Branch names on ``full_name`` (owner/repo), so branch is a real choice."""
        token = await self._installation_token(installation_id)
        branches: list[str] = []
        url = f"{_GITHUB_API}/repos/{full_name}/branches?per_page=100"
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
                    raise RemoteError("forge", "could not list branches") from exc
                branches.extend(self._branches_from_payload(response.json()))
                url = _next_link(response.headers.get("link"))
        return sorted(set(branches))

    @staticmethod
    def _repos_from_payload(payload: dict) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        for repo in payload.get("repositories", []):
            clone = repo.get("clone_url") or ""
            if not clone:
                continue
            out.append(
                {
                    "full_name": repo.get("full_name") or "",
                    "url": clone,
                    "default_branch": repo.get("default_branch") or "main",
                }
            )
        return out

    @staticmethod
    def _branches_from_payload(payload: list) -> list[str]:
        return [b["name"] for b in payload if b.get("name")]

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
