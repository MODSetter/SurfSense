"""Cloud and desktop ``rmdir`` branches.

Both branches receive an already-resolved + validated absolute path.
"""

from __future__ import annotations

import posixpath
from typing import TYPE_CHECKING

from deepagents.backends.protocol import WriteResult
from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from app.agents.shared.filesystem_state import SurfSenseFilesystemState
from app.agents.new_chat.middleware.kb_postgres_backend import KBPostgresBackend
from app.agents.shared.path_resolver import DOCUMENTS_ROOT
from app.agents.shared.state_reducers import _CLEAR

from ...middleware.path_resolution import current_cwd
from ...shared.paths import is_ancestor_of

if TYPE_CHECKING:
    from ...middleware import SurfSenseFilesystemMiddleware


async def cloud_rmdir(
    mw: SurfSenseFilesystemMiddleware,
    runtime: ToolRuntime[None, SurfSenseFilesystemState],
    validated: str,
) -> Command | str:
    """Stage an empty-folder delete in cloud mode (commit at end of turn)."""
    if validated in ("/", DOCUMENTS_ROOT):
        return f"Error: refusing to rmdir '{validated}'."
    if not validated.startswith(DOCUMENTS_ROOT + "/"):
        return (
            "Error: cloud rmdir must target a path under /documents/ "
            f"(got '{validated}')."
        )

    cwd = current_cwd(mw, runtime)
    if validated == cwd or is_ancestor_of(validated, cwd):
        return (
            f"Error: cannot rmdir '{validated}' because the current "
            "cwd is at or under it. cd out first."
        )

    staged_dirs = list(runtime.state.get("staged_dirs") or [])
    pending_dir_deletes = list(runtime.state.get("pending_dir_deletes") or [])
    if any(
        isinstance(d, dict) and d.get("path") == validated for d in pending_dir_deletes
    ):
        return f"'{validated}' is already queued for deletion."

    backend = mw._get_backend(runtime)

    exists_in_staged = validated in staged_dirs
    children: list = []
    if isinstance(backend, KBPostgresBackend):
        children = list(await backend.als_info(validated))

    if isinstance(backend, KBPostgresBackend) and not children and not exists_in_staged:
        loaded = await backend._load_file_data(validated)
        if loaded is not None:
            return f"Error: '{validated}' is a file. Use rm to delete files."
        parent = posixpath.dirname(validated) or "/"
        parent_listing = await backend.als_info(parent)
        parent_has_dir = any(
            info.get("path") == validated and info.get("is_dir")
            for info in parent_listing
        )
        if not parent_has_dir:
            return f"Error: directory '{validated}' not found."

    if children:
        return f"Error: directory '{validated}' is not empty. Remove contents first."

    if exists_in_staged:
        rest = [d for d in staged_dirs if d != validated]
        return Command(
            update={
                "staged_dirs": [_CLEAR, *rest],
                "staged_dir_tool_calls": {validated: None},
                "messages": [
                    ToolMessage(
                        content=(f"Un-staged directory '{validated}'."),
                        tool_call_id=runtime.tool_call_id,
                    )
                ],
            }
        )

    return Command(
        update={
            "pending_dir_deletes": [
                {
                    "path": validated,
                    "tool_call_id": runtime.tool_call_id,
                }
            ],
            "messages": [
                ToolMessage(
                    content=(
                        f"Staged rmdir of '{validated}' (will commit at end of turn)."
                    ),
                    tool_call_id=runtime.tool_call_id,
                )
            ],
        }
    )


async def desktop_rmdir(
    mw: SurfSenseFilesystemMiddleware,
    runtime: ToolRuntime[None, SurfSenseFilesystemState],
    validated: str,
) -> Command | str:
    """Hit disk immediately in desktop mode."""
    backend = mw._get_backend(runtime)
    armdir = getattr(backend, "armdir", None)
    if not callable(armdir):
        return "Error: rmdir is not supported by the active backend."
    res: WriteResult = await armdir(validated)
    if res.error:
        return res.error
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=f"Deleted directory '{res.path or validated}'",
                    tool_call_id=runtime.tool_call_id,
                )
            ],
        }
    )
