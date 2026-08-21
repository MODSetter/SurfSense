"""Tests for RetryAfterMiddleware Retry-After parsing and retry decision logic."""

from __future__ import annotations

from collections.abc import Mapping

import httpx
import pytest
from litellm.exceptions import RateLimitError

from app.agents.chat.shared.middleware.retry_after import (
    RetryAfterMiddleware,
    _extract_retry_after_seconds,
    _is_non_retryable,
)

pytestmark = pytest.mark.unit


class _FakeResponse:
    def __init__(self, headers: Mapping[str, str]) -> None:
        self.headers = headers


class _FakeRateLimitError(Exception):
    def __init__(self, msg: str, headers: Mapping[str, str] | None = None) -> None:
        super().__init__(msg)
        if headers is not None:
            self.response = _FakeResponse(headers)


def _litellm_rate_limit_error(**headers: str) -> RateLimitError:
    """A rate-limit error shaped the way litellm actually raises one.

    ``RateLimitError.__init__`` rebuilds ``self.response`` as an
    ``httpx.Response``, so ``response.headers`` is always ``httpx.Headers``.
    """
    return RateLimitError(
        message="rate limited",
        llm_provider="openai",
        model="gpt-4o",
        response=httpx.Response(
            429,
            headers=headers,
            request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
        ),
    )


class TestExtractRetryAfter:
    def test_seconds_header(self) -> None:
        exc = _FakeRateLimitError("rate", {"Retry-After": "30"})
        assert _extract_retry_after_seconds(exc) == 30.0

    def test_milliseconds_header_overrides_seconds(self) -> None:
        exc = _FakeRateLimitError("rate", {"retry-after-ms": "1500"})
        assert _extract_retry_after_seconds(exc) == 1.5

    def test_case_insensitive(self) -> None:
        exc = _FakeRateLimitError("rate", {"RETRY-AFTER": "12"})
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

    def test_reads_headers_off_a_real_litellm_error(self) -> None:
        """The shape production actually raises: ``httpx.Headers``.

        The message carries no "retry after N", so this can only pass through
        the header branch.
        """
        exc = _litellm_rate_limit_error(**{"Retry-After": "45"})
        assert _extract_retry_after_seconds(exc) == 45.0

    def test_reads_milliseconds_off_a_real_litellm_error(self) -> None:
        exc = _litellm_rate_limit_error(**{"retry-after-ms": "1500"})
        assert _extract_retry_after_seconds(exc) == 1.5


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

    @pytest.mark.parametrize(
        "message",
        [
            "llama runner process has terminated: cudaMalloc failed: out of memory",
            "model requires more system memory (10.9 GiB) than is available",
        ],
    )
    def test_host_out_of_memory_is_not_retried(self, message: str) -> None:
        """Ollama surfaces an OOM as a generic API error, so a class-name test
        retried it -- after the scheduler had already shrunk the context and
        evicted other models to try to make it fit."""
        cls = type("APIError", (Exception,), {})
        assert _is_non_retryable(cls(message)) is True

    def test_context_overflow_without_a_telling_class_name(self) -> None:
        cls = type("APIError", (Exception,), {})
        exc = cls(
            "the prompt is longer than the context length currently available "
            "to the model"
        )
        assert _is_non_retryable(exc) is True


class TestDelayCalculation:
    def test_takes_max_of_backoff_and_header(self) -> None:
        mw = RetryAfterMiddleware(max_retries=3, initial_delay=1.0, jitter=False)
        exc = _FakeRateLimitError("rl", {"retry-after": "10"})
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

    def test_caps_a_header_delay_at_max_delay(self) -> None:
        """A provider hint is a hint, not a licence to hold the turn open.

        The retry loop runs inside the live chat turn, so an hour-long
        ``retry-after-ms`` would hold the SSE stream, the thread's busy lock
        and the DB session for that hour.
        """
        mw = RetryAfterMiddleware(
            max_retries=3, initial_delay=1.0, max_delay=30.0, jitter=False
        )
        exc = _litellm_rate_limit_error(**{"retry-after-ms": "3600000"})
        assert mw._delay_for_attempt(0, exc) == pytest.approx(30.0)


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
