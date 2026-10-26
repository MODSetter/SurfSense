"""A paid plugin's access: the request's `License <key>`, checked with Keygen as contract 2 says."""

import asyncio
import logging
import time
from collections.abc import Callable

from starlette.datastructures import Headers

from mcp_server.access import Refusal, checked_license
from proprietary.license_check.keygen import Keygen, KeygenUnreachableError

logger = logging.getLogger(__name__)

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
    """Each key's last answer, kept for CACHE_SECONDS.

    After that a VALID key still passes at once while Keygen is asked again in the
    background, for up to GRACE_SECONDS since it was last valid; a refused key waits
    for Keygen's new answer. Keygen is asked about a key once at a time, however
    many requests carry it. Each key's license id, from the same answer, is set as
    `checked_license` for the request.
    """

    def __init__(
        self, keygen: Keygen | None = None, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._keygen = keygen or Keygen()
        self._clock = clock
        self._checked: dict[str, tuple[Refusal | None, float]] = {}
        self._valid_at: dict[str, float] = {}
        self._license_ids: dict[str, str] = {}
        # The check of each key that is under way, shared by every request for it.
        self._asking: dict[str, asyncio.Task[str | None]] = {}

    async def refusal(self, headers: Headers) -> Refusal | None:
        key = _license_key(headers.get("authorization", ""))
        refusal = await self._refusal_of(key) if key else MISSING
        checked_license.set(self._license_ids.get(key))
        return refusal

    async def _refusal_of(self, key: str) -> Refusal | None:
        now = self._clock()
        cached = self._checked.get(key)
        if cached is not None:
            refusal, checked_at = cached
            if now - checked_at < CACHE_SECONDS:
                return refusal
            if refusal is None and now - checked_at < GRACE_SECONDS:
                # Stale but valid: answer now, ask Keygen for the next request.
                self._ask(key)
                return None
        # Shielded: one request giving up must not end the check the others wait on.
        code = await asyncio.shield(self._ask(key))
        if code is None:
            valid_at = self._valid_at.get(key)
            if valid_at is not None and now - valid_at < GRACE_SECONDS:
                return None
            return UNAVAILABLE
        return _refusal(code)

    async def settled(self) -> None:
        """Wait for every check under way, as a test does before reading Keygen's log."""
        while self._asking:
            await asyncio.gather(*self._asking.values(), return_exceptions=True)

    def _ask(self, key: str) -> asyncio.Task[str | None]:
        """The check of `key` under way, or a new one."""
        task = self._asking.get(key)
        # A check started on another loop, as a finished test's, cannot be awaited here.
        if task is None or task.get_loop() is not asyncio.get_running_loop():
            task = asyncio.create_task(self._asked(key))
            self._asking[key] = task
            task.add_done_callback(lambda done: self._done(key, done))
        return task

    def _done(self, key: str, task: asyncio.Task[str | None]) -> None:
        if self._asking.get(key) is task:
            del self._asking[key]
        if not task.cancelled() and task.exception() is not None:
            # Retrieved here too, so a check no request awaited is still logged.
            logger.warning("[license] checking a key failed: %r", task.exception())

    async def _asked(self, key: str) -> str | None:
        """Keygen's code for `key`, kept as its answer, or None when Keygen is unreachable."""
        asked_at = self._clock()
        try:
            validation = await self._keygen.validation(key)
        except KeygenUnreachableError:
            return None
        if validation.license_id:
            self._license_ids[key] = validation.license_id
        else:
            self._license_ids.pop(key, None)
        code = validation.code
        refusal = _refusal(code)
        if refusal is None:
            self._valid_at[key] = asked_at
        else:
            # A refusal ends the grace: an expired key must not pass while Keygen is down.
            self._valid_at.pop(key, None)
        self._checked[key] = (refusal, asked_at)
        return code


_shared: dict[Keygen, LicenseAccess] = {}


def shared_access() -> LicenseAccess:
    """The process's one LicenseAccess for Keygen's settings in the environment.

    Every paid plugin shares it, so a key is asked about once for all of them.
    Settings that differ, as tests give, get their own.
    """
    keygen = Keygen()
    access = _shared.get(keygen)
    if access is None:
        access = _shared[keygen] = LicenseAccess(keygen)
    return access


def _refusal(code: str) -> Refusal | None:
    return None if code == "VALID" else _REFUSALS.get(code, Refusal(403, "invalid"))


def _license_key(authorization: str) -> str:
    scheme, _, key = authorization.partition(" ")
    return key.strip() if scheme.lower() == "license" else ""
