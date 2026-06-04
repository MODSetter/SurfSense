"""``luma`` native tools and (empty) permission ruleset.

Tools self-gate via :func:`request_approval` in their bodies.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from app.agents.shared.permissions import Ruleset

from .create_event import create_create_luma_event_tool
from .list_events import create_list_luma_events_tool
from .read_event import create_read_luma_event_tool

NAME = "luma"

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
        create_list_luma_events_tool(**common),
        create_read_luma_event_tool(**common),
        create_create_luma_event_tool(**common),
    ]
