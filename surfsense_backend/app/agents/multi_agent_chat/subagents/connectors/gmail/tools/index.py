"""``gmail`` native tools and (empty) permission ruleset.

Tools self-gate via :func:`request_approval` in their bodies.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from app.agents.shared.permissions import Ruleset

from .create_draft import create_create_gmail_draft_tool
from .read_email import create_read_gmail_email_tool
from .search_emails import create_search_gmail_tool
from .send_email import create_send_gmail_email_tool
from .trash_email import create_trash_gmail_email_tool
from .update_draft import create_update_gmail_draft_tool

NAME = "gmail"

RULESET = Ruleset(origin=NAME, rules=[])


def load_tools(
    *, dependencies: dict[str, Any] | None = None, **kwargs: Any
) -> list[BaseTool]:
    d = {**(dependencies or {}), **kwargs}
    common = {
        "db_session": d["db_session"],
        "search_space_id": d["search_space_id"],
        "user_id": d["user_id"],
    }
    return [
        create_search_gmail_tool(**common),
        create_read_gmail_email_tool(**common),
        create_create_gmail_draft_tool(**common),
        create_send_gmail_email_tool(**common),
        create_trash_gmail_email_tool(**common),
        create_update_gmail_draft_tool(**common),
    ]
