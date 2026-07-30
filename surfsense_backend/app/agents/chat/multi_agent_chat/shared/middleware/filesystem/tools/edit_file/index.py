"""``edit_file`` factory: lazy-load KB doc, enforce cloud namespace, dispatch to backend."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from deepagents.backends.protocol import EditResult
from deepagents.backends.utils import validate_path
from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.types import Command

from app.agents.chat.multi_agent_chat.shared.middleware.filesystem.backends.kb_postgres import (
    KBPostgresBackend,
)
from app.agents.chat.multi_agent_chat.shared.state.filesystem_state import (
    SurfSenseFilesystemState,
)

from ...middleware.async_dispatch import run_async_blocking
from ...middleware.mode import is_cloud
from ...middleware.namespace_policy import check_cloud_write_namespace
from ...middleware.path_resolution import resolve_relative
from .description import select_description

if TYPE_CHECKING:
    from ...middleware import SurfSenseFilesystemMiddleware


def create_edit_file_tool(mw: SurfSenseFilesystemMiddleware) -> BaseTool:
    description = select_description(mw._filesystem_mode)

    async def async_edit_file(
        file_path: Annotated[
            str,
            "Absolute path to the file to edit. Relative paths resolve against the current cwd.",
        ],
        old_string: Annotated[
            str,
            "Exact text to replace. Must be unique unless replace_all is True.",
        ],
        new_string: Annotated[
            str,
            "Replacement text. Must differ from old_string.",
        ],
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
        *,
        replace_all: Annotated[
            bool,
            "If True, replace all occurrences of old_string. Defaults to False.",
        ] = False,
    ) -> Command | str:
        target = resolve_relative(mw, file_path, runtime)
        try:
            validated = validate_path(target)
        except ValueError as exc:
            return f"Error: {exc}"

        namespace_error = check_cloud_write_namespace(mw, validated, runtime)
        if namespace_error:
            return namespace_error

        backend = mw._get_backend(runtime)
        files_state = runtime.state.get("files") or {}
        doc_id_to_attach: int | None = None

        if (
            is_cloud(mw._filesystem_mode)
            and validated not in files_state
            and isinstance(backend, KBPostgresBackend)
        ):
            loaded = await backend._load_file_data(validated)
            if loaded is None:
                return f"Error: File '{validated}' not found"
            _, doc_id_to_attach = loaded

        res: EditResult = await backend.aedit(
            validated, old_string, new_string, replace_all=replace_all
        )
        if res.error:
            return res.error

        path = res.path or validated
        files_update = res.files_update or {}
        update: dict[str, Any] = {
            "files": files_update,
            "messages": [
                ToolMessage(
                    content=(
                        f"Successfully replaced {res.occurrences} instance(s) "
                        f"of the string in '{path}'"
                    ),
                    tool_call_id=runtime.tool_call_id,
                )
            ],
        }
        if is_cloud(mw._filesystem_mode):
            update["dirty_paths"] = [path]
            update["dirty_path_tool_calls"] = {path: runtime.tool_call_id}
            if doc_id_to_attach is not None:
                update["doc_id_by_path"] = {path: doc_id_to_attach}
        return Command(update=update)

    def sync_edit_file(
        file_path: Annotated[
            str,
            "Absolute path to the file to edit. Relative paths resolve against the current cwd.",
        ],
        old_string: Annotated[
            str,
            "Exact text to replace. Must be unique unless replace_all is True.",
        ],
        new_string: Annotated[
            str,
            "Replacement text. Must differ from old_string.",
        ],
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
        *,
        replace_all: Annotated[
            bool,
            "If True, replace all occurrences of old_string. Defaults to False.",
        ] = False,
    ) -> Command | str:
        return run_async_blocking(
            async_edit_file(
                file_path, old_string, new_string, runtime, replace_all=replace_all
            )
        )

    return StructuredTool.from_function(
        name="edit_file",
        description=description,
        func=sync_edit_file,
        coroutine=async_edit_file,
    )
