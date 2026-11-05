"""The license server's current file for a key (contract 1, producer rule 7)."""

import httpx

from modules.license.renewal.refresh_failed import RefreshFailedError

# The server's own work is one Keygen validation and one check-out.
TIMEOUT_SECONDS = 10.0
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
        async with httpx.AsyncClient(
            timeout=TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT}
        ) as http:
            answer = await http.post(
                f"{server}/api/v1/license/refresh", json={"key": key}
            )
    except httpx.HTTPError as unreachable:
        raise RefreshFailedError("refresh_unavailable") from unreachable
    if answer.status_code == 200:
        return answer.text
    # 503 is Keygen out of reach; a redirect is not followed to a host never allowed.
    raise RefreshFailedError(_REFUSALS.get(answer.status_code, "refresh_unavailable"))
