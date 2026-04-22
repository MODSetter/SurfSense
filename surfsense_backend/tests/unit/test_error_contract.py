"""Unit tests for the structured error response contract.

Validates that:
- Global exception handlers produce the backward-compatible error envelope.
- 5xx responses never leak raw internal exception text.
- X-Request-ID is propagated correctly.
- SurfSenseError, HTTPException, validation, and unhandled exceptions all
  use the same response shape.
"""

from __future__ import annotations

import json

import pytest
from fastapi import HTTPException
from starlette.testclient import TestClient

from app.exceptions import (
    GENERIC_5XX_MESSAGE,
    ISSUES_URL,
    ConfigurationError,
    ConnectorError,
    DatabaseError,
    ExternalServiceError,
    ForbiddenError,
    NotFoundError,
    SurfSenseError,
    ValidationError,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers - lightweight FastAPI app that re-uses the real global handlers
# ---------------------------------------------------------------------------


def _make_test_app():
    """Build a minimal FastAPI app with the same handlers as the real one."""
    from fastapi import FastAPI
    from fastapi.exceptions import RequestValidationError
    from pydantic import BaseModel

    from app.app import (
        RequestIDMiddleware,
        _http_exception_handler,
        _surfsense_error_handler,
        _unhandled_exception_handler,
        _validation_error_handler,
    )

    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    app.add_exception_handler(SurfSenseError, _surfsense_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(HTTPException, _http_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)

    @app.get("/ok")
    async def ok():
        return {"status": "ok"}

    @app.get("/http-400")
    async def raise_http_400():
        raise HTTPException(status_code=400, detail="Bad input")

    @app.get("/http-500")
    async def raise_http_500():
        raise HTTPException(status_code=500, detail="secret db password leaked")

    @app.get("/http-503")
    async def raise_http_503():
        raise HTTPException(
            status_code=503,
            detail="Page purchases are temporarily unavailable.",
        )

    @app.get("/http-502")
    async def raise_http_502():
        raise HTTPException(
            status_code=502,
            detail="Unable to create Stripe checkout session.",
        )

    @app.get("/surfsense-connector")
    async def raise_connector():
        raise ConnectorError("GitHub API returned 401")

    @app.get("/surfsense-notfound")
    async def raise_notfound():
        raise NotFoundError("Document #42 was not found")

    @app.get("/surfsense-forbidden")
    async def raise_forbidden():
        raise ForbiddenError()

    @app.get("/surfsense-config")
    async def raise_config():
        raise ConfigurationError()

    @app.get("/surfsense-db")
    async def raise_db():
        raise DatabaseError()

    @app.get("/surfsense-external")
    async def raise_external():
        raise ExternalServiceError()

    @app.get("/surfsense-validation")
    async def raise_validation():
        raise ValidationError("Email is invalid")

    @app.get("/unhandled")
    async def raise_unhandled():
        raise RuntimeError("should never reach the client")

    class Item(BaseModel):
        name: str
        count: int

    @app.post("/validated")
    async def validated(item: Item):
        return item.model_dump()

    return app


@pytest.fixture(scope="module")
def client():
    app = _make_test_app()
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Envelope shape validation
# ---------------------------------------------------------------------------


def _assert_envelope(resp, expected_status: int):
    """Every error response MUST contain the standard envelope."""
    assert resp.status_code == expected_status
    body = resp.json()
    assert "error" in body, f"Missing 'error' key: {body}"
    assert "detail" in body, f"Missing legacy 'detail' key: {body}"

    err = body["error"]
    assert isinstance(err["code"], str) and len(err["code"]) > 0
    assert isinstance(err["message"], str) and len(err["message"]) > 0
    assert err["status"] == expected_status
    assert isinstance(err["request_id"], str) and len(err["request_id"]) > 0
    assert "timestamp" in err
    assert err["report_url"] == ISSUES_URL

    # Legacy compat: detail mirrors message
    assert body["detail"] == err["message"]

    return body


# ---------------------------------------------------------------------------
# X-Request-ID propagation
# ---------------------------------------------------------------------------


class TestRequestID:
    def test_generated_when_missing(self, client):
        resp = client.get("/ok")
        assert "X-Request-ID" in resp.headers
        assert resp.headers["X-Request-ID"].startswith("req_")

    def test_echoed_when_provided(self, client):
        resp = client.get("/ok", headers={"X-Request-ID": "my-trace-123"})
        assert resp.headers["X-Request-ID"] == "my-trace-123"

    def test_present_in_error_response_body(self, client):
        resp = client.get("/http-400", headers={"X-Request-ID": "trace-abc"})
        body = _assert_envelope(resp, 400)
        assert body["error"]["request_id"] == "trace-abc"


# ---------------------------------------------------------------------------
# HTTPException handling
# ---------------------------------------------------------------------------


class TestHTTPExceptionHandler:
    def test_400_preserves_detail(self, client):
        body = _assert_envelope(client.get("/http-400"), 400)
        assert body["error"]["message"] == "Bad input"
        assert body["error"]["code"] == "BAD_REQUEST"

    def test_500_sanitizes_detail(self, client):
        body = _assert_envelope(client.get("/http-500"), 500)
        assert "secret" not in body["error"]["message"]
        assert "password" not in body["error"]["message"]
        assert body["error"]["message"] == GENERIC_5XX_MESSAGE
        assert body["error"]["code"] == "INTERNAL_ERROR"

    def test_503_preserves_detail(self, client):
        # Intentional 503s (e.g. feature flag off) must surface the developer
        # message so the frontend can render actionable copy.
        body = _assert_envelope(client.get("/http-503"), 503)
        assert body["error"]["message"] == "Page purchases are temporarily unavailable."
        assert body["error"]["message"] != GENERIC_5XX_MESSAGE

    def test_502_preserves_detail(self, client):
        body = _assert_envelope(client.get("/http-502"), 502)
        assert body["error"]["message"] == "Unable to create Stripe checkout session."
        assert body["error"]["message"] != GENERIC_5XX_MESSAGE


# ---------------------------------------------------------------------------
# SurfSenseError hierarchy
# ---------------------------------------------------------------------------


class TestSurfSenseErrorHandler:
    def test_connector_error(self, client):
        body = _assert_envelope(client.get("/surfsense-connector"), 502)
        assert body["error"]["code"] == "CONNECTOR_ERROR"
        assert "GitHub" in body["error"]["message"]

    def test_not_found_error(self, client):
        body = _assert_envelope(client.get("/surfsense-notfound"), 404)
        assert body["error"]["code"] == "NOT_FOUND"

    def test_forbidden_error(self, client):
        body = _assert_envelope(client.get("/surfsense-forbidden"), 403)
        assert body["error"]["code"] == "FORBIDDEN"

    def test_configuration_error(self, client):
        body = _assert_envelope(client.get("/surfsense-config"), 500)
        assert body["error"]["code"] == "CONFIGURATION_ERROR"

    def test_database_error(self, client):
        body = _assert_envelope(client.get("/surfsense-db"), 500)
        assert body["error"]["code"] == "DATABASE_ERROR"

    def test_external_service_error(self, client):
        body = _assert_envelope(client.get("/surfsense-external"), 502)
        assert body["error"]["code"] == "EXTERNAL_SERVICE_ERROR"

    def test_validation_error_custom(self, client):
        body = _assert_envelope(client.get("/surfsense-validation"), 422)
        assert body["error"]["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# Unhandled exception (catch-all)
# ---------------------------------------------------------------------------


class TestUnhandledException:
    def test_returns_500_generic_message(self, client):
        body = _assert_envelope(client.get("/unhandled"), 500)
        assert body["error"]["code"] == "INTERNAL_ERROR"
        assert body["error"]["message"] == GENERIC_5XX_MESSAGE
        assert "should never reach" not in json.dumps(body)


# ---------------------------------------------------------------------------
# RequestValidationError (pydantic / FastAPI)
# ---------------------------------------------------------------------------


class TestValidationErrorHandler:
    def test_missing_fields(self, client):
        resp = client.post("/validated", json={})
        body = _assert_envelope(resp, 422)
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert "required" in body["error"]["message"].lower()

    def test_wrong_type(self, client):
        resp = client.post("/validated", json={"name": "test", "count": "not-a-number"})
        body = _assert_envelope(resp, 422)
        assert body["error"]["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# SurfSenseError class hierarchy unit tests
# ---------------------------------------------------------------------------


class TestSurfSenseErrorClasses:
    def test_base_defaults(self):
        err = SurfSenseError()
        assert err.code == "INTERNAL_ERROR"
        assert err.status_code == 500
        assert err.safe_for_client is True

    def test_connector_error(self):
        err = ConnectorError("fail")
        assert err.code == "CONNECTOR_ERROR"
        assert err.status_code == 502

    def test_database_error(self):
        err = DatabaseError()
        assert err.status_code == 500

    def test_not_found_error(self):
        err = NotFoundError()
        assert err.status_code == 404

    def test_forbidden_error(self):
        err = ForbiddenError()
        assert err.status_code == 403

    def test_custom_code(self):
        err = ConnectorError("x", code="GITHUB_TOKEN_EXPIRED")
        assert err.code == "GITHUB_TOKEN_EXPIRED"
