from types import SimpleNamespace

import httpx
import pytest

from app.routes.model_connections_routes import _apply_model_facts
from app.services import model_connection_service
from app.services.context_admission import SURFSENSE_UNKNOWN_MODEL_MAX_INPUT_TOKENS
from app.services.global_model_catalog import materialize_global_model_catalog
from app.services.model_connection_service import (
    ModelDiscoveryError,
    _discovery_error_message,
    _model_test_error,
    _ollama_seed_budget,
    derive_capabilities,
    discover_models,
    verify_connection,
)
from app.services.model_resolver import strip_version_suffix, to_litellm


def _facts(max_input_tokens: int | None) -> dict:
    return {
        "supports_chat": True,
        "max_input_tokens": max_input_tokens,
        "supports_image_input": False,
        "supports_tools": True,
        "supports_image_generation": False,
    }


def test_rediscovery_preserves_stored_context_limit() -> None:
    """A stored limit is written once: rediscovery must not clobber it."""
    model = SimpleNamespace(catalog={}, max_input_tokens=8_192)

    _apply_model_facts(model, _facts(131_072))

    assert model.max_input_tokens == 8_192


def test_discovery_seeds_context_limit_when_unset() -> None:
    model = SimpleNamespace(catalog={}, max_input_tokens=None)

    _apply_model_facts(model, _facts(131_072))

    assert model.max_input_tokens == 131_072


def _ollama_conn() -> SimpleNamespace:
    return SimpleNamespace(
        provider="ollama_chat",
        base_url="http://host.docker.internal:11434",
        api_key=None,
        extra={},
    )


def test_ollama_seed_budget_takes_modelfile_num_ctx_verbatim() -> None:
    """A Modelfile ``num_ctx`` is a human's statement about this deployment --
    the size Ollama will actually run at -- so it is the one discovered number
    trusted above the generic fallback."""
    assert (
        _ollama_seed_budget(
            {
                "parameters": "top_p 0.95\nnum_ctx 64000\ntemperature 1",
                "model_info": {
                    "general.architecture": "gemma4",
                    "gemma4.context_length": 262_144,
                },
            }
        )
        == 64_000
    )


def test_ollama_seed_budget_caps_the_architecture_maximum() -> None:
    """The architecture maximum describes the weights, not the host. Ollama
    sizes the context from free memory at load time, so a 262k-capable model
    routinely runs in a far smaller window; budgeting the maximum would
    overflow every turn."""
    assert (
        _ollama_seed_budget(
            {
                "parameters": "top_p 0.95\ntemperature 1",
                "model_info": {
                    "general.architecture": "gemma4",
                    "gemma4.context_length": 262_144,
                },
                "details": {"family": "gemma4", "quantization_level": "Q4_K_M"},
            }
        )
        == SURFSENSE_UNKNOWN_MODEL_MAX_INPUT_TOKENS
    )


def test_ollama_seed_budget_pins_a_window_under_the_fallback() -> None:
    """The direction the cap must not lose: newer Ollama reports context_length
    in /api/tags ``details``, and a model whose window is smaller than the
    generic fallback would otherwise be over-budgeted at 32k."""
    assert _ollama_seed_budget({"details": {"context_length": 4_096}}) == 4_096


def test_ollama_seed_budget_returns_none_when_unreported() -> None:
    assert _ollama_seed_budget({}) is None
    assert _ollama_seed_budget({"details": {"context_length": 0}}) is None


def test_derive_capabilities_seeds_a_small_window_verbatim() -> None:
    facts = derive_capabilities(
        _ollama_conn(),
        "llama2:7b",
        {
            "capabilities": ["completion", "tools", "vision"],
            "model_info": {
                "general.architecture": "llama",
                "llama.context_length": 4_096,
            },
        },
    )

    assert facts["max_input_tokens"] == 4_096
    assert facts["supports_tools"] is True
    assert facts["supports_image_input"] is True


@pytest.mark.asyncio
async def test_ollama_discovery_merges_details_from_both_endpoints(
    monkeypatch,
) -> None:
    """/api/tags and /api/show both return ``details`` with different fields. A
    shallow update would drop the context_length only /api/tags reports."""

    class FakeAsyncClient:
        def __init__(self, **_kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args) -> None:
            pass

        async def get(self, url: str, **_kwargs) -> httpx.Response:
            return httpx.Response(
                200,
                request=httpx.Request("GET", url),
                json={
                    "models": [
                        {
                            "model": "gemma4:12b",
                            "name": "gemma4:12b",
                            "details": {
                                "family": "gemma4",
                                "context_length": 262_144,
                                "embedding_length": 3_840,
                            },
                        }
                    ]
                },
            )

        async def post(self, url: str, **_kwargs) -> httpx.Response:
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={
                    "details": {
                        "family": "gemma4",
                        "quantization_level": "Q4_K_M",
                    },
                    "model_info": {"general.architecture": "gemma4"},
                    "capabilities": ["completion"],
                },
            )

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    results = await model_connection_service._ollama_tags_then_show(_ollama_conn())

    details = results[0]["metadata"]["details"]
    assert details["context_length"] == 262_144
    assert details["embedding_length"] == 3_840
    assert details["quantization_level"] == "Q4_K_M"
    # The reported maximum survives in the metadata the UI reads, while the
    # seeded budget stays at the fallback the host is likely to have allocated.
    assert results[0]["max_input_tokens"] == SURFSENSE_UNKNOWN_MODEL_MAX_INPUT_TOKENS


