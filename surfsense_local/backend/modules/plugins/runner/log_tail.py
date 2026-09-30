from typing import IO

# The end of the output is what is kept: a plugin explains a failure last.
LOG_TAIL_BYTES = 16 * 1024


class LogTail:
    """The last of what a plugin prints, filled on a thread while the run is watched."""

    def __init__(self) -> None:
        self._kept = b""

    def read_from(self, output: IO[bytes]) -> None:
        """Read until the output closes, holding only its last bytes."""
        while chunk := output.read1(LOG_TAIL_BYTES):
            self._kept = (self._kept + chunk)[-LOG_TAIL_BYTES:]

    def text(self) -> str:
        """What has been kept so far, as text."""
        return self._kept.decode(errors="replace")
