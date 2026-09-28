from urllib.parse import urlsplit

# Anthropic's OpenAI layer accepts a bearer key for chat, but its model listing
# reads only its native headers, which both routes accept.
_ANTHROPIC_HOST = "api.anthropic.com"
_ANTHROPIC_VERSION = "2023-06-01"


def key_headers(base_url: str, api_key: str | None) -> dict[str, str]:
    """The headers that carry a connection's key to its server."""
    if not api_key:
        return {}
    if urlsplit(base_url).hostname == _ANTHROPIC_HOST:
        return {"x-api-key": api_key, "anthropic-version": _ANTHROPIC_VERSION}
    return {"Authorization": f"Bearer {api_key}"}
