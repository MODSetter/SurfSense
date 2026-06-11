"""The bytes a TTS provider returns for one segment."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SynthesizedAudio:
    """Encoded audio for a single segment, ready to cache and concatenate.

    ``container`` is the file extension the bytes are encoded as (``"wav"`` or
    ``"mp3"``); the renderer uses it to name the on-disk segment so FFmpeg can
    demux the right format during merge.
    """

    data: bytes
    container: str
    sample_rate: int | None = None
