"""A one-lane, one-model sweep that presses Ctrl-C in its own console once its case runs, for the runner's tests.

usage: python -m tests.live.sweep.ctrl_c_sweep <work dir>, on Windows, in a
console of its own: the Ctrl-C reaches every process on it, as a terminal's does.
"""

import ctypes
import os
import sys
import threading
import time
from pathlib import Path

from tests.live.sweep.budget import Budget
from tests.live.sweep.model_list import ListedModel
from tests.live.sweep.ram_guard import RamGuard
from tests.live.sweep.runner import Runner, Sweep

_CTRL_C_EVENT = 0
# Long enough that the case is still running when Ctrl-C comes.
_CASE_SECONDS = "3"


def main() -> int:
    """Run the sweep; the case's stand-in passes unless the Ctrl-C reached it."""
    work = Path(sys.argv[1])
    kernel = ctypes.windll.kernel32  # type: ignore[attr-defined]
    # This process takes Ctrl-C even if it was started with it turned off.
    kernel.SetConsoleCtrlHandler(None, False)
    trace = work / "trace"

    def press_once_the_case_runs() -> None:
        while not (trace.is_dir() and any(trace.iterdir())):
            time.sleep(0.05)
        time.sleep(0.5)
        kernel.GenerateConsoleCtrlEvent(_CTRL_C_EVENT, 0)

    threading.Thread(target=press_once_the_case_runs, daemon=True).start()
    (work / "plan.json").write_text("{}", encoding="utf-8")
    Runner(
        Sweep(
            out=work / "sweep",
            models=[ListedModel("a/good", "good", 0.1, 0.0, 131_072, False)],
            assumed=[],
            listing={},
            command_for=lambda case, lane_dir: [
                sys.executable,
                str(Path(__file__).with_name("stand_in_case.py")),
                case,
            ],
            child_env={
                "STAND_IN_PLAN": str(work / "plan.json"),
                "STAND_IN_TRACE": str(trace),
                "STAND_IN_SECONDS": _CASE_SECONDS,
                "SYSTEMROOT": os.environ.get("SYSTEMROOT", "C:\\Windows"),
            },
            cwd=work,
            guard=RamGuard(lanes=1),
            budget=Budget(cap=100.0, case_cap=3.0),
            available_bytes=lambda: 64 << 30,
            poll_seconds=0.05,
            say=lambda line: None,
        )
    ).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
