"""Sandbox-execution helpers for ``execute_code``.

Wraps user-supplied code in a heredoc and dispatches it to the Daytona
sandbox associated with the current chat thread, with a single retry on
sandbox failure.
"""

from __future__ import annotations

import logging
import secrets
from typing import TYPE_CHECKING

from daytona.common.errors import DaytonaError
from langchain.tools import ToolRuntime

from app.agents.multi_agent_chat.shared.sandbox import (
    _evict_sandbox_cache,
    delete_sandbox,
    get_or_create_sandbox,
)
from app.agents.multi_agent_chat.shared.state.filesystem_state import (
    SurfSenseFilesystemState,
)

if TYPE_CHECKING:
    from ...middleware import SurfSenseFilesystemMiddleware

logger = logging.getLogger(__name__)

MAX_EXECUTE_TIMEOUT = 300


def wrap_as_python(code: str) -> str:
    """Wrap ``code`` in a unique-sentinel heredoc for shell execution."""
    sentinel = f"_PYEOF_{secrets.token_hex(8)}"
    return f"python3 << '{sentinel}'\n{code}\n{sentinel}"


async def execute_in_sandbox(
    mw: SurfSenseFilesystemMiddleware,
    command: str,
    runtime: ToolRuntime[None, SurfSenseFilesystemState],
    timeout: int | None,
) -> str:
    """Top-level entry: wraps + retries once on sandbox failure."""
    assert mw._thread_id is not None
    command = wrap_as_python(command)
    try:
        return await _try_sandbox_execute(mw, command, runtime, timeout)
    except (DaytonaError, Exception) as first_err:
        logger.warning(
            "Sandbox execute failed for thread %s, retrying: %s",
            mw._thread_id,
            first_err,
        )
        try:
            await delete_sandbox(mw._thread_id)
        except Exception:
            _evict_sandbox_cache(mw._thread_id)
        try:
            return await _try_sandbox_execute(mw, command, runtime, timeout)
        except Exception:
            logger.exception("Sandbox retry also failed for thread %s", mw._thread_id)
            return "Error: Code execution is temporarily unavailable. Please try again."


async def _try_sandbox_execute(
    mw: SurfSenseFilesystemMiddleware,
    command: str,
    runtime: ToolRuntime[None, SurfSenseFilesystemState],
    timeout: int | None,
) -> str:
    """One sandbox-execute attempt: get/create sandbox, run, format output."""
    sandbox, _is_new = await get_or_create_sandbox(mw._thread_id)
    result = await sandbox.aexecute(command, timeout=timeout)
    output = (result.output or "").strip()
    if not output and result.exit_code == 0:
        return (
            "[Code executed successfully but produced no output. "
            "Use print() to display results, then try again.]"
        )
    parts = [result.output]
    if result.exit_code is not None:
        status = "succeeded" if result.exit_code == 0 else "failed"
        parts.append(f"\n[Command {status} with exit code {result.exit_code}]")
    if result.truncated:
        parts.append("\n[Output was truncated due to size limits]")
    return "".join(parts)
