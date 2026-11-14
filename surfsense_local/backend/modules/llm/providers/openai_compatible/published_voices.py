"""The voices a server publishes per model in its model list, as OpenRouter's
`supported_voices`. The OpenAI API names no such field, so most servers have none.
"""

import httpx

from modules.llm.connections.key_headers import key_headers
from modules.llm.connections.model_voices import voices_of

__all__ = ["published_voices"]

LIST_TIMEOUT = httpx.Timeout(10.0, connect=5.0)

# Held for the process, never stored: a model gains voices on its own schedule,
# and the next start asks again. A failed listing is not an answer.
_answers: dict[tuple[int, str], dict[str, list[str]]] = {}


def published_voices(
    connection_id: int,
    base_url: str,
    api_key: str | None,
    model: str,
    *,
    transport: httpx.BaseTransport | None = None,
) -> list[str] | None:
    """`model`'s voices, or None when it publishes none."""
    key = (connection_id, base_url)
    if key not in _answers:
        listing = _listing(base_url, api_key, transport)
        if listing is None:
            return None
        _answers[key] = listing
    return _answers[key].get(model) or None


def _listing(
    base_url: str, api_key: str | None, transport: httpx.BaseTransport | None
) -> dict[str, list[str]] | None:
    try:
        with httpx.Client(
            timeout=LIST_TIMEOUT,
            headers=key_headers(base_url, api_key),
            transport=transport,
        ) as client:
            # Every modality: OpenRouter's default listing leaves speech models out.
            reply = client.get(
                f"{base_url.rstrip('/')}/models",
                params={"output_modalities": "all"},
            )
        reply.raise_for_status()
        entries = reply.json()["data"]
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return None
    if not isinstance(entries, list):
        return None
    return {
        entry["id"]: voices_of(entry)
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }
