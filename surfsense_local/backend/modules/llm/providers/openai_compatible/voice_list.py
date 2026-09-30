"""A server's voices, asked of the server itself.

The OpenAI API has no route that lists voices, and models.dev carries none,
so nothing else knows them. `GET /audio/voices` is Kokoro-FastAPI's; a server
without it leaves the user to type the voices.
"""

import httpx

from modules.llm.connections.key_headers import key_headers
from modules.llm.providers.protocols import Voice

__all__ = ["listed_voices"]

LIST_TIMEOUT = httpx.Timeout(10.0, connect=5.0)

# Held for the process, never stored: a server gains voices on its own
# schedule, and the next start asks again. Only answers are held; a server
# that could not be reached is asked again.
_answers: dict[tuple[int, str], list[Voice] | None] = {}


def listed_voices(
    connection_id: int,
    base_url: str,
    api_key: str | None,
    *,
    transport: httpx.BaseTransport | None = None,
) -> list[Voice] | None:
    """The server's voices, or None when it lists none. Ids alone: no server
    states a voice's gender or languages here, so none is claimed."""
    key = (connection_id, base_url)
    if key in _answers:
        return _answers[key]
    try:
        with httpx.Client(
            timeout=LIST_TIMEOUT,
            headers=key_headers(base_url, api_key),
            transport=transport,
        ) as client:
            reply = client.get(f"{base_url.rstrip('/')}/audio/voices")
    except httpx.HTTPError:
        return None
    _answers[key] = _voices(reply)
    return _answers[key]


def _voices(reply: httpx.Response) -> list[Voice] | None:
    if reply.is_error:
        return None
    try:
        listed = reply.json()["voices"]
        ids = [entry["id"] for entry in listed]
    except (ValueError, KeyError, TypeError):
        return None
    if not ids or not all(isinstance(id, str) and id for id in ids):
        return None
    return [Voice(id, id, None, ()) for id in dict.fromkeys(ids)]
