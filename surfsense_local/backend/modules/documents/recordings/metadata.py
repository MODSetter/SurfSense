"""What a recording's job keeps under `transcription` in the row's metadata:
`{language, duration_s, model}` once transcribed, or `{awaiting: true}` while
it waits for a speech model to be chosen."""

from typing import Any

KEY = "transcription"
AWAITING = "awaiting"


def transcription_entry(metadata: dict[str, Any] | None) -> dict[str, Any]:
    entry = (metadata or {}).get(KEY)
    return entry if isinstance(entry, dict) else {}


def is_awaiting(metadata: dict[str, Any] | None) -> bool:
    return transcription_entry(metadata).get(AWAITING) is True
