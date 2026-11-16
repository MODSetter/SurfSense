"""transcript/segments.json: where each paragraph of a finished transcript sits
in the recording, so a citation of a recording can seek to it later."""

import json
from collections.abc import Sequence
from pathlib import Path

from worker.ingestion.audio.transcript_text import HeardWindow, paragraph_lines

__all__ = ["write_segments"]


def write_segments(
    path: Path,
    *,
    model_id: str,
    language: str | None,
    seconds: float,
    windows: Sequence[HeardWindow],
) -> None:
    """Raises OSError when the disk is full."""
    segments = [
        {
            "line": line,
            "start_s": window.start_s,
            "end_s": window.end_s,
            "language": window.language,
        }
        for window, line in zip(windows, paragraph_lines(windows), strict=True)
        if line is not None
    ]
    partial = path.with_name(f"{path.name}.partial")
    partial.write_text(
        json.dumps(
            {
                "model_id": model_id,
                "language": language,
                "duration_s": seconds,
                "windows": segments,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    partial.replace(path)
