"""GitLab.com: PAT as HTTPS password."""

from __future__ import annotations

from urllib.parse import quote, urlsplit

import httpx

from app.knowledge_store.remote.exceptions import RemoteError
from app.knowledge_store.remote.forges.base import RemoteProvider
from app.knowledge_store.remote.schemas import GitlabSpec, RemoteCredentials, RemoteSpec

_GITLAB_API = "https://gitlab.com/api/v4"


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

    async def list_projects(self, token: str) -> list[dict[str, str]]:
        """Projects the PAT can push to: ``full_name``, clone ``url``, default branch."""
        projects: list[dict[str, str]] = []
        url = (
            f"{_GITLAB_API}/projects"
            "?membership=true&min_access_level=30&simple=true&per_page=100"
        )
        async with httpx.AsyncClient(timeout=30.0) as client:
            while url:
                response = await client.get(url, headers=_headers(token))
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    raise RemoteError("forge", "could not list GitLab projects") from exc
                projects.extend(self._projects_from_payload(response.json()))
                url = _next_link(response.headers.get("link"))
        return projects

    async def list_branches(self, *, token: str, project_id: str) -> list[str]:
        """Branch names on the project, so branch is a real choice."""
        branches: list[str] = []
        pid = quote(str(project_id), safe="")
        url = f"{_GITLAB_API}/projects/{pid}/repository/branches?per_page=100"
        async with httpx.AsyncClient(timeout=30.0) as client:
            while url:
                response = await client.get(url, headers=_headers(token))
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    raise RemoteError("forge", "could not list branches") from exc
                branches.extend(self._branches_from_payload(response.json()))
                url = _next_link(response.headers.get("link"))
        return sorted(set(branches))

    async def list_tree_folders(
        self, *, token: str, project_id: str, branch: str
    ) -> list[str]:
        """Folders under ``branch`` of the project, recursive."""
        folders: set[str] = set()
        pid = quote(str(project_id), safe="")
        url = (
            f"{_GITLAB_API}/projects/{pid}/repository/tree"
            f"?recursive=true&per_page=100&ref={quote(branch, safe='')}"
        )
        async with httpx.AsyncClient(timeout=30.0) as client:
            while url:
                response = await client.get(url, headers=_headers(token))
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    raise RemoteError("forge", "could not list repository folders") from exc
                folders.update(self._folders_from_tree(response.json()))
                url = _next_link(response.headers.get("link"))
        return sorted(folders)

    @staticmethod
    def _projects_from_payload(payload: list) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        for project in payload:
            clone = project.get("http_url_to_repo") or ""
            if not clone:
                continue
            out.append(
                {
                    "id": str(project.get("id") or ""),
                    "full_name": project.get("path_with_namespace") or "",
                    "url": clone,
                    "default_branch": project.get("default_branch") or "main",
                }
            )
        return out

    @staticmethod
    def _branches_from_payload(payload: list) -> list[str]:
        return [b["name"] for b in payload if b.get("name")]

    @staticmethod
    def _folders_from_tree(payload: list) -> list[str]:
        return [
            entry["path"]
            for entry in payload
            if entry.get("type") == "tree" and entry.get("path")
        ]


def _headers(token: str) -> dict[str, str]:
    return {"PRIVATE-TOKEN": token, "Accept": "application/json"}


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
