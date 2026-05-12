"""``write_file`` factory: resolve target, enforce cloud namespace, dispatch to backend."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from deepagents.backends.protocol import WriteResult
from deepagents.backends.utils import create_file_data, validate_path
from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.types import Command

from app.agents.new_chat.filesystem_state import SurfSenseFilesystemState

from ...middleware.async_dispatch import run_async_blocking
from ...middleware.mode import is_cloud
from ...middleware.namespace_policy import check_cloud_write_namespace
from ...middleware.path_resolution import resolve_write_target_path
from .description import select_description

if TYPE_CHECKING:
    from ...middleware import SurfSenseFilesystemMiddleware


def create_write_file_tool(mw: "SurfSenseFilesystemMiddleware") -> BaseTool:
    description = select_description(mw._filesystem_mode)

    async def async_write_file(
        file_path: Annotated[
            str,
            "Absolute path where the file should be created. Relative paths resolve against the current cwd.",
        ],
        content: Annotated[str, "Text content to write to the file."],
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
    ) -> Command | str:
        target = resolve_write_target_path(mw, file_path, runtime)
        try:
            validated = validate_path(target)
        except ValueError as exc:
            return f"Error: {exc}"

        namespace_error = check_cloud_write_namespace(mw, validated, runtime)
        if namespace_error:
            return namespace_error

        backend = mw._get_backend(runtime)
        res: WriteResult = await backend.awrite(validated, content)
        if res.error:
            return res.error

        path = res.path or validated
        files_update = res.files_update or {path: create_file_data(content)}
        update: dict[str, Any] = {
            "files": files_update,
            "messages": [
                ToolMessage(
                    content=f"Updated file {path}",
                    tool_call_id=runtime.tool_call_id,
                )
            ],
        }
        if is_cloud(mw._filesystem_mode):
            update["dirty_paths"] = [path]
            update["dirty_path_tool_calls"] = {path: runtime.tool_call_id}
        return Command(update=update)

    def sync_write_file(
        file_path: Annotated[
            str,
            "Absolute path where the file should be created. Relative paths resolve against the current cwd.",
        ],
        content: Annotated[str, "Text content to write to the file."],
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
    ) -> Command | str:
        return run_async_blocking(
            async_write_file(file_path, content, runtime)
        )

    return StructuredTool.from_function(
        name="write_file",
        description=description,
        func=sync_write_file,
        coroutine=async_write_file,
    )
