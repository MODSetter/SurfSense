"""Cloud-mode move helper: stages source/dest into pending_moves + files."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from app.agents.multi_agent_chat.shared.middleware.filesystem.backends.kb_postgres import (
    KBPostgresBackend,
)
from app.agents.multi_agent_chat.shared.state.filesystem_state import (
    SurfSenseFilesystemState,
)
from app.agents.multi_agent_chat.shared.state.reducers import _CLEAR
from app.agents.shared.path_resolver import DOCUMENTS_ROOT

if TYPE_CHECKING:
    from ...middleware import SurfSenseFilesystemMiddleware


async def cloud_move_file(
    mw: SurfSenseFilesystemMiddleware,
    runtime: ToolRuntime[None, SurfSenseFilesystemState],
    source: str,
    dest: str,
    *,
    overwrite: bool,
) -> Command | str:
    """Stage a source/dest move in cloud mode (commit at end of turn)."""
    backend = mw._get_backend(runtime)
    if not isinstance(backend, KBPostgresBackend):
        return "Error: cloud move requires KBPostgresBackend."

    if source == dest:
        return f"Moved '{source}' to '{dest}' (no-op)"
    if overwrite:
        return (
            "Error: overwrite=True is not supported in cloud mode. Move/edit "
            "the destination doc explicitly first."
        )
    if not source.startswith(DOCUMENTS_ROOT + "/"):
        return (
            f"Error: cloud move_file source must be under /documents/ (got '{source}')."
        )
    if not dest.startswith(DOCUMENTS_ROOT + "/"):
        return (
            "Error: cloud move_file destination must be under /documents/ (got "
            f"'{dest}')."
        )
    anon = runtime.state.get("kb_anon_doc") or {}
    if isinstance(anon, dict):
        anon_path = str(anon.get("path") or "")
        if anon_path and (anon_path in (source, dest)):
            return "Error: the anonymous uploaded document is read-only."

    files = runtime.state.get("files") or {}
    doc_id_by_path = runtime.state.get("doc_id_by_path") or {}
    pending_moves = list(runtime.state.get("pending_moves") or [])

    if dest in files:
        return f"Error: destination '{dest}' already exists."
    if any(move.get("dest") == dest for move in pending_moves):
        return f"Error: destination '{dest}' already exists."
    if dest != source:
        existing_dest = await backend._load_file_data(dest)
        if existing_dest is not None:
            return f"Error: destination '{dest}' already exists."

    source_file_data = files.get(source)
    source_doc_id = doc_id_by_path.get(source)
    if source_file_data is None:
        loaded = await backend._load_file_data(source)
        if loaded is None:
            return f"Error: source '{source}' not found."
        source_file_data, loaded_doc_id = loaded
        if source_doc_id is None:
            source_doc_id = loaded_doc_id

    files_update: dict[str, Any] = {source: None, dest: source_file_data}
    update: dict[str, Any] = {
        "files": files_update,
        "pending_moves": [
            {
                "source": source,
                "dest": dest,
                "overwrite": False,
                "tool_call_id": runtime.tool_call_id,
            }
        ],
        "messages": [
            ToolMessage(
                content=(f"Moved '{source}' to '{dest}' (will commit at end of turn)."),
                tool_call_id=runtime.tool_call_id,
            )
        ],
    }

    doc_id_update: dict[str, int | None] = {source: None}
    if source_doc_id is not None:
        doc_id_update[dest] = source_doc_id
    update["doc_id_by_path"] = doc_id_update

    dirty_paths = list(runtime.state.get("dirty_paths") or [])
    if source in dirty_paths:
        new_dirty: list[Any] = [_CLEAR]
        for entry in dirty_paths:
            new_dirty.append(dest if entry == source else entry)
        update["dirty_paths"] = new_dirty
    return Command(update=update)
