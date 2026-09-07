"""Run the model's generated code and return its module namespace.

The generated code runs unsandboxed in the worker process; the timeout bounds a
hang, not isolation. ponytail: ceiling — a runaway thread cannot be hard-killed
and the code holds the worker's privileges; upgrade path is an out-of-process
sandbox runner.
"""

from __future__ import annotations

import re
import threading

TIMEOUT_SECONDS = 120
_FENCE = re.compile(r"```(?:python)?\s*(.*?)```", re.DOTALL)


def extract_code(raw: str) -> str:
    """The Python the model returned, unwrapped from a ```python fence if present."""
    fenced = _FENCE.search(raw)
    return (fenced.group(1) if fenced else raw).strip()


def execute(code: str) -> dict:
    """Run the code in a fresh namespace, bounded by a timeout, and return it."""
    namespace: dict = {}
    failure: list[BaseException] = []

    def target() -> None:
        try:
            exec(compile(code, "<studio-office>", "exec"), namespace)
        except BaseException as error:  # any failure becomes the job's
            failure.append(error)

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(TIMEOUT_SECONDS)
    if thread.is_alive():
        raise RuntimeError(f"generated code did not finish within {TIMEOUT_SECONDS}s")
    if failure:
        error = failure[0]
        raise RuntimeError(f"generated code failed: {type(error).__name__}: {error}")
    return namespace
