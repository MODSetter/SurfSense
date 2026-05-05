from __future__ import annotations

from typing import Any

from app.agents.multi_agent_chat.subagents.shared.permissions import (
    ToolsPermissions,
)

from .create_draft import create_create_gmail_draft_tool
from .read_email import create_read_gmail_email_tool
from .search_emails import create_search_gmail_tool
from .send_email import create_send_gmail_email_tool
from .trash_email import create_trash_gmail_email_tool
from .update_draft import create_update_gmail_draft_tool


def load_tools(
    *, dependencies: dict[str, Any] | None = None, **kwargs: Any
) -> ToolsPermissions:
    d = {**(dependencies or {}), **kwargs}
    common = {
        "db_session": d["db_session"],
        "search_space_id": d["search_space_id"],
        "user_id": d["user_id"],
    }
    search = create_search_gmail_tool(**common)
    read = create_read_gmail_email_tool(**common)
    draft = create_create_gmail_draft_tool(**common)
    send = create_send_gmail_email_tool(**common)
    trash = create_trash_gmail_email_tool(**common)
    updraft = create_update_gmail_draft_tool(**common)
    return {
        "allow": [
            {"name": getattr(search, "name", "") or "", "tool": search},
            {"name": getattr(read, "name", "") or "", "tool": read},
        ],
        "ask": [
            {"name": getattr(draft, "name", "") or "", "tool": draft},
            {"name": getattr(send, "name", "") or "", "tool": send},
            {"name": getattr(trash, "name", "") or "", "tool": trash},
            {"name": getattr(updraft, "name", "") or "", "tool": updraft},
        ],
    }
