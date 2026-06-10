"""``pwd`` factory: read the cwd from state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool, StructuredTool

from app.agents.chat.multi_agent_chat.shared.state.filesystem_state import (
    SurfSenseFilesystemState,
)

from ...middleware.path_resolution import current_cwd
from .description import select_description

if TYPE_CHECKING:
    from ...middleware import SurfSenseFilesystemMiddleware


def create_pwd_tool(mw: SurfSenseFilesystemMiddleware) -> BaseTool:
    description = select_description(mw._filesystem_mode)

    def sync_pwd(
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
    ) -> str:
        return current_cwd(mw, runtime)

    async def async_pwd(
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
    ) -> str:
        return current_cwd(mw, runtime)

    return StructuredTool.from_function(
        name="pwd",
        description=description,
        func=sync_pwd,
        coroutine=async_pwd,
    )
