"""``rm`` factory: resolve + validate the path, then dispatch to cloud / desktop."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from deepagents.backends.utils import validate_path
from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.types import Command

from app.agents.shared.filesystem_state import SurfSenseFilesystemState

from ...middleware.async_dispatch import run_async_blocking
from ...middleware.mode import is_cloud
from ...middleware.path_resolution import resolve_relative
from .description import select_description
from .helpers import cloud_rm, desktop_rm

if TYPE_CHECKING:
    from ...middleware import SurfSenseFilesystemMiddleware


def create_rm_tool(mw: SurfSenseFilesystemMiddleware) -> BaseTool:
    description = select_description(mw._filesystem_mode)

    async def async_rm(
        path: Annotated[
            str,
            "Absolute or relative path to the file to delete.",
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
            return await cloud_rm(mw, runtime, validated)
        return await desktop_rm(mw, runtime, validated)

    def sync_rm(
        path: Annotated[
            str,
            "Absolute or relative path to the file to delete.",
        ],
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
    ) -> Command | str:
        return run_async_blocking(async_rm(path, runtime))

    return StructuredTool.from_function(
        name="rm",
        description=description,
        func=sync_rm,
        coroutine=async_rm,
    )
