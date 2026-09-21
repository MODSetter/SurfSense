"""The probe, as a child process. One line per device on stdout.

Run rather than imported. Everything it needs is the library directory, given as
its one argument, and the parent sets the working directory so ggml's backend
scan finds the libraries beside them.

Kept to the standard library and this package's own loader: this runs before the
app is up, and a heavy import here would be paid on every probe.
"""

import sys
import traceback
from pathlib import Path

from modules.llm.hardware.device_lines import encode_line
from modules.llm.hardware.probe import probe_devices_in_process


def main(argv: list[str]) -> int:
    """Print this machine's devices, or say why not on stderr.

    Exit 1 with a traceback rather than an empty listing: zero devices is a
    meaningful answer that the parent treats as a real machine with no GPU, and
    a crash must not be mistaken for one.
    """
    if len(argv) != 1:
        sys.stderr.write("usage: probe_script <library-dir>\n")
        return 2
    try:
        devices = probe_devices_in_process(Path(argv[0]))
    except Exception:  # the parent reads the traceback, then falls back
        traceback.print_exc(file=sys.stderr)
        return 1

    # Written rather than printed: this is the protocol between two processes,
    # and the parent parses it line by line.
    for device in devices:
        sys.stdout.write(encode_line(device) + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess
    sys.exit(main(sys.argv[1:]))
