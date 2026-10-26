"""Reading the GitHub REST API with the standard library alone.

Stdlib only, so the daily job needs no install step and no lockfile.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator
from typing import Any

API_ROOT = "https://api.github.com"
_TIMEOUT_SECONDS = 30
_NEXT_LINK = re.compile(r'<([^>]+)>\s*;\s*rel="next"')

Opener = Callable[..., Any]


class GitHubAccessDeniedError(RuntimeError):
    """The token may not read this endpoint: 401, 403, or 404 for hidden ones."""


class GitHubOriginError(RuntimeError):
    """A next-page link or redirect is off the API's origin, so it is not read."""


class GitHubApi:
    def __init__(
        self,
        token: str | None,
        *,
        opener: Opener | None = None,
        root: str = API_ROOT,
    ) -> None:
        self._token = token
        self._root = root.rstrip("/")
        self._opener = (
            opener or urllib.request.build_opener(_SameOriginRedirects(self._root)).open
        )

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
        # The token goes with every request, so only the API's own origin gets one.
        if _origin(url) != _origin(self._root):
            raise GitHubOriginError(f"{url} is not on {self._root}; not reading it")
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


class _SameOriginRedirects(urllib.request.HTTPRedirectHandler):
    """Follows a redirect only on the API's origin.

    urllib copies every header onto the redirected request, the token included.
    """

    def __init__(self, root: str) -> None:
        self._root = root

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if _origin(newurl) != _origin(self._root):
            fp.close()
            raise GitHubOriginError(
                f"{req.full_url} redirects to {newurl}, off {self._root}; "
                "not following it"
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def next_page_url(link_header: str | None) -> str | None:
    if not link_header:
        return None
    match = _NEXT_LINK.search(link_header)
    return match.group(1) if match else None


def _origin(url: str) -> tuple[str, str]:
    parts = urllib.parse.urlsplit(url)
    return parts.scheme.lower(), parts.netloc.lower()
