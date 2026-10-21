"""Reading the GitHub REST API with the standard library alone.

Stdlib only, so the daily job needs no install step and no lockfile.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from typing import Any

API_ROOT = "https://api.github.com"
_TIMEOUT_SECONDS = 30
_NEXT_LINK = re.compile(r'<([^>]+)>\s*;\s*rel="next"')

Opener = Callable[..., Any]


class GitHubAccessDeniedError(RuntimeError):
    """The token may not read this endpoint: 401, 403, or 404 for hidden ones."""


class GitHubApi:
    def __init__(
        self,
        token: str | None,
        *,
        opener: Opener = urllib.request.urlopen,
        root: str = API_ROOT,
    ) -> None:
        self._token = token
        self._opener = opener
        self._root = root.rstrip("/")

    def get(self, path: str) -> Any:
        body, _ = self._fetch(self._url(path))
        return body

    def pages(self, path: str) -> Iterator[Any]:
        """Each page of a list endpoint, following ``Link: rel="next"``."""
        url: str | None = self._url(path)
        while url:
            body, link = self._fetch(url)
            yield body
            url = next_page_url(link)

    def _url(self, path: str) -> str:
        return path if path.startswith("http") else f"{self._root}/{path.lstrip('/')}"

    def _fetch(self, url: str) -> tuple[Any, str | None]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "surfsense-release-stats",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        request = urllib.request.Request(url, headers=headers)
        try:
            with self._opener(request, timeout=_TIMEOUT_SECONDS) as response:
                return json.loads(response.read()), response.headers.get("Link")
        except urllib.error.HTTPError as error:
            if error.code in (401, 403, 404):
                raise GitHubAccessDeniedError(f"{error.code} for {url}") from error
            raise


def next_page_url(link_header: str | None) -> str | None:
    if not link_header:
        return None
    match = _NEXT_LINK.search(link_header)
    return match.group(1) if match else None
