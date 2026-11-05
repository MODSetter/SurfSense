"""Refusals from OpenCode's Console that no retry fixes and whose words name the fix.

Its 400s, 402 and 403s say what is missing: funds, a privacy setting, access, a model.
Its 429 is this kind only for the free limit, since a rate limit does pass with time.
"""

import json
from urllib.parse import urlsplit

import httpx

PROVIDER_REFUSED = "provider_refused"

_CONSOLE_HOST = "opencode.ai"
_ALWAYS_FINAL = frozenset({400, 402, 403})
_RATE_LIMITED = 429
_FREE_LIMIT = "FreeUsageLimitError"
_RELAY_PREFIX = "Upstream request failed: "


def is_final_refusal(url: str, status_code: int, body: bytes) -> bool:
    if urlsplit(url).hostname != _CONSOLE_HOST:
        return False
    if status_code in _ALWAYS_FINAL:
        return True
    return status_code == _RATE_LIMITED and _error_type(body) == _FREE_LIMIT


def refusal_words(error: httpx.HTTPStatusError) -> str | None:
    """What to show for a failed chat request, or None when it is no such refusal."""
    response = error.response
    # A failure raised mid-stream carries a body nobody can read any more.
    try:
        body = response.content
    except httpx.ResponseNotRead:
        body = b""
    if not is_final_refusal(str(error.request.url), response.status_code, body):
        return None
    return console_words(str(error))


def console_words(message: str) -> str:
    """The reason alone: the prefix is how the Console reports it, not part of it."""
    return message.removeprefix(_RELAY_PREFIX)


def _error_type(body: bytes) -> object:
    try:
        payload = json.loads(body)
    except ValueError:
        return None
    error = payload.get("error") if isinstance(payload, dict) else None
    return error.get("type") if isinstance(error, dict) else None
