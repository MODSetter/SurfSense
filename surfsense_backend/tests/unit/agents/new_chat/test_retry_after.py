"""Tests for RetryAfterMiddleware Retry-After parsing and retry decision logic."""

from __future__ import annotations

import pytest

from app.agents.new_chat.middleware.retry_after import (
    RetryAfterMiddleware,
    _extract_retry_after_seconds,
    _is_non_retryable,
)

pytestmark = pytest.mark.unit


class _FakeResponse:
    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = headers


class _FakeRateLimit(Exception):
    def __init__(self, msg: str, headers: dict[str, str] | None = None) -> None:
        super().__init__(msg)
        if headers is not None:
            self.response = _FakeResponse(headers)


class TestExtractRetryAfter:
    def test_seconds_header(self) -> None:
        exc = _FakeRateLimit("rate", {"Retry-After": "30"})
        assert _extract_retry_after_seconds(exc) == 30.0

    def test_milliseconds_header_overrides_seconds(self) -> None:
        exc = _FakeRateLimit("rate", {"retry-after-ms": "1500"})
        assert _extract_retry_after_seconds(exc) == 1.5

    def test_case_insensitive(self) -> None:
        exc = _FakeRateLimit("rate", {"RETRY-AFTER": "12"})
        assert _extract_retry_after_seconds(exc) == 12.0

    def test_falls_back_to_message_regex(self) -> None:
        exc = Exception("Please retry after 7 seconds")
        assert _extract_retry_after_seconds(exc) == 7.0

    def test_returns_none_when_no_hint(self) -> None:
        exc = Exception("oops")
        assert _extract_retry_after_seconds(exc) is None

    def test_handles_missing_headers_attr(self) -> None:
        exc = ValueError("no headers")
        assert _extract_retry_after_seconds(exc) is None


class TestIsNonRetryable:
    @pytest.mark.parametrize(
        "name",
        ["ContextWindowExceededError", "AuthenticationError", "InvalidRequestError"],
    )
    def test_non_retryable_classes(self, name: str) -> None:
        cls = type(name, (Exception,), {})
        assert _is_non_retryable(cls("x")) is True

    def test_generic_exception_is_retryable(self) -> None:
        assert _is_non_retryable(RuntimeError("transient")) is False


class TestDelayCalculation:
    def test_takes_max_of_backoff_and_header(self) -> None:
        mw = RetryAfterMiddleware(max_retries=3, initial_delay=1.0, jitter=False)
        exc = _FakeRateLimit("rl", {"retry-after": "10"})
        delay = mw._delay_for_attempt(0, exc)
        assert delay == pytest.approx(10.0)

    def test_uses_backoff_when_no_header(self) -> None:
        mw = RetryAfterMiddleware(
            max_retries=3, initial_delay=2.0, backoff_factor=2.0, jitter=False
        )
        delay = mw._delay_for_attempt(2, RuntimeError("transient"))
        # 2 * 2^2 = 8
        assert delay == pytest.approx(8.0)

    def test_caps_at_max_delay(self) -> None:
        mw = RetryAfterMiddleware(
            max_retries=3,
            initial_delay=10.0,
            backoff_factor=10.0,
            max_delay=15.0,
            jitter=False,
        )
        delay = mw._delay_for_attempt(5, RuntimeError("x"))
        assert delay <= 15.0


class TestShouldRetry:
    def test_default_retries_generic(self) -> None:
        mw = RetryAfterMiddleware()
        assert mw._should_retry(RuntimeError("transient")) is True

    def test_default_skips_non_retryable(self) -> None:
        mw = RetryAfterMiddleware()
        cls = type("ContextWindowExceededError", (Exception,), {})
        assert mw._should_retry(cls("too big")) is False

    def test_custom_retry_on(self) -> None:
        mw = RetryAfterMiddleware(retry_on=lambda exc: isinstance(exc, ValueError))
        assert mw._should_retry(ValueError()) is True
        assert mw._should_retry(KeyError()) is False
