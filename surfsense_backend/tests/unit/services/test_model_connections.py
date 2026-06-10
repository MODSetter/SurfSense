from app.services.global_model_catalog import materialize_global_model_catalog
from app.services.model_resolver import ensure_v1, to_litellm


def test_openai_compatible_resolver_normalizes_v1() -> None:
    model, kwargs = to_litellm(
        {
            "protocol": "OPENAI_COMPATIBLE",
            "base_url": "http://host.docker.internal:1234",
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
                "provider": "OPENROUTER",
                "model_name": "meta-llama/llama-3.1-8b-instruct:free",
                "api_key": "sk-global-secret",
                "billing_tier": "free",
                "anonymous_enabled": True,
                "seo_enabled": True,
                "rpm": 10,
                "tpm": 1000,
            },
            {
                "id": -102,
                "name": "OpenRouter Premium",
                "provider": "OPENROUTER",
                "model_name": "anthropic/claude-sonnet-4",
                "api_key": "sk-global-secret",
                "billing_tier": "premium",
            },
        ],
        vision_configs=[],
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
