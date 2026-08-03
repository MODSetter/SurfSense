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


def test_adapter_classifies_runtime_out_of_memory() -> None:
    exc = RuntimeError(
        "llama runner process has terminated: "
        "ggml_backend_cuda_buffer_type_alloc_buffer: allocating 4096.00 MiB "
        "on device 0: cudaMalloc failed: out of memory"
    )

    adapted = adapt_llm_exception(exc)

    assert adapted.category is LLMErrorCategory.INSUFFICIENT_MEMORY
    # Retrying reloads the same model at the same size and fails the same way.
    assert adapted.retryable is False


def test_adapter_classifies_preflight_does_not_fit() -> None:
    """Ollama's ``ErrLoadRequiredFull``, raised before any allocation."""
    adapted = adapt_llm_exception(RuntimeError("unable to load full model on GPU"))

    assert adapted.category is LLMErrorCategory.INSUFFICIENT_MEMORY


def test_adapter_prefers_memory_over_context_when_both_appear() -> None:
    """The ordering guard: a failed KV cache reservation names the ``n_ctx`` it
    could not fit, and ``n_ctx`` is also a context-limit hint. Reading it as a
    context limit would tell the user to shrink a prompt that never ran."""
    exc = RuntimeError(
        "llama_init_from_model: failed to allocate KV cache for n_ctx = 262144"
    )

    adapted = adapt_llm_exception(exc)

    assert adapted.category is LLMErrorCategory.INSUFFICIENT_MEMORY


def test_adapter_keeps_unrelated_http_400_as_bad_request() -> None:
    adapted = adapt_llm_exception(RuntimeError('{"code":400,"type":"invalid_request"}'))

    assert adapted.category is LLMErrorCategory.BAD_REQUEST


def test_stream_classifier_maps_context_limit_to_stable_code() -> None:
    exc = RuntimeError('{"code":400,"type":"exceed_context_size_error","n_ctx":8192}')

    kind, code, severity, expected, message, diagnostic, extra = (
        classify_stream_exception(
            exc,
            flow_label="chat",
        )
    )

    assert kind == "model_context_limit"
    assert code == "MODEL_CONTEXT_LIMIT"
    assert severity == "warn"
    assert expected is True
    assert "too large" in message
    assert diagnostic == str(exc)
    assert extra == {
        "provider_error_category": "context_limit",
        "provider_status_code": 400,
        "provider_error_type": "exceed_context_size_error",
    }


def test_stream_classifier_maps_model_auth_to_stable_code() -> None:
    exc = RuntimeError(
        'litellm.AuthenticationError: OpenrouterException - {"error":{"message":"User not found.","code":401}}'
    )

    kind, code, severity, expected, message, diagnostic, extra = (
        classify_stream_exception(
            exc,
            flow_label="chat",
        )
    )

    assert kind == "model_auth_failed"
    assert code == "MODEL_AUTH_FAILED"
    assert severity == "warn"
    assert expected is True
    assert "API key" in message
    assert diagnostic == str(exc)
    assert extra == {
        "provider_error_category": "auth_failed",
        "provider_status_code": 401,
    }


def test_stream_classifier_maps_out_of_memory_to_stable_code() -> None:
    """A local runtime reports OOM as a 5xx, which lands in the unavailable
    group unless this classifies ahead of it -- and that group's copy tells the
    user to retry a load that cannot succeed until memory is freed."""
    exc = RuntimeError(
        'litellm.APIError: OllamaException - {"error":"model requires more '
        'system memory (14.2 GiB) than is available (7.8 GiB)"}'
    )

    kind, code, severity, expected, message, diagnostic, extra = (
        classify_stream_exception(exc, flow_label="chat")
    )

    assert kind == "model_out_of_memory"
    assert code == "MODEL_OUT_OF_MEMORY"
    assert severity == "warn"
    assert expected is True
    # Names a lever that works: our budget does not size the host's allocation,
    # so telling the user to lower it would not free a byte.
    assert "smaller model" in message
    assert diagnostic == str(exc)
    assert extra["provider_error_category"] == "insufficient_memory"


def test_stream_classifier_keeps_unknown_errors_generic() -> None:
    exc = RuntimeError("database exploded")

    kind, code, severity, expected, message, diagnostic, extra = (
        classify_stream_exception(
            exc,
            flow_label="chat",
        )
    )

    assert kind == "server_error"
    assert code == "SERVER_ERROR"
    assert severity == "error"
    assert expected is False
    assert message == "We couldn't complete this response right now. Please try again."
    assert diagnostic == "Error during chat: database exploded"
    assert extra is None
