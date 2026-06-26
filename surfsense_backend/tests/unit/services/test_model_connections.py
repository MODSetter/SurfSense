from app.services.global_model_catalog import materialize_global_model_catalog
from app.services.model_resolver import ensure_v1, strip_version_suffix, to_litellm


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
    assert ensure_v1("http://example.com/v1") == "http://example.com/v1"


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
