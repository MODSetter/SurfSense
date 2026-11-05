"""The license server's current file for a key (contract 1, producer rule 7)."""

import asyncio

import httpx

from modules.license.renewal.refresh_failed import RefreshFailedError

# The whole exchange, body included: httpx's own timeout is per read, which a
# trickle never trips. The server's own work is one Keygen validation and one check-out.
TIMEOUT_SECONDS = 10.0
# A Keygen license file is a few kilobytes, relationships included; past this it is not one.
MAX_FILE_BYTES = 64 * 1024
# As update checks name themselves: no version, no library.
USER_AGENT = "SurfSense"

_REFUSALS = {
    403: "refresh_refused",
    404: "refresh_not_found",
    429: "refresh_rate_limited",
}


async def renewed_file(server: str, key: str) -> str:
    """The file's text. The key goes in the body, alone, never in the URL, which is logged."""
    try:
        async with (
            asyncio.timeout(TIMEOUT_SECONDS),
            httpx.AsyncClient(
                timeout=TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT}
            ) as http,
            http.stream(
                "POST", f"{server}/api/v1/license/refresh", json={"key": key}
            ) as answer,
        ):
            if answer.status_code != 200:
                # 503 is Keygen out of reach; a redirect is not followed to a host never allowed.
                raise RefreshFailedError(
                    _REFUSALS.get(answer.status_code, "refresh_unavailable")
                )
            return await _file_text(answer)
    except (httpx.HTTPError, TimeoutError) as unreachable:
        raise RefreshFailedError("refresh_unavailable") from unreachable


async def _file_text(answer: httpx.Response) -> str:
    """The body as `.text` decodes it, never read past MAX_FILE_BYTES."""
    data = bytearray()
    async for chunk in answer.aiter_bytes():
        data += chunk
        if len(data) > MAX_FILE_BYTES:
            raise RefreshFailedError("refresh_unavailable")
    return bytes(data).decode(answer.encoding or "utf-8", errors="replace")