def test_anthropic_resolver_strips_trailing_v1_from_api_base() -> None:
    # LiteLLM's Anthropic handler appends ``/v1/messages``; a base URL ending in
    # ``/v1`` (the frontend default) would otherwise yield ``/v1/v1/messages``.
    model, kwargs = to_litellm(
        {
            "provider": "anthropic",
            "base_url": "https://api.anthropic.com/v1",
            "api_key": "sk-ant-test",
            "extra": {},
        },
        "claude-opus-4-8",
    )

    assert model == "anthropic/claude-opus-4-8"
    assert kwargs["api_base"] == "https://api.anthropic.com"


def test_anthropic_resolver_keeps_root_api_base() -> None:
    _model, kwargs = to_litellm(
        {
            "provider": "anthropic",
            "base_url": "https://api.anthropic.com",
            "api_key": "sk-ant-test",
            "extra": {},
        },
        "claude-opus-4-8",
    )

    assert kwargs["api_base"] == "https://api.anthropic.com"


def test_strip_version_suffix() -> None:
    assert strip_version_suffix("https://api.anthropic.com/v1") == (
        "https://api.anthropic.com"
    )
    assert strip_version_suffix("https://api.anthropic.com/v1/") == (
        "https://api.anthropic.com"
    )
    assert strip_version_suffix("https://api.anthropic.com") == (
        "https://api.anthropic.com"
    )
    assert strip_version_suffix(None) is None


def test_openai_compatible_resolver_uses_explicit_api_base() -> None:
    model, kwargs = to_litellm(
        {
            "protocol": "OPENAI_COMPATIBLE",
            "provider": "openai",
            "base_url": "http://host.docker.internal:1234/v1",
            "api_key": "local-key",
            "extra": {},
        },
        "qwen/qwen3",
    )

    assert model == "openai/qwen/qwen3"
    assert kwargs["api_base"] == "http://host.docker.internal:1234/v1"
    assert kwargs["api_key"] == "local-key"


def test_openai_compatible_resolver_uses_base_url_verbatim() -> None:
    # A bare host is NOT rewritten to append ``/v1``.
    _model, kwargs = to_litellm(
        {
            "provider": "openai_compatible",
            "base_url": "https://api.example.com",
            "api_key": "ex-key",
            "extra": {},
        },
        "some-model",
    )

    assert kwargs["api_base"] == "https://api.example.com"


def test_openai_compatible_resolver_preserves_custom_path() -> None:
    # Custom (non-/v1) paths survive verbatim, covering the old ``_raw`` case.
    _model, kwargs = to_litellm(
        {
            "provider": "openai_compatible",
            "base_url": "https://ark.cn-beijing.volces.com/api/v3/",
            "api_key": "ark-key",
            "extra": {},
        },
        "ep-20260101000000-test",
    )

    assert kwargs["api_base"] == "https://ark.cn-beijing.volces.com/api/v3"


def test_lm_studio_resolver_supplies_dummy_api_key_when_empty() -> None:
    model, kwargs = to_litellm(
        {
            "provider": "lm_studio",
            "base_url": "http://host.docker.internal:1234/v1",
            "api_key": None,
            "extra": {},
        },
        "tinyllama-1.1b-chat-v0.6",
    )

    assert model == "openai/tinyllama-1.1b-chat-v0.6"
    assert kwargs["api_base"] == "http://host.docker.internal:1234/v1"
    assert kwargs["api_key"] == "not-needed"


def test_openai_compatible_raw_resolver_does_not_append_v1() -> None:
    model, kwargs = to_litellm(
        {
            "provider": "openai_compatible_raw",
            "base_url": "https://ark.cn-beijing.volces.com/api/v3",
            "api_key": "ark-key",
            "extra": {},
        },
        "ep-20260101000000-test",
    )

    assert model == "openai/ep-20260101000000-test"
    assert kwargs["api_base"] == "https://ark.cn-beijing.volces.com/api/v3"
    assert kwargs["api_key"] == "ark-key"


def test_ollama_resolver_uses_native_api_base() -> None:
    model, kwargs = to_litellm(
        {
            "protocol": "OLLAMA",
            "provider": "ollama_chat",
            "base_url": "http://host.docker.internal:11434",
            "api_key": None,
            "extra": {},
        },
        "llama3.2",
    )

    assert model == "ollama_chat/llama3.2"
    assert kwargs["api_base"] == "http://host.docker.internal:11434"


