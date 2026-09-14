"""Export-only mode for the hosted wind-down.

The hosted service goes read-only at T-0 and its data is purged at T+30, so the
only thing left for a user to do is take their data out. This module owns the
flag that says so and the middleware that enforces it.

Two properties matter more than anything else here:

* **Self-hosters run this same code forever with the flag unset.** Every path
  through this module has to be a no-op in that case, which is why the flag is
  checked before anything else and defaults to off.
* **Signing in has to keep working.** Export is behind a session, so blocking
  authentication would lock people out of the one action still available and
  make the 30-day window meaningless.

Spec: ``plans/community-local/00d-pivot-plan.md`` (B7, the export-only switch).
"""

from __future__ import annotations

import os

from starlette import status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# Contract 4 documents the flag as ``SUNSET_MODE=1``; the rest of this codebase
# spells booleans ``TRUE``. Both are accepted because this switch is thrown
# once, under time pressure, and a spelling that quietly reads as false would
# leave the service running as normal with nothing to show it had failed.
_TRUTHY = frozenset({"1", "true", "yes", "on"})

_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Everything under ``/auth`` keeps working: a user cannot export without
# signing in, and the legacy desktop client authenticates through
# ``/auth/desktop/*``. Registration is the one exception -- the service is
# winding down, so there is nobody new to sign up.
_ALLOWED_PREFIXES = (
    "/auth/",
    "/api/v1/license/",
    "/api/v1/stripe/webhook",
)
_BLOCKED_PATHS = frozenset({"/auth/register"})

_DETAIL = (
    "SurfSense is export-only while the hosted service winds down. "
    "Your data is still available to export."
)


def is_sunset_mode() -> bool:
    """Whether the hosted service is winding down.

    Read from the environment on every call rather than through ``config``,
    which resolves at import: contract 4 requires that flipping the flag take
    effect without a deploy.
    """
    return os.getenv("SUNSET_MODE", "").strip().lower() in _TRUTHY


def sunset_url() -> str:
    """Where sunset clients are sent. Legacy clients default to the same URL."""
    return os.environ.get("SUNSET_URL", "https://surfsense.com/sunset")


def _is_allowed(path: str) -> bool:
    if path in _BLOCKED_PATHS:
        return False
    return path.startswith(_ALLOWED_PREFIXES)


class SunsetWriteBlockMiddleware(BaseHTTPMiddleware):
    """Refuse writes while the hosted service is export-only.

    Reads stay open because export is a ``GET``; that is what makes this a
    method check rather than a list of every route that mutates something.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        # Checked first and cheapest: this is the branch self-hosters and the
        # pre-sunset hosted service always take.
        if not is_sunset_mode():
            return await call_next(request)

        if request.method not in _UNSAFE_METHODS:
            return await call_next(request)

        if _is_allowed(request.url.path):
            return await call_next(request)

        return JSONResponse(
            {"detail": _DETAIL},
            status_code=status.HTTP_410_GONE,
        )
