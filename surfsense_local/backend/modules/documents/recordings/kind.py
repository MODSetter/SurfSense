"""Which sources are recordings: the server-owned MIME type an upload was given."""

RECORDING_MIME_PREFIX = "audio/"


def is_recording(mime_type: str | None) -> bool:
    return mime_type is not None and mime_type.startswith(RECORDING_MIME_PREFIX)
