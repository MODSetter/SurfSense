"""``calendar`` native tools and (empty) permission ruleset.

Tools self-gate via :func:`request_approval` in their bodies, so the
ruleset just falls through to the SurfSense allow-by-default rules.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from app.agents.shared.permissions import Ruleset

from .create_event import create_create_calendar_event_tool
from .delete_event import create_delete_calendar_event_tool
from .search_events import create_search_calendar_events_tool
from .update_event import create_update_calendar_event_tool

NAME = "calendar"

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
        create_search_calendar_events_tool(**common),
        create_create_calendar_event_tool(**common),
        create_update_calendar_event_tool(**common),
        create_delete_calendar_event_tool(**common),
    ]
