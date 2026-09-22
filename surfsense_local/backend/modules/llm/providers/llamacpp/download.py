"""Fetch a GGUF into the models directory.

SurfSense downloads rather than delegating to `POST /models`, for one reason
that decides it and two that pay for it. llama-server is a second process we do
not proxy, so an in-process fetch is **the only place `egress.require()` can
hold**. It also buys resume, which matters because a model is gigabytes, and a
checksum, which matters because a half written file is indistinguishable from a
whole one to a runtime that discovers a directory.
"""

import hashlib
from collections.abc import AsyncIterator
from pathlib import Path

import httpx

from modules.llm.providers.types import DownloadProgress

TIMEOUT = httpx.Timeout(600.0, connect=10.0)
_CHUNK = 1024 * 1024


async def download_gguf(
    url: str,
    destination: Path,
    *,
    sha256: str | None = None,
    transport: httpx.BaseTransport | None = None,
) -> AsyncIterator[DownloadProgress]:
    """Stream a model to `destination`, yielding progress as it lands.

    Writes to a sibling `.part` file and renames only once the whole file is
    present and verified, so the router never discovers a partial model. A
    cancelled download keeps the `.part` for a later resume.
    """
    partial = destination.with_suffix(destination.suffix + ".part")
    destination.parent.mkdir(parents=True, exist_ok=True)
    already = partial.stat().st_size if partial.exists() else 0

    headers = {"Range": f"bytes={already}-"} if already else {}
    async with httpx.AsyncClient(
        timeout=TIMEOUT, transport=transport, follow_redirects=True
    ) as client, client.stream("GET", url, headers=headers) as reply:
        reply.raise_for_status()
        resumed = reply.status_code == 206
        total = already + int(reply.headers.get("content-length", 0))

        # The server ignored our Range, so the bytes we have are worthless.
        mode = "ab" if resumed and already else "wb"
        done = already if resumed else 0

        with partial.open(mode) as handle:
            async for chunk in reply.aiter_bytes(_CHUNK):
                handle.write(chunk)
                done += len(chunk)
                yield DownloadProgress("downloading", completed=done, total=total)

    if sha256 is not None:
        actual = _digest(partial)
        if actual != sha256:
            partial.unlink(missing_ok=True)
            raise ValueError(
                f"checksum mismatch for {destination.name}: "
                f"expected {sha256}, got {actual}"
            )

    partial.replace(destination)
    yield DownloadProgress("complete", completed=done, total=total)


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()
