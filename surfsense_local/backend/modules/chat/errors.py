import enum

import httpx

from modules.egress.service import EgressDeniedError
from modules.llm.providers.openai_compatible.chat import StreamedError
from modules.llm.providers.openai_responses import PlanLimitError, SignInRequiredError
from modules.llm.subscriptions.claude.errors import (
    ClaudePlanLimitError,
    ClaudeSignInRequiredError,
)
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
    MODEL_CANNOT_RUN = "model_cannot_run"
    CONTEXT_TOO_LONG = "context_too_long"
    SUBSCRIPTION_SIGN_IN = "subscription_sign_in"
    SUBSCRIPTION_LIMIT = "subscription_limit"
    CLAUDE_SIGN_IN = "claude_sign_in"
    CLAUDE_LIMIT = "claude_limit"
    EGRESS_DISABLED = "egress_disabled"
    RUNTIME_BUSY = "runtime_busy"
    NETWORK = "network"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


_MESSAGES: dict[ChatErrorKind, str] = {
    ChatErrorKind.PROVIDER_AUTH: "Your model connection needs a new API key.",
    ChatErrorKind.PROVIDER_NOT_FOUND: (
        "The selected model couldn't be found — pick another in Model setup."
    ),
    ChatErrorKind.PROVIDER_RATE_LIMITED: (
        "The model provider is rate-limiting requests right now. Try again in a moment."
    ),
    ChatErrorKind.PROVIDER_UNAVAILABLE: (
        "The model provider is temporarily unavailable. Try again shortly."
    ),
    ChatErrorKind.MODEL_CANNOT_RUN: (
        "SurfSense cannot run this model. Pick another model."
    ),
    ChatErrorKind.CONTEXT_TOO_LONG: (
        "This conversation is too long for the model's context window. "
        "Start a new chat or pick a model with a larger window."
    ),
    ChatErrorKind.SUBSCRIPTION_SIGN_IN: (
        "Your ChatGPT account needs to sign in again in Model setup."
    ),
    ChatErrorKind.SUBSCRIPTION_LIMIT: (
        "Your ChatGPT plan's usage limit is reached. "
        "It resets on its own; check your usage in ChatGPT's settings."
    ),
    ChatErrorKind.CLAUDE_SIGN_IN: (
        "Claude Code on this computer needs to sign in again: run claude in a "
        "terminal and sign in."
    ),
    ChatErrorKind.CLAUDE_LIMIT: (
        "Your Claude plan's usage limit is reached. It resets on its own."
    ),
    ChatErrorKind.EGRESS_DISABLED: (
        "A host this model needs was turned off in Settings > Network. "
        "Allow it there, then try again."
    ),
    ChatErrorKind.RUNTIME_BUSY: (
        "The replies running together ran out of room in the local model's "
        "memory. Try again."
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
    "Couldn't reach the model provider — check the connection's URL in Model setup."
)

_AUTH_STATUS_CODES = {401, 403}

# llama.cpp's own name for the one 400 that retrying can never fix: the
# prompt does not get shorter on its own. Every other 400 keeps the generic
# PROVIDER_UNAVAILABLE bucket, because only this one shape names a fix.
_CONTEXT_TOO_LONG_ERROR_TYPE = "exceed_context_size_error"

# The local runtime is our own subprocess, not somebody's API, so a 500 from it
# is not a service having a bad minute. It is llama-server saying it could not
# load the file: an architecture this build has no builder for, or one it builds
# and then aborts on. "Try again shortly" sends the reader into a retry loop
# over something that can never work.
_LOCAL_RUNTIME = "llamacpp"

# What llama.cpp says when replies sharing one unified cache overflow it. It
# ends every request involved, as a 500 like a model that failed to load, so
# the message is the only thing that tells the two apart. At b11050 each
# request is told "Context size has been exceeded." (server-context.cpp); the
# other two are what its log says.
_CACHE_FULL = (
    "context size has been exceeded",
    "failed to find free space in the kv cache",
    "failed to find a memory slot",
)


def classify_chat_error(exc: Exception, provider: str) -> tuple[ChatErrorKind, str]:
    """Sort a generation failure into a kind, with the plain-language text to show.

    Classification is by exception type, HTTP status and provider; an error's
    own words are read only where those leave it ambiguous.
    """
    if isinstance(exc, UnreadableSecretError):
        # Not `unknown`: the fix is specific and the user can do it. The stored
        # key is unrecoverable once this install's secret changes, so the only
        # useful answer names the key rather than reporting a fault.
        return ChatErrorKind.PROVIDER_AUTH, _MESSAGES[ChatErrorKind.PROVIDER_AUTH]
    # Refused before a reply, this is a 403 the egress prompt answers; refused
    # during one, as a Claude Code run is when a host is turned off, it is here.
    if isinstance(exc, EgressDeniedError):
        kind = ChatErrorKind.EGRESS_DISABLED
        return kind, _MESSAGES[kind]
    # The Claude plan's first: they are the ChatGPT plan's errors too.
    if isinstance(exc, ClaudeSignInRequiredError):
        kind = ChatErrorKind.CLAUDE_SIGN_IN
        return kind, _MESSAGES[kind]
    if isinstance(exc, ClaudePlanLimitError):
        kind = ChatErrorKind.CLAUDE_LIMIT
        return kind, _MESSAGES[kind]
    if isinstance(exc, SignInRequiredError):
        kind = ChatErrorKind.SUBSCRIPTION_SIGN_IN
        return kind, _MESSAGES[kind]
    if isinstance(exc, PlanLimitError):
        kind = ChatErrorKind.SUBSCRIPTION_LIMIT
        return kind, _MESSAGES[kind]
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
        elif status_code == 500 and provider == _LOCAL_RUNTIME:
            kind = (
                ChatErrorKind.RUNTIME_BUSY
                if _is_cache_full(exc.response)
                else ChatErrorKind.MODEL_CANNOT_RUN
            )
        else:
            kind = ChatErrorKind.PROVIDER_UNAVAILABLE
        return kind, _MESSAGES[kind]
    # The same overflow reaches a reply already streaming as an error chunk.
    if (
        isinstance(exc, StreamedError)
        and provider == _LOCAL_RUNTIME
        and _says_cache_full(str(exc))
    ):
        return ChatErrorKind.RUNTIME_BUSY, _MESSAGES[ChatErrorKind.RUNTIME_BUSY]
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


def _is_cache_full(response: httpx.Response) -> bool:
    """Whether a local runtime's 500 is its shared cache running out of room."""
    try:
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return False
    error = payload.get("error") if isinstance(payload, dict) else None
    said = error.get("message") if isinstance(error, dict) else None
    return isinstance(said, str) and _says_cache_full(said)


def _says_cache_full(said: str) -> bool:
    return said.casefold().startswith(_CACHE_FULL)


def empty_reply_error() -> tuple[ChatErrorKind, str]:
    """A stream that closed with no answer text: nothing raised, but nothing to keep.

    `unknown` rather than a new kind, whose text would need translating: a
    retry can succeed, since sampling differs from one run to the next.
    """
    return ChatErrorKind.UNKNOWN, _MESSAGES[ChatErrorKind.UNKNOWN]
