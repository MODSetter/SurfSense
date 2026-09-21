import enum

import httpx

from shared.secrets import UnreadableSecretError


class ChatErrorKind(enum.StrEnum):
    """Buckets a failed generation call so the UI can offer the right fix.

    Add new kinds here as new failure shapes come up; keep classify_chat_error
    the single place that maps an exception to one.
    """

    PROVIDER_AUTH = "provider_auth"
    PROVIDER_NOT_FOUND = "provider_not_found"
    PROVIDER_RATE_LIMITED = "provider_rate_limited"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    CONTEXT_TOO_LONG = "context_too_long"
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
    ChatErrorKind.CONTEXT_TOO_LONG: (
        "This conversation is too long for the model's context window. "
        "Start a new chat or pick a model with a larger window."
    ),
    ChatErrorKind.TIMEOUT: "The model took too long to respond. Try again.",
    ChatErrorKind.UNKNOWN: "Something went wrong generating a reply. Try again.",
}

# `network` is the one kind whose fix depends on the provider: a bad base URL
# is a Model setup problem, an unreachable local runtime is not.
_NETWORK_MESSAGES: dict[str, str] = {
    "llamacpp": "Couldn't reach the local model runtime. Restart SurfSense to start it again.",
}
_DEFAULT_NETWORK_MESSAGE = (
    "Couldn't reach the model provider — "
    "check the connection's URL in Model setup."
)

_AUTH_STATUS_CODES = {401, 403}

# llama.cpp's own name for the one 400 that retrying can never fix: the
# prompt does not get shorter on its own. Every other 400 keeps the generic
# PROVIDER_UNAVAILABLE bucket, because only this one shape names a fix.
_CONTEXT_TOO_LONG_ERROR_TYPE = "exceed_context_size_error"


def classify_chat_error(exc: Exception, provider: str) -> tuple[ChatErrorKind, str]:
    """Sort a generation failure into a kind, with the plain-language text to show.

    Classification is by exception type and HTTP status only, never by parsing
    the exception's text, so this holds for any provider that raises through
    httpx (every provider in modules/llm/providers does).
    """
    if isinstance(exc, UnreadableSecretError):
        # Not `unknown`: the fix is specific and the user can do it. The stored
        # key is unrecoverable once this install's secret changes, so the only
        # useful answer names the key rather than reporting a fault.
        return ChatErrorKind.PROVIDER_AUTH, _MESSAGES[ChatErrorKind.PROVIDER_AUTH]
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        if status_code in _AUTH_STATUS_CODES:
            kind = ChatErrorKind.PROVIDER_AUTH
        elif status_code == 404:
            kind = ChatErrorKind.PROVIDER_NOT_FOUND
        elif status_code == 429:
            kind = ChatErrorKind.PROVIDER_RATE_LIMITED
        elif status_code == 400 and _is_context_too_long(exc.response):
            kind = ChatErrorKind.CONTEXT_TOO_LONG
        else:
            kind = ChatErrorKind.PROVIDER_UNAVAILABLE
        return kind, _MESSAGES[kind]
    if isinstance(exc, httpx.TimeoutException):
        return ChatErrorKind.TIMEOUT, _MESSAGES[ChatErrorKind.TIMEOUT]
    if isinstance(exc, httpx.TransportError):
        message = _NETWORK_MESSAGES.get(provider, _DEFAULT_NETWORK_MESSAGE)
        return ChatErrorKind.NETWORK, message
    return ChatErrorKind.UNKNOWN, _MESSAGES[ChatErrorKind.UNKNOWN]


def _is_context_too_long(response: httpx.Response) -> bool:
    """Whether a 400 is llama.cpp's `exceed_context_size_error`, read from the
    body it already sent rather than parsed from the message text.

    The body was read once already, building the exception's own message
    (`_error_message` in the chat provider), so this reads the cached content
    rather than the network again. A response httpx has not read yet, or one
    with no JSON body at all, is not this kind and falls through quietly.
    """
    try:
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return False
    error = payload.get("error") if isinstance(payload, dict) else None
    error_type = error.get("type") if isinstance(error, dict) else None
    return error_type == _CONTEXT_TOO_LONG_ERROR_TYPE
