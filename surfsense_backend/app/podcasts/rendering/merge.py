"""Concatenate ordered segment files into a single MP3.

Uses FFmpeg's concat *demuxer* (a list file of inputs) rather than a
``filter_complex`` graph. The demuxer takes one ``-i`` no matter how many
segments there are, so an hour-long episode with thousands of turns never hits
command-line length limits. Output is always re-encoded to MP3 for a uniform
artifact regardless of the source container (Kokoro WAV or hosted MP3).
"""

from __future__ import annotations

from pathlib import Path

from ffmpeg.asyncio import FFmpeg

from .errors import RenderError


async def concat_to_mp3(segment_paths: list[Path], output_path: Path) -> None:
    """Merge ``segment_paths`` in order into ``output_path`` as MP3."""
    if not segment_paths:
        raise RenderError("cannot merge an empty list of segments")

    list_file = output_path.with_name(f"{output_path.stem}.concat.txt")
    list_file.write_text(_concat_list(segment_paths), encoding="utf-8")

    try:
        ffmpeg = (
            FFmpeg()
            .option("y")
            .input(str(list_file), f="concat", safe=0)
            .output(str(output_path), {"c:a": "libmp3lame"})
        )
        await ffmpeg.execute()
    except Exception as exc:
        raise RenderError(f"audio merge failed: {exc}") from exc
    finally:
        list_file.unlink(missing_ok=True)


def _concat_list(segment_paths: list[Path]) -> str:
    # The concat demuxer reads `file '<path>'` lines; single quotes in a path
    # are escaped per its quoting rules ('\'').
    lines = []
    for path in segment_paths:
        escaped = str(path.resolve()).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    return "\n".join(lines) + "\n"
