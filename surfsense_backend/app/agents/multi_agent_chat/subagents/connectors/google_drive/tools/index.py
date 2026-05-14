"""``google_drive`` native tools and (empty) permission ruleset.

Tools self-gate via :func:`request_approval` in their bodies.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from app.agents.new_chat.permissions import Ruleset

from .create_file import create_create_google_drive_file_tool
from .trash_file import create_delete_google_drive_file_tool

NAME = "google_drive"

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
        create_create_google_drive_file_tool(**common),
        create_delete_google_drive_file_tool(**common),
    ]
