"""One episode from each line's reply, in the format the server sent.

The format is read from the bytes, not from what was asked for: a server can
ignore `response_format`. WAV joins frame by frame with a pause between
speakers. MP3 joins frame to frame with no pause, because a silent frame would
need the episode's encoder settings, which no reply states.
"""

import struct
from collections.abc import Sequence

from modules.llm.providers.audiocpp.joined_wav import joined_wav
from modules.llm.providers.protocols import SynthesizedAudio

__all__ = ["joined_replies"]


def joined_replies(replies: Sequence[bytes]) -> SynthesizedAudio:
    """Raises ValueError when the replies are neither WAV nor MP3, or mixed."""
    kinds = {_kind(reply) for reply in replies}
    if kinds == {"wav"}:
        # A line's pieces run on; only a new line gets the pause.
        lines = [joined_wav(_stacked_wavs(reply), gap=0) for reply in replies]
        return SynthesizedAudio(joined_wav(lines), "audio/wav")
    if kinds == {"mp3"}:
        return SynthesizedAudio(b"".join(map(_mp3_frames, replies)), "audio/mpeg")
    raise ValueError(f"the lines came back as {', '.join(sorted(kinds))}")


def _kind(reply: bytes) -> str:
    if reply[:4] == b"RIFF" and reply[8:12] == b"WAVE":
        return "wav"
    if reply[:3] == b"ID3" or _frame_length(reply, 0):
        return "mp3"
    return "neither WAV nor MP3"


def _stacked_wavs(reply: bytes) -> list[bytes]:
    """Each WAV in a reply, by the size its RIFF header states. A streamed WAV
    states no size, and is taken whole."""
    parts = []
    at = 0
    while reply[at : at + 4] == b"RIFF":
        (size,) = struct.unpack_from("<I", reply, at + 4)
        end = at + 8 + size
        if size in (0, 0xFFFFFFFF) or end > len(reply):
            parts.append(reply[at:])
            return parts
        parts.append(reply[at:end])
        at = end
    return parts or [reply]


def _mp3_frames(reply: bytes) -> bytes:
    """The audio frames alone: without the ID3v2 tag, and without the Xing or
    Info frame, which states one line's length for the whole file."""
    at = 0
    if reply[:3] == b"ID3":
        size = _syncsafe(reply[6:10])
        at = 10 + size + (10 if reply[5] & 0x10 else 0)
    length = _frame_length(reply, at)
    if length and (b"Xing" in reply[at : at + 40] or b"Info" in reply[at : at + 40]):
        at += length
    return reply[at:]


def _syncsafe(four: bytes) -> int:
    return (four[0] << 21) | (four[1] << 14) | (four[2] << 7) | four[3]


# Kbit/s by index for MPEG-1 and for MPEG-2/2.5, Layer III.
_BITRATES = {
    1: (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320),
    2: (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160),
}
_RATES = {3: (44100, 48000, 32000), 2: (22050, 24000, 16000), 0: (11025, 12000, 8000)}


def _frame_length(data: bytes, at: int) -> int:
    """The byte length of the Layer III frame at `at`, or 0 when none starts there."""
    if len(data) < at + 4 or data[at] != 0xFF or data[at + 1] & 0xE0 != 0xE0:
        return 0
    version = (data[at + 1] >> 3) & 0x3
    layer = (data[at + 1] >> 1) & 0x3
    bitrate_index = data[at + 2] >> 4
    rate_index = (data[at + 2] >> 2) & 0x3
    if version == 1 or layer != 1 or bitrate_index in (0, 15) or rate_index == 3:
        return 0
    mpeg1 = version == 3
    bitrate = _BITRATES[1 if mpeg1 else 2][bitrate_index] * 1000
    rate = _RATES[version][rate_index]
    padding = (data[at + 2] >> 1) & 0x1
    return (144 if mpeg1 else 72) * bitrate // rate + padding
