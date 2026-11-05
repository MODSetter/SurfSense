"""The packs' store: the releases of one private repository that holds only releases.

Each release is tagged `<id>-v<version>` and carries one asset, `<id>-<version>.zip`.
The token goes to GitHub's API alone: an asset's download redirects to storage whose
signed URL is its own credential, so that request carries no token.
"""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx2

from license.job_packs.manifest import PackRefusedError
from license.job_packs.source import PackAsset, PackSourceError
from license.job_packs.verify import MAX_PACK_BYTES

logger = logging.getLogger(__name__)

API = "https://api.github.com"
API_VERSION = "2022-11-28"
USER_AGENT = "SurfSense-license-server"
_TIMEOUT = httpx2.Timeout(15.0, connect=5.0)
# 1,000 releases: years of versions, and a bound on a listing that never ends.
_MAX_PAGES = 10
# Digits 0 to 9 only: \d takes any script's, which no header can carry.
_TAG = re.compile(
    r"^(?P<id>[a-z][a-z0-9-]{0,63})-v(?P<version>[0-9]+\.[0-9]+\.[0-9]+)$"
)
_REDIRECTS = frozenset({301, 302, 303, 307, 308})


@asynccontextmanager
async def _http() -> AsyncIterator[httpx2.AsyncClient]:
    async with httpx2.AsyncClient(timeout=_TIMEOUT, follow_redirects=False) as client:
        yield client


@dataclass(frozen=True)
class GitHubReleases:
    repo: str
    token: str = field(repr=False)

    async def assets(self) -> list[PackAsset]:
        found = []
        for release in await self._releases():
            asset = self._asset_of(release)
            if asset is not None:
                found.append(asset)
        return found

    async def read(self, asset: PackAsset) -> bytes:
        try:
            async with _http() as http:
                async with http.stream(
                    "GET",
                    asset.locator,
                    headers=self._headers("application/octet-stream"),
                ) as answer:
                    if answer.status_code == 200:
                        return await _capped(answer, asset.name)
                    if answer.status_code not in _REDIRECTS:
                        raise PackSourceError(
                            f"GitHub answered {answer.status_code} for {asset.name}"
                        )
                    location = answer.headers.get("location", "")
                if not location.startswith("https://"):
                    raise PackSourceError(
                        f"GitHub sent {asset.name} to an address that is not https"
                    )
                async with http.stream(
                    "GET", location, headers={"User-Agent": USER_AGENT}
                ) as stored:
                    if stored.status_code != 200:
                        raise PackSourceError(
                            f"GitHub's storage answered {stored.status_code} "
                            f"for {asset.name}"
                        )
                    return await _capped(stored, asset.name)
        except (httpx2.HTTPError, httpx2.InvalidURL) as error:
            # Its message would name the signed storage URL.
            raise PackSourceError(
                f"{asset.name} could not be downloaded ({type(error).__name__})"
            ) from None

    async def _releases(self) -> list[dict]:
        url = f"{API}/repos/{self.repo}/releases?per_page=100"
        releases: list[dict] = []
        try:
            async with _http() as http:
                for _ in range(_MAX_PAGES):
                    answer = await http.get(
                        url, headers=self._headers("application/vnd.github+json")
                    )
                    self._raise_for_refusal(answer)
                    page = _json(answer)
                    if not isinstance(page, list):
                        raise PackSourceError("GitHub's release list is not a list")
                    releases += [
                        release for release in page if isinstance(release, dict)
                    ]
                    url = (answer.links.get("next") or {}).get("url", "")
                    if not url:
                        return releases
                    # The token is sent with the next page too, so only to the API.
                    if not url.startswith(f"{API}/"):
                        raise PackSourceError("GitHub's next page is outside its API")
        except httpx2.HTTPError as error:
            raise PackSourceError(
                f"GitHub could not be reached ({type(error).__name__})"
            ) from None
        logger.warning(
            "%s lists more than %d pages of releases; the rest are not read",
            self.repo,
            _MAX_PAGES,
        )
        return releases

    def _raise_for_refusal(self, answer: httpx2.Response) -> None:
        status = answer.status_code
        if status == 200:
            return
        if status == 401:
            raise PackSourceError(
                "GitHub refused JOB_PACKS_GITHUB_TOKEN: it is wrong or has expired"
            )
        if status == 403 and answer.headers.get("x-ratelimit-remaining") == "0":
            raise PackSourceError(
                f"GitHub's rate limit is spent until {_reset_time(answer)}"
            )
        if status in {403, 404}:
            raise PackSourceError(
                f"JOB_PACKS_GITHUB_REPO {self.repo} does not exist, "
                "or the token cannot read it"
            )
        raise PackSourceError(f"GitHub answered {status}")

    def _asset_of(self, release: dict) -> PackAsset | None:
        """The release's one asset when it is a pack's, else None and the reason logged."""
        if release.get("draft") or release.get("prerelease"):
            return None
        tag = str(release.get("tag_name") or "")
        tagged = _TAG.fullmatch(tag)
        if tagged is None:
            logger.warning(
                "Release %r of %s is not tagged <id>-v<version>, so it is skipped",
                tag,
                self.repo,
            )
            return None
        expected = f"{tagged['id']}-{tagged['version']}.zip"
        uploaded = [
            asset
            for asset in release.get("assets") or []
            if isinstance(asset, dict) and asset.get("state") == "uploaded"
        ]
        if [asset.get("name") for asset in uploaded] != [expected]:
            logger.warning(
                "Release %s of %s does not carry exactly one uploaded asset, %s, "
                "so it is skipped",
                tag,
                self.repo,
                expected,
            )
            return None
        (asset,) = uploaded
        size = asset.get("size")
        locator = str(asset.get("url") or "")
        if not isinstance(size, int) or not locator.startswith(f"{API}/"):
            logger.warning("Release %s's asset is not as GitHub describes one", tag)
            return None
        if size > MAX_PACK_BYTES:
            logger.error("%s is larger than 50 MB, so it is never served", expected)
            return None
        return PackAsset(
            name=expected,
            ref=f"github:{asset.get('id')}:{asset.get('updated_at')}:{size}",
            size=size,
            locator=locator,
        )

    def _headers(self, accept: str) -> dict[str, str]:
        return {
            "Accept": accept,
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": USER_AGENT,
        }


async def _capped(answer: httpx2.Response, name: str) -> bytes:
    """The body, refused past the cap: by its Content-Length first, then as it streams."""
    declared = answer.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_PACK_BYTES:
        raise PackRefusedError("PACK_TOO_LARGE", f"{name} is larger than 50 MB.")
    body = bytearray()
    async for chunk in answer.aiter_bytes():
        body += chunk
        if len(body) > MAX_PACK_BYTES:
            raise PackRefusedError("PACK_TOO_LARGE", f"{name} is larger than 50 MB.")
    return bytes(body)


def _json(answer: httpx2.Response) -> object:
    try:
        return answer.json()
    except ValueError:
        raise PackSourceError("GitHub's release list is not JSON") from None


def _reset_time(answer: httpx2.Response) -> str:
    reset = answer.headers.get("x-ratelimit-reset", "")
    if not reset.isdigit():
        return "GitHub resets it"
    return datetime.fromtimestamp(int(reset), UTC).strftime("%Y-%m-%d %H:%M UTC")
