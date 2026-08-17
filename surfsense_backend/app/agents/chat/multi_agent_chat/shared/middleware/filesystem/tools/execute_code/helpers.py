"""Sandbox-execution helpers for ``execute_code``.

Dispatches code to the chat thread's sandbox session, with a single retry on
failure: sandboxes die for reasons the model can do nothing about (expiry, a
restarted server), and one silent retry beats surfacing that as a tool error.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from langchain.tools import ToolRuntime

from app.agents.chat.multi_agent_chat.shared.state.filesystem_state import (
    SurfSenseFilesystemState,
)
from app.config import config as app_config
from app.sandbox import ExecResult, SandboxUnavailableError, get_registry

if TYPE_CHECKING:
    from ...middleware import SurfSenseFilesystemMiddleware

logger = logging.getLogger(__name__)

MAX_EXECUTE_TIMEOUT = app_config.SANDBOX_OPERATION_TIMEOUT_SECONDS


async def execute_in_sandbox(
    mw: SurfSenseFilesystemMiddleware,
    command: str,
    runtime: ToolRuntime[None, SurfSenseFilesystemState],
    timeout: int | None,
) -> str:
    """Top-level entry: run *command* as Python, retrying once."""
    assert mw._thread_id is not None
    effective_timeout = timeout or MAX_EXECUTE_TIMEOUT
    try:
        return _format(await _run(mw, command, effective_timeout))
    except SandboxUnavailableError as err:
        return f"Error: {err}"
    except TimeoutError:
        # ponytail: we stop waiting, the cell does not stop running — it holds
        # the kernel until the sandbox expires. Upgrade path is an interrupt
        # call on the execution id once the SDK exposes one for kernel runs.
        return (
            f"Error: execution exceeded {effective_timeout}s and was "
            "abandoned. The interpreter may still be busy; simplify the code."
        )
    except Exception as first_err:
        logger.warning(
            "Sandbox execute failed for thread %s, retrying: %s",
            mw._thread_id,
            first_err,
        )
        try:
            # Terminate rather than evict: a session that failed mid-execution
            # may have a wedged kernel, and reconnecting would inherit it.
            registry = await get_registry()
            await registry.terminate(mw._thread_id)
            return _format(await _run(mw, command, effective_timeout))
        except Exception:
            logger.exception("Sandbox retry also failed for thread %s", mw._thread_id)
            return "Error: Code execution is temporarily unavailable. Please try again."


async def _run(
    mw: SurfSenseFilesystemMiddleware, code: str, timeout: int
) -> ExecResult:
    registry = await get_registry()
    # Without a workspace every such thread would share one cap bucket and
    # block each other, so an unknown workspace gets a bucket of its own.
    workspace_id = mw._workspace_id if mw._workspace_id is not None else mw._thread_id
    session = await registry.get_session(mw._thread_id, workspace_id)
    return await asyncio.wait_for(
        session.execute(code, language="python"),
        timeout=timeout,
    )


def _format(result: ExecResult) -> str:
    output = (result.output or "").strip()
    if not output and result.ok:
        return (
            "[Code executed successfully but produced no output. "
            "Use print() to display results, then try again.]"
        )
    parts = [result.output]
    status = "succeeded" if result.ok else "failed"
    parts.append(f"\n[Command {status} with exit code {result.exit_code}]")
    if result.truncated:
        parts.append("\n[Output was truncated due to size limits]")
    return "".join(parts)
