"""GitHub's releases API for one private repository, and the storage its assets redirect to.

Served over `httpx2.MockTransport`, so the store's client runs as written: the
pages it follows, the headers it sends, the redirect it takes without the token.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx2

API = "https://api.github.com"
STORAGE_HOST = "release-assets.githubusercontent.com"
REPO = "MODSetter/surfsense-job-packs"
TOKEN = "github_pat_test_only"  # pragma: allowlist secret


class FakeGitHub:
    """Releases listed newest first, `page_size` to a page, as GitHub pages them."""

    def __init__(
        self, *, repo: str = REPO, token: str = TOKEN, page_size: int = 100
    ) -> None:
        self.repo = repo
        self.token = token
        self.page_size = page_size
        self.releases: list[dict] = []
        self.stored: dict[int, bytes] = {}
        self.requests: list[httpx2.Request] = []
        # Unreachable altogether, or answering every listing with this status.
        self.down = False
        self.status: int | None = None
        self.status_headers: dict[str, str] = {}
        # An asset's download answered with this status instead of its redirect.
        self.asset_status: dict[int, int] = {}
        self.redirect_scheme = "https"
        # Assets the storage streams with no Content-Length.
        self.chunked: set[int] = set()
        # A `next` link on the last page, as a listing that sends the reader elsewhere.
        self.next_link: str | None = None
        self._next_id = 1

    def publish(
        self,
        tag: str,
        name: str,
        data: bytes,
        *,
        draft: bool = False,
        prerelease: bool = False,
        size: int | None = None,
        state: str = "uploaded",
        url: str | None = None,
    ) -> int:
        """A release with one asset, described at `url` or else under the API; returns the
        asset's id."""
        asset_id = self._next_id
        self._next_id += 1
        self.stored[asset_id] = data
        self.releases.insert(
            0,
            {
                "id": asset_id,
                "tag_name": tag,
                "draft": draft,
                "prerelease": prerelease,
                "assets": [
                    {
                        "id": asset_id,
                        "name": name,
                        "state": state,
                        "size": len(data) if size is None else size,
                        "updated_at": "2026-11-03T00:00:00Z",
                        "url": url
                        or f"{API}/repos/{self.repo}/releases/assets/{asset_id}",
                    }
                ],
            },
        )
        return asset_id

    def unpublish(self, tag: str) -> None:
        self.releases = [r for r in self.releases if r["tag_name"] != tag]

    def listings(self) -> list[httpx2.Request]:
        return [r for r in self.requests if r.url.path.endswith("/releases")]

    def downloads(self) -> list[httpx2.Request]:
        return [r for r in self.requests if "/releases/assets/" in r.url.path]

    def fetched(self) -> list[httpx2.Request]:
        """The requests that reached the asset storage."""
        return [r for r in self.requests if r.url.host == STORAGE_HOST]

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if self.down:
            raise httpx2.ConnectError("GitHub is unreachable", request=request)
        if request.url.host == STORAGE_HOST:
            return self._storage(request)
        if request.headers.get("authorization") != f"Bearer {self.token}":
            return httpx2.Response(401, json={"message": "Bad credentials"})
        releases = f"/repos/{self.repo}/releases"
        if request.url.path == releases:
            return self._listing(request, releases)
        if request.url.path.startswith(f"{releases}/assets/"):
            return self._asset(request)
        return httpx2.Response(404, json={"message": "Not Found"})

    def _listing(self, request: httpx2.Request, path: str) -> httpx2.Response:
        if self.status is not None:
            return httpx2.Response(
                self.status, headers=self.status_headers, json={"message": "refused"}
            )
        page = int(request.url.params.get("page", "1"))
        start = (page - 1) * self.page_size
        headers = {}
        if start + self.page_size < len(self.releases):
            headers["Link"] = (
                f'<{API}{path}?per_page=100&page={page + 1}>; rel="next", '
                f'<{API}{path}?per_page=100&page=1>; rel="first"'
            )
        elif self.next_link is not None:
            headers["Link"] = f'<{self.next_link}>; rel="next"'
        return httpx2.Response(
            200, json=self.releases[start : start + self.page_size], headers=headers
        )

    def _asset(self, request: httpx2.Request) -> httpx2.Response:
        asset_id = int(request.url.path.rsplit("/", 1)[1])
        if asset_id in self.asset_status:
            return httpx2.Response(self.asset_status[asset_id])
        if request.headers.get("accept") != "application/octet-stream":
            # GitHub answers the asset's description, not its bytes.
            return httpx2.Response(200, json={"id": asset_id})
        location = f"{self.redirect_scheme}://{STORAGE_HOST}/{asset_id}?sig=x"
        return httpx2.Response(302, headers={"Location": location})

    def _storage(self, request: httpx2.Request) -> httpx2.Response:
        # The signed URL is the credential; a second one is refused, as S3 does.
        if "authorization" in request.headers:
            return httpx2.Response(400, text="Only one auth mechanism allowed")
        asset_id = int(request.url.path[1:])
        data = self.stored[asset_id]
        if asset_id in self.chunked:
            return httpx2.Response(200, content=_chunks(data))
        return httpx2.Response(200, content=data)


async def _chunks(data: bytes, size: int = 1 << 20) -> AsyncIterator[bytes]:
    for start in range(0, len(data), size):
        yield data[start : start + size]
