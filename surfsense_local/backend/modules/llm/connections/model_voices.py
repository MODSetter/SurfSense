"""The voices one entry of a server's model list publishes, as OpenRouter's
`supported_voices`. Here, not under `providers/`, whose package loads the chat
provider, which needs `connections.service`, which needs this."""

__all__ = ["voices_of"]

# What a voice test and a podcast brief accept.
_MAX_VOICE_ID = 100


def voices_of(entry: dict) -> list[str]:
    """The ids it publishes, each once, without what no brief takes."""
    raw = entry.get("supported_voices")
    if not isinstance(raw, list):
        return []
    return list(
        dict.fromkeys(
            voice
            for voice in raw
            if isinstance(voice, str) and 0 < len(voice) <= _MAX_VOICE_ID
        )
    )
