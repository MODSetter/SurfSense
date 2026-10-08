"""Fetch the pinned upstream file, resumably, and keep it only if its sha256 matches.

The first request goes to the pinned host, which the user allowed; TDF answers
with a redirect to one of its mirrors. Redirects are followed by hand, https
only and at most a few, because the pin's sha256, not the mirror, is what
vouches for the bytes.
"""

import asyncio
import hashlib
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx

from modules.runtime_packs.office.pin import PackFile

TIMEOUT = httpx.Timeout(60.0, connect=15.0)
MAX_REDIRECTS = 3
_CHUNK = 1024 * 1024


class DownloadRefusedError(Exception):
    """The download went somewhere it may not, or brought back the wrong bytes."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class Progress:
    completed: int
    total: int


async def download_pack_file(
    file: PackFile,
    destination: Path,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> AsyncIterator[Progress]:
    """Stream `file` to `destination`, yielding progress; a `.part` beside it resumes.

    Raises DownloadRefusedError for a redirect that is not https, too many redirects,
    more bytes than pinned, or a sha256 that does not match (the `.part` is deleted).
    """
    partial = destination.with_name(destination.name + ".part")
    destination.parent.mkdir(parents=True, exist_ok=True)
    have = partial.stat().st_size if partial.exists() else 0
    if have > file.size:
        partial.unlink()
        have = 0
    if have < file.size:
        async for progress in _fetch(file, partial, have, transport):
            yield progress
    # Off the event loop: hashing a few hundred MB takes seconds.
    await asyncio.to_thread(_verify, file, partial)
    partial.replace(destination)
    yield Progress(file.size, file.size)


async def _fetch(
    file: PackFile,
    partial: Path,
    have: int,
    transport: httpx.AsyncBaseTransport | None,
) -> AsyncIterator[Progress]:
    headers = {"Range": f"bytes={have}-"} if have else {}
    async with httpx.AsyncClient(
        timeout=TIMEOUT, transport=transport, follow_redirects=False
    ) as client:
        url = file.url
        for _ in range(MAX_REDIRECTS + 1):
            async with client.stream("GET", url, headers=headers) as reply:
                if reply.is_redirect:
                    url = _next_hop(url, reply.headers.get("location", ""))
                    continue
                reply.raise_for_status()
                # A server that ignored Range sends the whole file again.
                resumed = reply.status_code == 206
                done = have if resumed else 0
                with partial.open("ab" if resumed else "wb") as handle:
                    async for chunk in reply.aiter_bytes(_CHUNK):
                        done += len(chunk)
                        if done > file.size:
                            break
                        handle.write(chunk)
                        yield Progress(done, file.size)
                if done > file.size:
                    partial.unlink()
                    raise DownloadRefusedError(
                        "too_large", "the download is larger than pinned"
                    )
                return
        raise DownloadRefusedError(
            "too_many_redirects", f"more than {MAX_REDIRECTS} redirects"
        )


def _next_hop(current: str, location: str) -> str:
    target = urljoin(current, location)
    if urlsplit(target).scheme != "https" or not urlsplit(target).hostname:
        raise DownloadRefusedError("insecure_redirect", "a redirect left https")
    return target


def _verify(file: PackFile, partial: Path) -> None:
    digest = _sha256(partial)
    if digest != file.sha256:
        partial.unlink(missing_ok=True)
        raise DownloadRefusedError(
            "checksum_mismatch", f"sha256 {digest} is not the pinned {file.sha256}"
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()
