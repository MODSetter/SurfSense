import os
from collections.abc import Mapping

EMBEDDING_BASE_URL_ENV = "EMBEDDING_BASE_URL"
OLLAMA_EMBEDDING_BASE_URL_ENV = "OLLAMA_EMBEDDING_BASE_URL"


def _clean_env_value(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def resolve_embedding_base_url(environ: Mapping[str, str] | None = None) -> str | None:
    """Return the configured embedding endpoint, if any."""
    environ = os.environ if environ is None else environ
    return _clean_env_value(environ.get(EMBEDDING_BASE_URL_ENV)) or _clean_env_value(
        environ.get(OLLAMA_EMBEDDING_BASE_URL_ENV)
    )


def _supports_embedding_api_base(embedding_model: str | None) -> bool:
    return (embedding_model or "").startswith("litellm://")


def build_embedding_kwargs(
    environ: Mapping[str, str] | None = None,
    *,
    embedding_model: str | None = None,
) -> dict[str, str]:
    """Build keyword arguments for Chonkie's embedding provider."""
    environ = os.environ if environ is None else environ

    embedding_kwargs: dict[str, str] = {}
    embedding_base_url = resolve_embedding_base_url(environ)
    if embedding_base_url and _supports_embedding_api_base(embedding_model):
        embedding_kwargs["api_base"] = embedding_base_url

    azure_openai_endpoint = _clean_env_value(environ.get("AZURE_OPENAI_ENDPOINT"))
    azure_openai_api_key = _clean_env_value(environ.get("AZURE_OPENAI_API_KEY"))

    if azure_openai_endpoint:
        embedding_kwargs["azure_endpoint"] = azure_openai_endpoint
    if azure_openai_api_key:
        embedding_kwargs["azure_api_key"] = azure_openai_api_key

    return embedding_kwargs