def test_global_materialization_preserves_tier_and_keeps_key_server_side() -> None:
    connections, models = materialize_global_model_catalog(
        chat_configs=[
            {
                "id": -101,
                "name": "OpenRouter Free",
                "litellm_provider": "openrouter",
                "model_name": "meta-llama/llama-3.1-8b-instruct:free",
                "api_key": "sk-global-secret",
                "api_base": "https://openrouter.ai/api/v1",
                "billing_tier": "free",
                "anonymous_enabled": True,
                "seo_enabled": True,
                "rpm": 10,
                "tpm": 1000,
            },
            {
                "id": -102,
                "name": "OpenRouter Premium",
                "litellm_provider": "openrouter",
                "model_name": "anthropic/claude-sonnet-4",
                "api_key": "sk-global-secret",
                "api_base": "https://openrouter.ai/api/v1",
                "billing_tier": "premium",
            },
        ],
        image_configs=[],
    )

    assert len(connections) == 1
    assert connections[0]["api_key"] == "sk-global-secret"
    assert {model["billing_tier"] for model in models} == {"free", "premium"}
    assert models[0]["catalog"]["anonymous_enabled"] is True
    assert models[0]["catalog"]["rpm"] == 10

    public_connections = [
        {key: value for key, value in connection.items() if key != "api_key"}
        for connection in connections
    ]
    assert "sk-" not in repr(public_connections)


def test_discovery_404_message_points_at_base_url_and_echoes_url() -> None:
    request = httpx.Request("GET", "http://host.docker.internal:1234/models")
    exc = httpx.HTTPStatusError(
        "404", request=request, response=httpx.Response(404, request=request)
    )
    conn = SimpleNamespace(
        provider="openai_compatible", base_url="http://host.docker.internal:1234"
    )

    message = _discovery_error_message(conn, exc)

    assert "http://host.docker.internal:1234/models" in message
    assert "API Base URL" in message


def test_model_test_error_reports_http_response_as_provider_error() -> None:
    class APIConnectionError(Exception):
        status_code = 415

    conn = SimpleNamespace(
        provider="ollama_chat",
        base_url="http://host.docker.internal:11434",
    )

    result = _model_test_error(
        conn,
        "gemma4:12b",
        APIConnectionError("Unsupported Media Type"),
    )

    assert result.status == "PROVIDER_ERROR"
    assert result.ok is False
    assert "HTTP 415" in result.message
    assert "Unsupported Media Type" in result.message


def test_model_test_error_keeps_statusless_connection_failure_unreachable() -> None:
    class APIConnectionError(Exception):
        pass

    conn = SimpleNamespace(
        provider="ollama_chat",
        base_url="http://host.docker.internal:11434",
    )

    result = _model_test_error(
        conn,
        "gemma4:12b",
        APIConnectionError("Connection refused"),
    )

    assert result.status == "UNREACHABLE"
    assert result.ok is False


@pytest.mark.asyncio
async def test_verify_connection_reports_http_response_as_provider_error(
    monkeypatch,
) -> None:
    class FakeAsyncClient:
        def __init__(self, **_kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args) -> None:
            pass

        async def get(self, url: str, **_kwargs) -> httpx.Response:
            request = httpx.Request("GET", url)
            return httpx.Response(
                500,
                request=request,
                text="Provider failed",
            )

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    conn = SimpleNamespace(
        provider="openai_compatible",
        base_url="https://models.example.com/v1",
        api_key="test-key",
    )

    result = await verify_connection(conn)

    assert result.status == "PROVIDER_ERROR"
    assert result.ok is False
    assert "HTTP 500" in result.message
    assert "Provider failed" in result.message


@pytest.mark.asyncio
async def test_verify_lm_studio_reports_http_response_as_provider_error(
    monkeypatch,
) -> None:
    request = httpx.Request(
        "GET",
        "http://host.docker.internal:1234/api/v1/models",
    )
    response = httpx.Response(503, request=request, text="Server unavailable")

    async def failed_discovery(_conn) -> list[dict]:
        raise httpx.HTTPStatusError(
            "503",
            request=request,
            response=response,
        )

    monkeypatch.setattr(
        model_connection_service,
        "_discover_lm_studio_models",
        failed_discovery,
    )
    conn = SimpleNamespace(
        provider="lm_studio",
        base_url="http://host.docker.internal:1234/v1",
        api_key=None,
    )

    result = await verify_connection(conn)

    assert result.status == "PROVIDER_ERROR"
    assert result.ok is False
    assert "HTTP 503" in result.message
    assert "Server unavailable" in result.message


@pytest.mark.asyncio
async def test_discover_models_rejects_empty_discoverable_provider(
    monkeypatch,
) -> None:
    async def empty_ollama_models(_conn) -> list[dict]:
        return []

    monkeypatch.setattr(
        model_connection_service,
        "_ollama_tags_then_show",
        empty_ollama_models,
    )
    conn = SimpleNamespace(
        provider="ollama_chat",
        base_url="http://host.docker.internal:11434",
    )

    with pytest.raises(ModelDiscoveryError, match="No models found at"):
        await discover_models(conn)


@pytest.mark.asyncio
async def test_discover_models_allows_empty_static_provider(monkeypatch) -> None:
    monkeypatch.setattr(
        model_connection_service,
        "_litellm_static_models",
        lambda _conn: [],
    )
    conn = SimpleNamespace(provider="azure", base_url=None)

    assert await discover_models(conn) == []
