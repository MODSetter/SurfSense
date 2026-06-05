"""Cloud-only write namespace policy.

A write is allowed iff it lands under ``/documents/`` OR its basename uses
the ``temp_`` scratch prefix. The anonymous uploaded document is read-only
even when its path is under ``/documents/``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain.tools import ToolRuntime

from app.agents.chat.multi_agent_chat.shared.path_resolver import DOCUMENTS_ROOT
from app.agents.chat.multi_agent_chat.shared.state.filesystem_state import (
    SurfSenseFilesystemState,
)

from ..shared.paths import TEMP_PREFIX, basename
from .mode import is_cloud

if TYPE_CHECKING:
    from .middleware import SurfSenseFilesystemMiddleware


def check_cloud_write_namespace(
    mw: SurfSenseFilesystemMiddleware,
    path: str,
    runtime: ToolRuntime[None, SurfSenseFilesystemState],
) -> str | None:
    """Return an error string if cloud writes to ``path`` are not allowed.

    Order matters:
    1. Reject writes to the anonymous read-only doc.
    2. Allow ``/documents/*``.
    3. Allow ``temp_*`` basename anywhere.
    4. Reject everything else.
    """
    if not is_cloud(mw._filesystem_mode):
        return None
    anon = runtime.state.get("kb_anon_doc") or {}
    if isinstance(anon, dict):
        anon_path = str(anon.get("path") or "")
        if anon_path and anon_path == path:
            return "Error: the anonymous uploaded document is read-only."
    if path.startswith(DOCUMENTS_ROOT + "/") or path == DOCUMENTS_ROOT:
        return None
    if basename(path).startswith(TEMP_PREFIX):
        return None
    return (
        "Error: cloud writes must target /documents/<...> or use a 'temp_' "
        f"basename for scratch (got '{path}')."
    )
