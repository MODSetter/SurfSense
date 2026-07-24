import pytest

from app.config.embedding_settings import (
    build_embedding_kwargs,
    resolve_embedding_base_url,
)

pytestmark = pytest.mark.unit


def test_resolve_embedding_base_url_prefers_generic_value() -> None:
    environ = {
        "EMBEDDING_BASE_URL": " http://embed-host:11434 ",
        "OLLAMA_EMBEDDING_BASE_URL": "http://ollama-embed:11434",
    }

    assert resolve_embedding_base_url(environ) == "http://embed-host:11434"


def test_resolve_embedding_base_url_falls_back_to_ollama_specific_value() -> None:
    environ = {
        "EMBEDDING_BASE_URL": " ",
        "OLLAMA_EMBEDDING_BASE_URL": "http://ollama-embed:11434",
    }

    assert resolve_embedding_base_url(environ) == "http://ollama-embed:11434"


def test_build_embedding_kwargs_maps_base_url_to_litellm_api_base() -> None:
    kwargs = build_embedding_kwargs(
        {"EMBEDDING_BASE_URL": "http://host.docker.internal:11435"},
        embedding_model="litellm://ollama/nomic-embed-text",
    )

    assert kwargs == {"api_base": "http://host.docker.internal:11435"}


def test_build_embedding_kwargs_does_not_leak_api_base_to_other_providers() -> None:
    kwargs = build_embedding_kwargs(
        {"EMBEDDING_BASE_URL": "http://host.docker.internal:11435"},
        embedding_model="cohere://embed-english-light-v3.0",
    )

    assert kwargs == {}


def test_build_embedding_kwargs_preserves_azure_settings() -> None:
    kwargs = build_embedding_kwargs(
        {
            "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
            "AZURE_OPENAI_API_KEY": "test-key",
        },
        embedding_model="azure_openai://text-embedding-3-small",
    )

    assert kwargs == {
        "azure_endpoint": "https://example.openai.azure.com",
        "azure_api_key": "test-key",
    }


def test_build_embedding_kwargs_combines_litellm_and_azure_env_when_set() -> None:
    kwargs = build_embedding_kwargs(
        {
            "EMBEDDING_BASE_URL": "http://host.docker.internal:4000/v1",
            "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
            "AZURE_OPENAI_API_KEY": "test-key",
        },
        embedding_model="litellm://openai/text-embedding-3-small",
    )

    assert kwargs == {
        "api_base": "http://host.docker.internal:4000/v1",
        "azure_endpoint": "https://example.openai.azure.com",
        "azure_api_key": "test-key",
    }
