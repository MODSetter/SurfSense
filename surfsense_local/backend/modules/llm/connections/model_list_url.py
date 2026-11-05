from urllib.parse import urlsplit

# OpenCode's Console lists under /inference[/go]/v1; /inference/openai/v1/models
# is a 404. https://opencode.ai/docs/zen https://opencode.ai/docs/go
_CONSOLE_HOST = "opencode.ai"
_CONSOLE_PATHS = {
    "/inference/openai/v1": "/inference/v1/models",
    "/inference/go/openai/v1": "/inference/go/v1/models",
}


def model_list_url(base_url: str) -> str:
    """Where a connection's server lists its models."""
    address = base_url.rstrip("/")
    parts = urlsplit(address)
    if parts.hostname == _CONSOLE_HOST and parts.path in _CONSOLE_PATHS:
        return f"https://{_CONSOLE_HOST}{_CONSOLE_PATHS[parts.path]}"
    return f"{address}/models"
