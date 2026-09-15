import enum

import httpx


class ChatErrorKind(enum.StrEnum):
    """Buckets a failed generation call so the UI can offer the right fix.

    Add new kinds here as new failure shapes come up; keep classify_chat_error
    the single place that maps an exception to one.
    """

    PROVIDER_AUTH = "provider_auth"
    PROVIDER_NOT_FOUND = "provider_not_found"
    PROVIDER_RATE_LIMITED = "provider_rate_limited"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    NETWORK = "network"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


_MESSAGES: dict[ChatErrorKind, str] = {
    ChatErrorKind.PROVIDER_AUTH: "Your model connection needs a new API key.",
    ChatErrorKind.PROVIDER_NOT_FOUND: (
        "The selected model couldn't be found — pick another in Model setup."
    ),
    ChatErrorKind.PROVIDER_RATE_LIMITED: (
        "The model provider is rate-limiting requests right now. "
        "Try again in a moment."
    ),
    ChatErrorKind.PROVIDER_UNAVAILABLE: (
        "The model provider is temporarily unavailable. Try again shortly."
    ),
    ChatErrorKind.TIMEOUT: "The model took too long to respond. Try again.",
    ChatErrorKind.UNKNOWN: "Something went wrong generating a reply. Try again.",
}

# `network` is the one kind whose fix depends on the provider: a bad base URL
# is a Model setup problem, an unreachable local Ollama is not.
_NETWORK_MESSAGES: dict[str, str] = {
    "ollama": "Couldn't reach Ollama — make sure it's running locally.",
}
_DEFAULT_NETWORK_MESSAGE = (
    "Couldn't reach the model provider — "
    "check the connection's URL in Model setup."
)

_AUTH_STATUS_CODES = {401, 403}


def classify_chat_error(exc: Exception, provider: str) -> tuple[ChatErrorKind, str]:
    """Sort a generation failure into a kind, with the plain-language text to show.

    Classification is by exception type and HTTP status only, never by parsing
    the exception's text, so this holds for any provider that raises through
    httpx (every provider in modules/llm/providers does).
    """
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        if status_code in _AUTH_STATUS_CODES:
            kind = ChatErrorKind.PROVIDER_AUTH
        elif status_code == 404:
            kind = ChatErrorKind.PROVIDER_NOT_FOUND
        elif status_code == 429:
            kind = ChatErrorKind.PROVIDER_RATE_LIMITED
        else:
            kind = ChatErrorKind.PROVIDER_UNAVAILABLE
        return kind, _MESSAGES[kind]
    if isinstance(exc, httpx.TimeoutException):
        return ChatErrorKind.TIMEOUT, _MESSAGES[ChatErrorKind.TIMEOUT]
    if isinstance(exc, httpx.TransportError):
        message = _NETWORK_MESSAGES.get(provider, _DEFAULT_NETWORK_MESSAGE)
        return ChatErrorKind.NETWORK, message
    return ChatErrorKind.UNKNOWN, _MESSAGES[ChatErrorKind.UNKNOWN]
