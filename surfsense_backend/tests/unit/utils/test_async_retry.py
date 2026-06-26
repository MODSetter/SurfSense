"""Tests for async_retry utilities."""

import httpx
import pytest

from app.connectors.exceptions import (
    ConnectorAPIError,
    ConnectorAuthError,
    ConnectorError,
    ConnectorRateLimitError,
    ConnectorTimeoutError,
)
from app.utils.async_retry import _is_retryable, raise_for_status

pytestmark = pytest.mark.unit


def make_response(
    status_code: int,
    *,
    headers: dict[str, str] | None = None,
    json_body=None,
    text_body: str = "",
):
    kwargs = {
        "status_code": status_code,
        "headers": headers,
        "request": httpx.Request("GET", "https://x"),
    }

    if json_body is not None:
        kwargs["json"] = json_body
    else:
        kwargs["text"] = text_body

    return httpx.Response(**kwargs)


def test_raise_for_status_does_not_raise_for_success():
    response = make_response(200)

    raise_for_status(response)


@pytest.mark.parametrize(
    ("retry_after_header", "expected"),
    [
        ("5", 5.0),
        (None, None),
        ("abc", None),
    ],
)
def test_raise_for_status_429(retry_after_header, expected):
    headers = {}
    if retry_after_header is not None:
        headers["Retry-After"] = retry_after_header

    response = make_response(
        429,
        headers=headers,
        json_body={"detail": "rate limited"},
    )

    with pytest.raises(ConnectorRateLimitError) as exc_info:
        raise_for_status(response)

    exc = exc_info.value
    assert exc.retry_after == expected
    assert exc.response_body == {"detail": "rate limited"}


@pytest.mark.parametrize("status_code", [401, 403])
def test_raise_for_status_auth_errors(status_code):
    response = make_response(
        status_code,
        json_body={"error": "unauthorized"},
    )

    with pytest.raises(ConnectorAuthError) as exc_info:
        raise_for_status(response)

    exc = exc_info.value
    assert exc.status_code == status_code
    assert exc.response_body == {"error": "unauthorized"}


def test_raise_for_status_gateway_timeout():
    response = make_response(
        504,
        json_body={"error": "timeout"},
    )

    with pytest.raises(ConnectorTimeoutError):
        raise_for_status(response)


@pytest.mark.parametrize("status_code", [500, 502])
def test_raise_for_status_server_errors(status_code):
    response = make_response(
        status_code,
        json_body={"error": "server"},
    )

    with pytest.raises(ConnectorAPIError) as exc_info:
        raise_for_status(response)

    assert exc_info.value.status_code == status_code


@pytest.mark.parametrize("status_code", [400, 404])
def test_raise_for_status_client_errors(status_code):
    response = make_response(
        status_code,
        json_body={"error": "client"},
    )

    with pytest.raises(ConnectorAPIError) as exc_info:
        raise_for_status(response)

    assert exc_info.value.status_code == status_code


def test_raise_for_status_uses_text_when_json_parsing_fails():
    response = make_response(
        500,
        text_body="Internal server error",
    )

    with pytest.raises(ConnectorAPIError) as exc_info:
        raise_for_status(response)

    assert exc_info.value.response_body == "Internal server error"


def test_connector_error_retryable_false():
    exc = ConnectorError("boom")

    assert _is_retryable(exc) is False


def test_rate_limit_error_is_retryable():
    exc = ConnectorRateLimitError()

    assert _is_retryable(exc) is True


def test_timeout_exception_is_retryable():
    exc = httpx.TimeoutException("timeout")

    assert _is_retryable(exc) is True


def test_connect_error_is_retryable():
    exc = httpx.ConnectError("connection failed")

    assert _is_retryable(exc) is True


def test_unrelated_exception_is_not_retryable():
    exc = ValueError("boom")

    assert _is_retryable(exc) is False
