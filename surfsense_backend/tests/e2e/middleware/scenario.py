"""X-E2E-Scenario middleware.

Reads the X-E2E-Scenario request header and pipes the value into a
ContextVar that the strict fakes consult to switch between happy-path
and error scenarios on a per-request basis.

Mounted by tests/e2e/run_backend.py only. Production never adds this
middleware, so production never reads the header.

Supported scenarios:
- "happy" (default): everything succeeds with deterministic fixtures.
- "denied": Composio.connected_accounts.initiate returns a redirect URL
  pointing at our callback with ?error=access_denied.
- "auth_expired": GOOGLEDRIVE_LIST_FILES returns an authentication
  failure that the route translates to connector.config.auth_expired.
- "duplicate": no special fake behavior; the duplicate path is exercised
  by running the OAuth flow twice with the same toolkit.
"""

from __future__ import annotations

from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

_scenario: ContextVar[str] = ContextVar("e2e_scenario", default="happy")


def current_scenario() -> str:
    """Return the active E2E scenario for the current request context."""
    return _scenario.get()


class ScenarioMiddleware(BaseHTTPMiddleware):
    """Reads X-E2E-Scenario and exposes it via a ContextVar.

    The header is also forwarded as state on the request so route
    handlers can branch if they ever need to (Composio routes do not).
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        value = request.headers.get("X-E2E-Scenario", "happy")
        token = _scenario.set(value)
        try:
            request.state.e2e_scenario = value
            return await call_next(request)
        finally:
            _scenario.reset(token)
