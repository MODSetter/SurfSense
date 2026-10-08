"""The script process: worker.py's --run-document-script mode.

It loads nothing of the worker's queue, database or settings; the script gets
only its folder and the environment the parent built.
"""

import os
import runpy
import signal
import sys
import threading
import traceback
from pathlib import Path

from worker.document_script.run_folder import SCRIPT_NAME


def main(folder: str) -> None:
    """Run the folder's script.py as __main__ from inside the folder; a failure
    prints its traceback and exits 1."""
    if sys.platform != "win32":
        _die_with_the_worker()
    os.chdir(folder)
    script = str(Path(folder).resolve() / SCRIPT_NAME)
    try:
        runpy.run_path(script, run_name="__main__")
    except Exception as error:
        _print_traceback_from_the_script(error, script, folder)
        sys.exit(1)


def _die_with_the_worker() -> None:
    """POSIX: the script's process group is its own, out of reach of a stop of
    the worker's group. The worker holds the other end of stdin, so stdin
    closing means the worker is gone, and the group goes too. (A job object
    does this on Windows.)"""

    def kill_the_group_at_eof() -> None:
        # The raw descriptor: a thread blocked in sys.stdin holds its lock, and
        # the interpreter aborts at exit when it cannot take it.
        while os.read(sys.stdin.fileno(), 4096):
            pass
        os.killpg(0, signal.SIGKILL)

    threading.Thread(target=kill_the_group_at_eof, daemon=True).start()


def _print_traceback_from_the_script(
    error: Exception, script: str, folder: str
) -> None:
    """The traceback without the runner's own frames, which mean nothing to the
    model fixing the script. A SyntaxError has none of the script's frames."""
    frame = error.__traceback__
    while frame is not None and frame.tb_frame.f_code.co_filename != script:
        frame = frame.tb_next
    printed = "".join(traceback.format_exception(type(error), error, frame))
    sys.stderr.write(_without_the_run_folder(printed, folder, script))


def _without_the_run_folder(text: str, folder: str, script: str) -> str:
    """Paths in the run folder, relative to it: the folder is gone once the run
    ends, and its absolute path in every frame crowds the traceback out of the
    500-character reason the agent reads."""
    prefixes = {os.path.join(folder, ""), os.path.join(os.path.dirname(script), "")}
    # Longest first: the resolved form can end with the given one, as
    # /private/var/... does /var/... on macOS.
    for prefix in sorted(prefixes, key=len, reverse=True):
        text = text.replace(prefix, "")
    return text
