"""A plugin step's result kept as a note, the same call with the same inputs updating the note it made."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.agent.agent_threads.steps import tool_output
from modules.agent.plugin_tools.turn_plugins import opencode_tool_name
from modules.chat.models import ChatThread
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.plugins.installed.models import InstalledPlugin, PluginTool
from modules.source_roots.managed_root import ensure_managed_root


def save_result(
    session: Session, thread: ChatThread, part: dict[str, Any]
) -> tuple[Document, bool]:
    """The note, and whether it is new; `part` is the call as the engine stored it."""
    found = _plugin_tool(session, str(part.get("name")))
    if found is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "only a connected plugin's step is saved"
        )
    plugin, tool = found
    state = part.get("state") or {}
    if state.get("status") != "completed":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "only a finished step's result is saved"
        )
    call = hashlib.sha256(
        json.dumps(
            [plugin.id, tool.tool, state.get("input") or {}], sort_keys=True
        ).encode()
    ).hexdigest()
    metadata = {
        "plugin_id": plugin.id,
        "tool": tool.tool,
        "thread_id": thread.id,
        "step_id": part["id"],
        "fetched_at": datetime.now(UTC).isoformat(),
        "plugin_call": call,
    }
    content = tool_output(state) or ""
    note = session.scalars(
        select(Document).where(
            Document.workspace_id == thread.workspace_id,
            Document.document_type == DocumentType.NOTE,
            func.json_extract(Document.document_metadata, "$.plugin_call") == call,
        )
    ).first()
    if note is not None:
        note.content = content
        note.document_metadata = metadata
        note.status = DocumentStatus.PENDING
        session.flush()
        return note, False
    note = Document(
        workspace_id=thread.workspace_id,
        title=f"{plugin.entry.get('name', plugin.id)}: {tool.title or tool.tool}",
        document_type=DocumentType.NOTE,
        content=content,
        document_metadata=metadata,
        folder_id=ensure_managed_root(session, thread.workspace_id).id,
    )
    session.add(note)
    session.flush()
    return note, True


def _plugin_tool(
    session: Session, step_tool: str
) -> tuple[InstalledPlugin, PluginTool] | None:
    """The plugin and tool opencode named `<plugin>_<tool>`."""
    rows = session.execute(
        select(InstalledPlugin, PluginTool).join(
            PluginTool, PluginTool.plugin_id == InstalledPlugin.id
        )
    )
    for plugin, tool in rows:
        if opencode_tool_name(plugin.id, tool.tool) == step_tool:
            return plugin, tool
    return None
