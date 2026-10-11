"""A paid plugin's access: the request's `License <key>`, checked with Keygen as contract 2 says."""

import time
from collections.abc import Callable

from starlette.datastructures import Headers

from mcp_server.access import Refusal
from proprietary.license_check.keygen import Keygen, KeygenUnreachableError

# Keygen is asked about a key at most this often.
CACHE_SECONDS = 5 * 60
# While Keygen is unreachable, a key valid this recently still works: never fail
# closed for a key that was valid this morning.
GRACE_SECONDS = 24 * 3600

MISSING = Refusal(401, "missing_license")
UNAVAILABLE = Refusal(503, "license_service_unavailable")
_REFUSALS = {
    "EXPIRED": Refusal(403, "expired"),
    "SUSPENDED": Refusal(403, "revoked"),
    "BANNED": Refusal(403, "revoked"),
}


class LicenseAccess:
    def __init__(
        self, keygen: Keygen | None = None, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._keygen = keygen or Keygen()
        self._clock = clock
        self._checked: dict[str, tuple[Refusal | None, float]] = {}
        self._valid_at: dict[str, float] = {}

    async def refusal(self, headers: Headers) -> Refusal | None:
        key = _license_key(headers.get("authorization", ""))
        if not key:
            return MISSING
        now = self._clock()
        cached = self._checked.get(key)
        if cached is not None and now - cached[1] < CACHE_SECONDS:
            return cached[0]
        try:
            code = await self._keygen.validation_code(key)
        except KeygenUnreachableError:
            valid_at = self._valid_at.get(key)
            if valid_at is not None and now - valid_at < GRACE_SECONDS:
                return None
            return UNAVAILABLE
        refusal = (
            None if code == "VALID" else _REFUSALS.get(code, Refusal(403, "invalid"))
        )
        if refusal is None:
            self._valid_at[key] = now
        self._checked[key] = (refusal, now)
        return refusal


def _license_key(authorization: str) -> str:
    scheme, _, key = authorization.partition(" ")
    return key.strip() if scheme.lower() == "license" else ""
