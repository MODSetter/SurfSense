"""``execute_code`` factory: bounds-check timeout, dispatch to the sandbox."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool, StructuredTool

from app.agents.multi_agent_chat.shared.state.filesystem_state import (
    SurfSenseFilesystemState,
)

from ...middleware.async_dispatch import run_async_blocking
from .description import select_description
from .helpers import MAX_EXECUTE_TIMEOUT, execute_in_sandbox

if TYPE_CHECKING:
    from ...middleware import SurfSenseFilesystemMiddleware


def create_execute_code_tool(mw: SurfSenseFilesystemMiddleware) -> BaseTool:
    description = select_description(mw._filesystem_mode)

    def sync_execute_code(
        command: Annotated[str, "Python code to execute. Use print() to see output."],
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
        timeout: Annotated[
            int | None,
            "Optional timeout in seconds.",
        ] = None,
    ) -> str:
        if timeout is not None:
            if timeout < 0:
                return f"Error: timeout must be non-negative, got {timeout}."
            if timeout > MAX_EXECUTE_TIMEOUT:
                return f"Error: timeout {timeout}s exceeds maximum ({MAX_EXECUTE_TIMEOUT}s)."
        return run_async_blocking(execute_in_sandbox(mw, command, runtime, timeout))

    async def async_execute_code(
        command: Annotated[str, "Python code to execute. Use print() to see output."],
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
        timeout: Annotated[
            int | None,
            "Optional timeout in seconds.",
        ] = None,
    ) -> str:
        if timeout is not None:
            if timeout < 0:
                return f"Error: timeout must be non-negative, got {timeout}."
            if timeout > MAX_EXECUTE_TIMEOUT:
                return f"Error: timeout {timeout}s exceeds maximum ({MAX_EXECUTE_TIMEOUT}s)."
        return await execute_in_sandbox(mw, command, runtime, timeout)

    return StructuredTool.from_function(
        name="execute_code",
        description=description,
        func=sync_execute_code,
        coroutine=async_execute_code,
    )
