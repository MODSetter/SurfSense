"""``mkdir`` factory: cloud stages for end-of-turn; desktop hits disk immediately."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Annotated, Any

from deepagents.backends.utils import validate_path
from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.types import Command

from app.agents.multi_agent_chat.shared.path_resolver import DOCUMENTS_ROOT
from app.agents.multi_agent_chat.shared.state.filesystem_state import (
    SurfSenseFilesystemState,
)

from ...middleware.async_dispatch import run_async_blocking
from ...middleware.mode import is_cloud
from ...middleware.path_resolution import resolve_relative
from .description import select_description

if TYPE_CHECKING:
    from ...middleware import SurfSenseFilesystemMiddleware


def create_mkdir_tool(mw: SurfSenseFilesystemMiddleware) -> BaseTool:
    description = select_description(mw._filesystem_mode)

    async def async_mkdir(
        path: Annotated[str, "Absolute or relative directory path to create."],
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
    ) -> Command | str:
        target = resolve_relative(mw, path, runtime)
        try:
            validated = validate_path(target)
        except ValueError as exc:
            return f"Error: {exc}"

        if is_cloud(mw._filesystem_mode):
            if not (
                validated.startswith(DOCUMENTS_ROOT + "/")
                or validated == DOCUMENTS_ROOT
            ):
                return (
                    "Error: cloud mkdir must target a path under /documents/ "
                    f"(got '{validated}')."
                )
            return Command(
                update={
                    "staged_dirs": [validated],
                    "staged_dir_tool_calls": {
                        validated: runtime.tool_call_id,
                    },
                    "messages": [
                        ToolMessage(
                            content=(
                                f"Staged directory '{validated}' (will be created "
                                "at end of turn)."
                            ),
                            tool_call_id=runtime.tool_call_id,
                        )
                    ],
                }
            )

        backend = mw._get_backend(runtime)
        local_method = getattr(backend, "amkdir", None) or getattr(
            backend, "mkdir", None
        )
        if callable(local_method):
            try:
                res: Any = local_method(validated, parents=True, exist_ok=True)
                if asyncio.iscoroutine(res):
                    await res
            except TypeError:
                res = local_method(validated)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as exc:  # pragma: no cover
                return f"Error: {exc}"
        return f"Created directory {validated}"

    def sync_mkdir(
        path: Annotated[str, "Absolute or relative directory path to create."],
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
    ) -> Command | str:
        return run_async_blocking(async_mkdir(path, runtime))

    return StructuredTool.from_function(
        name="mkdir",
        description=description,
        func=sync_mkdir,
        coroutine=async_mkdir,
    )
