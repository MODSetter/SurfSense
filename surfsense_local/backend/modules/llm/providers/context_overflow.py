"""A refusal for a request longer than the model's context window: sent again, it is refused again."""

import httpx

# llama.cpp's type for a prompt past the window (b11050, server-common.cpp).
_LLAMACPP_TYPE = "exceed_context_size_error"
# OpenAI's code for it, which compatible servers copy.
_OPENAI_CODE = "context_length_exceeded"


class ContextOverflowError(httpx.HTTPStatusError):
    """A model refused a request longer than its window."""


def refuses_as_too_long(response: httpx.Response) -> bool:
    """Whether a refusal's body says the request was longer than the window.

    The provider read the body once already, for its message, so this reads the
    cached content; an unread or non-JSON body is not this refusal.
    """
    try:
        payload = response.json()
    except (httpx.HTTPError, httpx.ResponseNotRead, ValueError):
        return False
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return False
    return error.get("type") == _LLAMACPP_TYPE or error.get("code") == _OPENAI_CODE
