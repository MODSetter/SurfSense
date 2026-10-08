"""A file replaced whole, so a reader or a kill mid-write never leaves half of it.

Windows refuses to replace a file another process has open, and the sweep's
runner and `report` read a run's ledger and the sweep's results while they are
rewritten; the replace is tried again rather than lost.
"""

import time
from pathlib import Path

# A reader holds one of these small files for milliseconds; this rides out a second.
_TRIES = 50
_PAUSE_SECONDS = 0.02


def write_whole(path: Path, text: str) -> None:
    """Write beside `path`, then put it in place."""
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f".{path.name}.partial")
    partial.write_text(text, encoding="utf-8")
    for tried in range(1, _TRIES + 1):
        try:
            partial.replace(path)
            return
        except PermissionError:
            if tried == _TRIES:
                raise
            time.sleep(_PAUSE_SECONDS)
