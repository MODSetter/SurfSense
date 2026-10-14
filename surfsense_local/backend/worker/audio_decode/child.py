"""The decode process: worker.py's --decode-audio mode. It loads no queue,
database or settings, prints its outcome on one line and exits 0; anything
else is a decoder that died."""

import os
import sys
import threading
from pathlib import Path

from worker.audio_decode.decode import decode_to_pcm

# Exit status of a child whose worker went away mid-decode.
ORPHANED = 3


def main(source: str, out: str) -> None:
    _exit_with_the_worker()
    outcome = decode_to_pcm(Path(source), Path(out))
    sys.stdout.write(outcome.line() + "\n")
    sys.stdout.flush()


def _exit_with_the_worker() -> None:
    """The worker holds the other end of stdin, so stdin closing means it is
    gone: a decode of a long file must not outlive it."""

    def exit_at_eof() -> None:
        # The raw descriptor: a thread blocked in sys.stdin holds its lock, and
        # the interpreter aborts at exit when it cannot take it.
        while os.read(sys.stdin.fileno(), 4096):
            pass
        os._exit(ORPHANED)

    threading.Thread(target=exit_at_eof, daemon=True).start()
