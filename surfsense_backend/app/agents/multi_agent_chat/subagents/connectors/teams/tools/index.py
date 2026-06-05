"""``teams`` native tools and (empty) permission ruleset.

Tools self-gate via :func:`request_approval` in their bodies.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from app.agents.multi_agent_chat.shared.permissions import Ruleset

from .list_channels import create_list_teams_channels_tool
from .read_messages import create_read_teams_messages_tool
from .send_message import create_send_teams_message_tool

NAME = "teams"

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
        create_list_teams_channels_tool(**common),
        create_read_teams_messages_tool(**common),
        create_send_teams_message_tool(**common),
    ]
