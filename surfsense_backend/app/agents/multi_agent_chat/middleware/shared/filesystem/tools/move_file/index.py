"""``move_file`` factory: dispatches cloud (staged) vs desktop (direct disk) moves."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from deepagents.backends.protocol import WriteResult
from deepagents.backends.utils import validate_path
from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.types import Command

from app.agents.new_chat.filesystem_state import SurfSenseFilesystemState

from ...middleware.async_dispatch import run_async_blocking
from ...middleware.mode import is_cloud
from ...middleware.path_resolution import resolve_move_target_path
from .description import select_description
from .helpers import cloud_move_file

if TYPE_CHECKING:
    from ...middleware import SurfSenseFilesystemMiddleware


def create_move_file_tool(mw: SurfSenseFilesystemMiddleware) -> BaseTool:
    description = select_description(mw._filesystem_mode)

    async def async_move_file(
        source_path: Annotated[str, "Absolute or relative source path."],
        destination_path: Annotated[str, "Absolute or relative destination path."],
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
        *,
        overwrite: Annotated[
            bool,
            "If True, replace existing destination. Cloud mode rejects True. Defaults to False.",
        ] = False,
    ) -> Command | str:
        if not source_path.strip() or not destination_path.strip():
            return "Error: source_path and destination_path are required."

        source = resolve_move_target_path(mw, source_path, runtime)
        dest = resolve_move_target_path(mw, destination_path, runtime)
        try:
            validated_source = validate_path(source)
            validated_dest = validate_path(dest)
        except ValueError as exc:
            return f"Error: {exc}"

        if is_cloud(mw._filesystem_mode):
            return await cloud_move_file(
                mw,
                runtime,
                validated_source,
                validated_dest,
                overwrite=overwrite,
            )

        backend = mw._get_backend(runtime)
        res: WriteResult = await backend.amove(
            validated_source, validated_dest, overwrite=overwrite
        )
        if res.error:
            return res.error
        update: dict[str, Any] = {
            "messages": [
                ToolMessage(
                    content=f"Moved '{validated_source}' to '{res.path or validated_dest}'",
                    tool_call_id=runtime.tool_call_id,
                )
            ],
        }
        if res.files_update is not None:
            update["files"] = res.files_update
        return Command(update=update)

    def sync_move_file(
        source_path: Annotated[str, "Absolute or relative source path."],
        destination_path: Annotated[str, "Absolute or relative destination path."],
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
        *,
        overwrite: Annotated[
            bool,
            "If True, replace existing destination. Cloud mode rejects True. Defaults to False.",
        ] = False,
    ) -> Command | str:
        return run_async_blocking(
            async_move_file(source_path, destination_path, runtime, overwrite=overwrite)
        )

    return StructuredTool.from_function(
        name="move_file",
        description=description,
        func=sync_move_file,
        coroutine=async_move_file,
    )
