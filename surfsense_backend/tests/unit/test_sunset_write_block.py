"""The export-only switch: writes refused while the hosted service winds down.

Half of these tests are about the flag being ON. The other half exist because
self-hosters run this same code with the flag unset, forever, and a write-block
that misread its flag would 410 every install with nothing in the logs to say
why. That half is a launch gate in ``plans/community-local/00d-pivot-plan.md``:
"Compose stack with both flags unset behaves exactly as before."
"""

from __future__ import annotations

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.sunset import SunsetWriteBlockMiddleware, is_sunset_mode

pytestmark = pytest.mark.unit

# The paths under test are the real ones: /auth/jwt/login rather than
# /auth/login, because fastapi-users mounts the login routes under /auth/jwt
# and an allowlist written against the wrong spelling would match nothing and
# lock every user out of the export they came for.
_PATHS = (
    "/api/v1/documents",
    "/api/v1/searchspaces",
    "/auth/jwt/login",
    "/auth/jwt/refresh",
    "/auth/jwt/logout",
    "/auth/desktop/login",
    "/auth/desktop/session",
    "/auth/register",
    "/auth/forgot-password",
    "/auth/reset-password",
    "/api/v1/license/resend",
    "/api/v1/license/trial",
    "/api/v1/stripe/webhook",
    "/api/v1/export",
)


async def _ok(request):
    return JSONResponse({"reached": request.url.path})


@pytest.fixture
def client() -> TestClient:
    """A stand-in app carrying only the middleware under test.

    The real app would drag in auth, the database and a rate limiter, none of
    which this middleware consults -- it decides on method and path alone.
    """
    app = Starlette(
        routes=[
            Route(path, _ok, methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
            for path in _PATHS
        ]
    )
    app.add_middleware(SunsetWriteBlockMiddleware)
    return TestClient(app)


@pytest.fixture
def sunset_on(monkeypatch):
    monkeypatch.setenv("SUNSET_MODE", "1")


@pytest.fixture
def sunset_off(monkeypatch):
    monkeypatch.delenv("SUNSET_MODE", raising=False)


# --------------------------------------------------------------------------
# Self-hosters, and the hosted service before T-0
# --------------------------------------------------------------------------


@pytest.mark.parametrize("path", _PATHS)
@pytest.mark.parametrize("method", ["get", "post", "put", "patch", "delete"])
def test_nothing_is_blocked_while_the_flag_is_unset(client, sunset_off, path, method):
    """The launch gate: with the flag unset the stack behaves exactly as before."""
    response = getattr(client, method)(path)

    assert response.status_code == 200
    assert response.json()["reached"] == path


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off", "  "])
def test_a_flag_that_does_not_mean_yes_blocks_nothing(client, monkeypatch, value):
    """Anything short of an explicit yes leaves the service fully writable."""
    monkeypatch.setenv("SUNSET_MODE", value)

    assert client.post("/api/v1/documents").status_code == 200


def test_the_flag_is_read_per_request(client, monkeypatch):
    """Sunset is thrown by changing the environment, not by redeploying."""
    monkeypatch.delenv("SUNSET_MODE", raising=False)
    assert client.post("/api/v1/documents").status_code == 200

    monkeypatch.setenv("SUNSET_MODE", "1")
    assert client.post("/api/v1/documents").status_code == 410

    monkeypatch.delenv("SUNSET_MODE", raising=False)
    assert client.post("/api/v1/documents").status_code == 200


# --------------------------------------------------------------------------
# The hosted service from T-0
# --------------------------------------------------------------------------


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_writes_are_refused_with_410(client, sunset_on, method):
    response = getattr(client, method)("/api/v1/documents")

    assert response.status_code == 410
    assert "export" in response.json()["detail"].lower()


@pytest.mark.parametrize("path", _PATHS)
def test_reads_are_never_refused(client, sunset_on, path):
    """Export is a GET, which is what makes this a method check.

    If reads were blocked the 30-day window would have nothing in it.
    """
    assert client.get(path).status_code == 200


@pytest.mark.parametrize(
    "path",
    [
        "/auth/jwt/login",
        "/auth/jwt/refresh",
        "/auth/jwt/logout",
        "/auth/desktop/login",
        "/auth/desktop/session",
        "/auth/forgot-password",
        "/auth/reset-password",
    ],
)
def test_signing_in_keeps_working(client, sunset_on, path):
    """Export lives behind a session, so blocking auth would strand everyone.

    ``/auth/desktop/*`` matters twice over: it is how the legacy client that
    contract 4 redirects to ``/sunset`` authenticates in the first place.
    """
    assert client.post(path).status_code == 200


def test_new_signups_are_refused(client, sunset_on):
    """Nobody should be joining a service that is shutting down."""
    assert client.post("/auth/register").status_code == 410


@pytest.mark.parametrize(
    "path", ["/api/v1/license/resend", "/api/v1/license/trial", "/api/v1/stripe/webhook"]
)
def test_the_license_business_keeps_running(client, sunset_on, path):
    """Licences are what the company becomes; the webhook still has to fulfil."""
    assert client.post(path).status_code == 200


# --------------------------------------------------------------------------
# The flag itself
# --------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "True", "yes", "on"])
def test_every_documented_spelling_means_yes(monkeypatch, value):
    monkeypatch.setenv("SUNSET_MODE", value)

    assert is_sunset_mode() is True


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off", "  ", "1 "])
def test_anything_else_means_no(monkeypatch, value):
    monkeypatch.setenv("SUNSET_MODE", value)

    assert is_sunset_mode() is (value.strip() == "1")
