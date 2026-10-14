"""The child's work: the recording's length from its headers, the disk checked
for room, then its samples streamed to `<out>.part`, renamed to `out` once
every one is written, so a file named `out` is always whole."""

import errno
import shutil
import sys
from pathlib import Path

import miniaudio

from worker.audio_decode.outcome import DecodeOutcome
from worker.audio_decode.room import needed_bytes

__all__ = ["decode_to_pcm"]

RATE = 16000
# Four seconds a read: memory stays flat for an 18-hour file.
_FRAMES_PER_READ = 4 * RATE


def decode_to_pcm(source: Path, out: Path) -> DecodeOutcome:
    """Little-endian signed 16-bit mono at 16 kHz, through miniaudio's own
    resampler and channel mix."""
    part = out.with_name(f"{out.name}.part")
    try:
        needed = needed_bytes(_header_seconds(source))
    except miniaudio.MiniaudioError as error:
        return DecodeOutcome("undecodable", detail=str(error))
    if shutil.disk_usage(out.parent).free < needed:
        return DecodeOutcome("no_room", needed_bytes=needed)
    try:
        frames = _stream(source, part)
    except miniaudio.MiniaudioError as error:
        part.unlink(missing_ok=True)
        return DecodeOutcome("undecodable", detail=str(error))
    except OSError as error:
        part.unlink(missing_ok=True)
        if error.errno == errno.ENOSPC:
            return DecodeOutcome("no_room", needed_bytes=needed)
        raise
    if frames == 0:
        part.unlink()
        return DecodeOutcome("no_audio")
    part.replace(out)
    return DecodeOutcome("decoded", seconds=frames / RATE)


def _header_seconds(source: Path) -> float:
    # miniaudio picks the reader by extension and knows .oga by no name.
    if source.suffix.lower() == ".oga":
        return miniaudio.vorbis_get_file_info(str(source)).duration
    return miniaudio.get_file_info(str(source)).duration


def _stream(source: Path, part: Path) -> int:
    frames = 0
    with part.open("wb") as written:
        for chunk in miniaudio.stream_file(
            str(source),
            output_format=miniaudio.SampleFormat.SIGNED16,
            nchannels=1,
            sample_rate=RATE,
            frames_to_read=_FRAMES_PER_READ,
        ):
            if sys.byteorder == "big":
                chunk.byteswap()
            written.write(chunk.tobytes())
            frames += len(chunk)
    return frames
