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

