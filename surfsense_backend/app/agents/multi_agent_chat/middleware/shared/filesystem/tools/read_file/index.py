"""``read_file`` factory: state-cache lookup, then lazy KB load, then disk read."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from deepagents.backends.utils import format_read_response, validate_path
from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.types import Command

from app.agents.new_chat.filesystem_state import SurfSenseFilesystemState
from app.agents.new_chat.middleware.kb_postgres_backend import KBPostgresBackend

from ...middleware.async_dispatch import run_async_blocking
from ...middleware.path_resolution import resolve_relative
from .description import select_description

if TYPE_CHECKING:
    from ...middleware import SurfSenseFilesystemMiddleware


def create_read_file_tool(mw: "SurfSenseFilesystemMiddleware") -> BaseTool:
    description = select_description(mw._filesystem_mode)

    async def async_read_file(
        file_path: Annotated[
            str,
            "Absolute path to the file to read. Relative paths resolve against the current cwd.",
        ],
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
        offset: Annotated[
            int,
            "Line number to start reading from (0-indexed).",
        ] = 0,
        limit: Annotated[
            int,
            "Maximum number of lines to read.",
        ] = 100,
    ) -> Command | str:
        target = resolve_relative(mw, file_path, runtime)
        try:
            validated = validate_path(target)
        except ValueError as exc:
            return f"Error: {exc}"

        files = runtime.state.get("files") or {}
        if validated in files:
            return format_read_response(files[validated], offset, limit)

        backend = mw._get_backend(runtime)
        if isinstance(backend, KBPostgresBackend):
            loaded = await backend._load_file_data(validated)
            if loaded is None:
                return f"Error: File '{validated}' not found"
            file_data, doc_id = loaded
            rendered = format_read_response(file_data, offset, limit)
            update: dict[str, Any] = {
                "files": {validated: file_data},
                "messages": [
                    ToolMessage(
                        content=rendered,
                        tool_call_id=runtime.tool_call_id,
                    )
                ],
            }
            if doc_id is not None:
                update["doc_id_by_path"] = {validated: doc_id}
            return Command(update=update)

        try:
            rendered = await backend.aread(validated, offset=offset, limit=limit)
        except Exception as exc:  # pragma: no cover - defensive
            return f"Error: {exc}"
        return rendered

    def sync_read_file(
        file_path: Annotated[
            str,
            "Absolute path to the file to read. Relative paths resolve against the current cwd.",
        ],
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
        offset: Annotated[
            int,
            "Line number to start reading from (0-indexed).",
        ] = 0,
        limit: Annotated[
            int,
            "Maximum number of lines to read.",
        ] = 100,
    ) -> Command | str:
        return run_async_blocking(
            async_read_file(file_path, runtime, offset, limit)
        )

    return StructuredTool.from_function(
        name="read_file",
        description=description,
        func=sync_read_file,
        coroutine=async_read_file,
    )
