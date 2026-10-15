"""How far a recording's transcription has come, kept beside its checkpoint so a
reload, a late listener or the job after a yield reads it too."""

import json
import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path

__all__ = ["TranscriptionProgress", "read_progress", "write_progress"]

logger = logging.getLogger(__name__)

# Windows refuses to replace a file another process has open; the API reads
# this one for a moment at a time.
_REPLACE_ATTEMPTS = 5
_REPLACE_PAUSE_SECONDS = 0.02


@dataclass(frozen=True)
class TranscriptionProgress:
    # Where in the recording the last finished window ends.
    done_s: float
    total_s: float
    # Time spent waiting for memory, summed across yields: the job gives up
    # past its limit.
    memory_wait_s: float = 0.0


def read_progress(path: Path) -> TranscriptionProgress | None:
    """None when there is no complete file to read."""
    try:
        kept = json.loads(path.read_text(encoding="utf-8"))
        return TranscriptionProgress(
            float(kept["done_s"]),
            float(kept["total_s"]),
            float(kept.get("memory_wait_s", 0.0)),
        )
    except (OSError, ValueError, TypeError, KeyError):
        return None


def write_progress(path: Path, progress: TranscriptionProgress) -> None:
    """Replaced whole, so a reader never sees half of it. Raises OSError only
    for a full disk; a reader holding the file costs this update alone."""
    partial = path.with_name(f"{path.name}.partial")
    partial.write_text(json.dumps(asdict(progress)), encoding="utf-8")
    for _ in range(_REPLACE_ATTEMPTS):
        try:
            partial.replace(path)
            return
        except PermissionError:
            time.sleep(_REPLACE_PAUSE_SECONDS)
    logger.info("transcription: %s is held open; this update is skipped", path)
