"""``rmdir`` factory: resolve + validate the path, then dispatch to cloud / desktop."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from deepagents.backends.utils import validate_path
from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.types import Command

from app.agents.chat.multi_agent_chat.shared.state.filesystem_state import (
    SurfSenseFilesystemState,
)

from ...middleware.async_dispatch import run_async_blocking
from ...middleware.mode import is_cloud
from ...middleware.path_resolution import resolve_relative
from .description import select_description
from .helpers import cloud_rmdir, desktop_rmdir

if TYPE_CHECKING:
    from ...middleware import SurfSenseFilesystemMiddleware


def create_rmdir_tool(mw: SurfSenseFilesystemMiddleware) -> BaseTool:
    description = select_description(mw._filesystem_mode)

    async def async_rmdir(
        path: Annotated[
            str,
            "Absolute or relative path of the empty directory to delete.",
        ],
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
    ) -> Command | str:
        if not path or not path.strip():
            return "Error: path is required."

        target = resolve_relative(mw, path, runtime)
        try:
            validated = validate_path(target)
        except ValueError as exc:
            return f"Error: {exc}"

        if is_cloud(mw._filesystem_mode):
            return await cloud_rmdir(mw, runtime, validated)
        return await desktop_rmdir(mw, runtime, validated)

    def sync_rmdir(
        path: Annotated[
            str,
            "Absolute or relative path of the empty directory to delete.",
        ],
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
    ) -> Command | str:
        return run_async_blocking(async_rmdir(path, runtime))

    return StructuredTool.from_function(
        name="rmdir",
        description=description,
        func=sync_rmdir,
        coroutine=async_rmdir,
    )
