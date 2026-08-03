from __future__ import annotations

import pytest

from app.services.llm_error_adapter import LLMErrorCategory, adapt_llm_exception
from app.tasks.chat.streaming.errors.classifier import classify_stream_exception

pytestmark = pytest.mark.unit


def _exception_named(name: str, message: str) -> Exception:
    return type(name, (Exception,), {})(message)


def test_adapter_classifies_authentication_error_by_class_name() -> None:
    exc = _exception_named("AuthenticationError", "provider rejected credentials")

    adapted = adapt_llm_exception(exc)

    assert adapted.category is LLMErrorCategory.AUTH_FAILED
    assert adapted.retryable is False
    assert adapted.user_message == "LLM authentication failed. Check your API key."


def test_adapter_classifies_embedded_provider_401_payload() -> None:
    exc = RuntimeError(
        'litellm.AuthenticationError: OpenrouterException - {"error":{"message":"User not found.","code":401}}'
    )

    adapted = adapt_llm_exception(exc)

    assert adapted.category is LLMErrorCategory.AUTH_FAILED
    assert adapted.provider_status_code == 401


def test_adapter_preserves_rate_limit_classification() -> None:
    exc = RuntimeError('{"error":{"message":"Slow down","code":429}}')

    adapted = adapt_llm_exception(exc)

    assert adapted.category is LLMErrorCategory.RATE_LIMITED
    assert adapted.retryable is True


def test_adapter_prioritizes_lm_studio_context_type_over_http_400() -> None:
    exc = RuntimeError(
        '{"code":400,"type":"exceed_context_size_error",'
        '"n_prompt_tokens":14684,"n_ctx":8192}'
    )

    adapted = adapt_llm_exception(exc)

    assert adapted.category is LLMErrorCategory.CONTEXT_LIMIT
    assert adapted.retryable is False
    assert adapted.provider_status_code == 400
    assert adapted.provider_error_type == "exceed_context_size_error"


def test_adapter_finds_context_overflow_in_wrapped_cause() -> None:
    cause = RuntimeError(
        'LM Studio error: {"code":400,"type":"exceed_context_size_error"} trailing'
    )
    exc = _exception_named("MidStreamFallbackError", "provider unavailable")
    exc.__cause__ = cause

    adapted = adapt_llm_exception(exc)

    assert adapted.category is LLMErrorCategory.CONTEXT_LIMIT
    assert adapted.retryable is False
    assert adapted.provider_status_code == 400


def test_adapter_keeps_unrelated_http_400_as_bad_request() -> None:
    adapted = adapt_llm_exception(RuntimeError('{"code":400,"type":"invalid_request"}'))

    assert adapted.category is LLMErrorCategory.BAD_REQUEST


def test_stream_classifier_maps_context_limit_to_stable_code() -> None:
    exc = RuntimeError('{"code":400,"type":"exceed_context_size_error","n_ctx":8192}')

    kind, code, severity, expected, message, extra = classify_stream_exception(
        exc,
        flow_label="chat",
    )

    assert kind == "model_context_limit"
    assert code == "MODEL_CONTEXT_LIMIT"
    assert severity == "warn"
    assert expected is True
    assert "too large" in message
    assert extra == {
        "provider_error_category": "context_limit",
        "provider_status_code": 400,
        "provider_error_type": "exceed_context_size_error",
    }


def test_stream_classifier_maps_model_auth_to_stable_code() -> None:
    exc = RuntimeError(
        'litellm.AuthenticationError: OpenrouterException - {"error":{"message":"User not found.","code":401}}'
    )

    kind, code, severity, expected, message, extra = classify_stream_exception(
        exc,
        flow_label="chat",
    )

    assert kind == "model_auth_failed"
    assert code == "MODEL_AUTH_FAILED"
    assert severity == "warn"
    assert expected is True
    assert "API key" in message
    assert extra == {
        "provider_error_category": "auth_failed",
        "provider_status_code": 401,
    }


def test_stream_classifier_keeps_unknown_errors_generic() -> None:
    exc = RuntimeError("database exploded")

    kind, code, severity, expected, message, extra = classify_stream_exception(
        exc,
        flow_label="chat",
    )

    assert kind == "server_error"
    assert code == "SERVER_ERROR"
    assert severity == "error"
    assert expected is False
    assert message == "Error during chat: database exploded"
    assert extra is None
