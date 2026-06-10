"""Cloud and desktop ``rm`` branches.

Both branches receive an already-resolved + validated absolute path.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from deepagents.backends.protocol import WriteResult
from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from app.agents.chat.multi_agent_chat.shared.middleware.filesystem.backends.kb_postgres import (
    KBPostgresBackend,
)
from app.agents.chat.multi_agent_chat.shared.state.filesystem_state import (
    SurfSenseFilesystemState,
)
from app.agents.chat.multi_agent_chat.shared.state.reducers import _CLEAR
from app.agents.chat.runtime.path_resolver import DOCUMENTS_ROOT

if TYPE_CHECKING:
    from ...middleware import SurfSenseFilesystemMiddleware


async def cloud_rm(
    mw: SurfSenseFilesystemMiddleware,
    runtime: ToolRuntime[None, SurfSenseFilesystemState],
    validated: str,
) -> Command | str:
    """Stage a deletion in cloud mode (commit at end of turn)."""
    if validated in ("/", DOCUMENTS_ROOT):
        return f"Error: refusing to rm '{validated}'."
    if not validated.startswith(DOCUMENTS_ROOT + "/"):
        return (
            f"Error: cloud rm must target a path under /documents/ (got '{validated}')."
        )

    anon = runtime.state.get("kb_anon_doc") or {}
    if isinstance(anon, dict) and str(anon.get("path") or "") == validated:
        return "Error: the anonymous uploaded document is read-only."

    staged_dirs = list(runtime.state.get("staged_dirs") or [])
    if validated in staged_dirs:
        return f"Error: '{validated}' is a directory. Use rmdir for empty directories."
    pending_dir_deletes = list(runtime.state.get("pending_dir_deletes") or [])
    if any(
        isinstance(d, dict) and d.get("path") == validated for d in pending_dir_deletes
    ):
        return f"Error: '{validated}' is already queued for rmdir."

    backend = mw._get_backend(runtime)
    if isinstance(backend, KBPostgresBackend):
        children = await backend.als_info(validated)
        if children:
            return (
                f"Error: '{validated}' is a directory. Use rmdir for empty directories."
            )

    pending_deletes = list(runtime.state.get("pending_deletes") or [])
    if any(isinstance(d, dict) and d.get("path") == validated for d in pending_deletes):
        return f"'{validated}' is already queued for deletion."

    files_state = runtime.state.get("files") or {}
    doc_id_by_path = runtime.state.get("doc_id_by_path") or {}
    resolved_doc_id: int | None = doc_id_by_path.get(validated)
    if (
        validated not in files_state
        and resolved_doc_id is None
        and isinstance(backend, KBPostgresBackend)
    ):
        loaded = await backend._load_file_data(validated)
        if loaded is None:
            return f"Error: file '{validated}' not found."
        _, resolved_doc_id = loaded

    files_update: dict[str, Any] = {validated: None}
    update: dict[str, Any] = {
        "pending_deletes": [
            {
                "path": validated,
                "tool_call_id": runtime.tool_call_id,
            }
        ],
        "files": files_update,
        "doc_id_by_path": {validated: None},
        "messages": [
            ToolMessage(
                content=(
                    f"Staged delete of '{validated}' (will commit at end of turn)."
                ),
                tool_call_id=runtime.tool_call_id,
            )
        ],
    }

    dirty_paths = list(runtime.state.get("dirty_paths") or [])
    if validated in dirty_paths:
        new_dirty: list[Any] = [_CLEAR]
        for entry in dirty_paths:
            if entry != validated:
                new_dirty.append(entry)
        update["dirty_paths"] = new_dirty
        update["dirty_path_tool_calls"] = {validated: None}

    return Command(update=update)


async def desktop_rm(
    mw: SurfSenseFilesystemMiddleware,
    runtime: ToolRuntime[None, SurfSenseFilesystemState],
    validated: str,
) -> Command | str:
    """Hit disk immediately in desktop mode."""
    backend = mw._get_backend(runtime)
    adelete = getattr(backend, "adelete_file", None)
    if not callable(adelete):
        return "Error: rm is not supported by the active backend."
    res: WriteResult = await adelete(validated)
    if res.error:
        return res.error
    return Command(
        update={
            "files": {validated: None},
            "messages": [
                ToolMessage(
                    content=f"Deleted file '{res.path or validated}'",
                    tool_call_id=runtime.tool_call_id,
                )
            ],
        }
    )
