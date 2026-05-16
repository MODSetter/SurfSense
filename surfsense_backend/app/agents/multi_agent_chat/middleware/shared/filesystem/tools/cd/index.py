"""``cd`` factory: resolve target, verify existence (staged + on-disk), update cwd."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from deepagents.backends.utils import validate_path
from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.types import Command

from app.agents.new_chat.filesystem_state import SurfSenseFilesystemState
from app.agents.new_chat.path_resolver import DOCUMENTS_ROOT

from ...middleware.async_dispatch import run_async_blocking
from ...middleware.path_resolution import resolve_relative
from .description import select_description

if TYPE_CHECKING:
    from ...middleware import SurfSenseFilesystemMiddleware


def create_cd_tool(mw: SurfSenseFilesystemMiddleware) -> BaseTool:
    description = select_description(mw._filesystem_mode)

    async def async_cd(
        path: Annotated[str, "Absolute or relative directory path to switch into."],
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
    ) -> Command | str:
        target = resolve_relative(mw, path, runtime)
        try:
            validated = validate_path(target)
        except ValueError as exc:
            return f"Error: {exc}"

        backend = mw._get_backend(runtime)
        try:
            infos = await backend.als_info(validated)
        except Exception as exc:  # pragma: no cover - defensive
            return f"Error: {exc}"
        staged_dirs = list(runtime.state.get("staged_dirs") or [])
        files = runtime.state.get("files") or {}
        cwd_exists = (
            bool(infos)
            or validated in staged_dirs
            or any(p == validated for p in files)
            or any(
                isinstance(p, str) and p.startswith(validated.rstrip("/") + "/")
                for p in files
            )
            or validated == "/"
            or validated == DOCUMENTS_ROOT
        )
        if not cwd_exists:
            return f"Error: directory '{validated}' not found."
        return Command(
            update={
                "cwd": validated,
                "messages": [
                    ToolMessage(
                        content=f"cwd changed to {validated}",
                        tool_call_id=runtime.tool_call_id,
                    )
                ],
            }
        )

    def sync_cd(
        path: Annotated[str, "Absolute or relative directory path to switch into."],
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
    ) -> Command | str:
        return run_async_blocking(async_cd(path, runtime))

    return StructuredTool.from_function(
        name="cd",
        description=description,
        func=sync_cd,
        coroutine=async_cd,
    )
