"""Body fields that send a conversation's requests to the cache holding its prompt.

A provider caches a prompt on the machine that read it, and a key naming the
conversation routes its next request there. Only a host known to take a field
gets it: a strict endpoint rejects one it does not know.
"""

from urllib.parse import urlsplit

_OPENROUTER_HOST = "openrouter.ai"
_OPENAI_HOST = "api.openai.com"
# OpenRouter caches these only behind a marker; every other family it serves
# caches on its own.
_MARKED_FAMILY = "anthropic/"


def conversation_fields(
    url: str, model: str, conversation: str | None
) -> dict[str, object]:
    """What this host reads to keep `conversation` on one cache, if anything."""
    if conversation is None:
        return {}
    host = urlsplit(url).hostname
    if host == _OPENROUTER_HOST:
        fields: dict[str, object] = {"session_id": conversation}
        if model.startswith(_MARKED_FAMILY):
            # Top level, so the breakpoint moves to each turn's last message.
            fields["cache_control"] = {"type": "ephemeral"}
        return fields
    if host == _OPENAI_HOST:
        return {"prompt_cache_key": conversation}
    return {}
