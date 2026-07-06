"""``mcp_discovery`` tools + metadata-derived permission ruleset.

Assembles the connected-apps toolset from three sources:

1. **Interim native tools** — Gmail + Calendar factories (kept until Google
   Workspace MCP is GA). Loaded only when a matching connector row exists.
   They self-gate writes via ``request_approval`` in their bodies, so they
   get no ruleset entries.
2. **``get_connected_accounts``** — read-only discovery helper.
3. **MCP tools** — injected at runtime by the factory (already
   collision-resolved). Loaded with ``bypass_internal_hitl=True``, so their
   *only* gate is this subagent's :class:`PermissionMiddleware`; the ruleset
   is derived from each tool's ``metadata['hitl']`` flag.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from app.agents.chat.multi_agent_chat.shared.permissions import Rule, Ruleset

from .calendar.index import load_tools as load_calendar_tools
from .get_connected_accounts import create_get_connected_accounts_tool
from .gmail.index import load_tools as load_gmail_tools

NAME = "mcp_discovery"

# Searchable-token gate for each interim native app (Composio types map to
# these same tokens in connector_searchable_types).
_GMAIL_TOKEN = "GOOGLE_GMAIL_CONNECTOR"
_CALENDAR_TOKEN = "GOOGLE_CALENDAR_CONNECTOR"


def _interim_native_tools(dependencies: dict[str, Any]) -> list[BaseTool]:
    """Gmail/Calendar native tools, loaded only for connected accounts."""
    available = set(dependencies.get("available_connectors") or [])
    if not available & {_GMAIL_TOKEN, _CALENDAR_TOKEN}:
        return []
    # These factories require an authenticated user + db session.
    if not dependencies.get("db_session") or not dependencies.get("user_id"):
        return []

    tools: list[BaseTool] = []
    if _GMAIL_TOKEN in available:
        tools.extend(load_gmail_tools(dependencies=dependencies))
    if _CALENDAR_TOKEN in available:
        tools.extend(load_calendar_tools(dependencies=dependencies))
    return tools


def load_tools(
    *,
    dependencies: dict[str, Any] | None = None,
    mcp_tools: list[BaseTool] | None = None,
    **kwargs: Any,
) -> list[BaseTool]:
    """Interim native tools + ``get_connected_accounts`` + injected MCP tools."""
    d = {**(dependencies or {}), **kwargs}
    return [
        *_interim_native_tools(d),
        create_get_connected_accounts_tool(workspace_id=d["workspace_id"]),
        *(mcp_tools or []),
    ]


def _is_mcp_tool(tool: BaseTool) -> bool:
    meta = getattr(tool, "metadata", None) or {}
    return "mcp_transport" in meta


def build_ruleset(tools: list[BaseTool]) -> Ruleset:
    """Derive the approval ruleset from tool metadata.

    Only MCP tools get rules: read-only ones (``metadata['hitl'] is False``)
    are ``allow``, every other MCP tool is ``ask``. Native interim tools and
    ``get_connected_accounts`` carry no rules and fall through to the
    ``allow */*`` default (Gmail/Calendar self-gate writes internally;
    ``get_connected_accounts`` is read-only).
    """
    rules: list[Rule] = []
    for tool in tools:
        if not _is_mcp_tool(tool):
            continue
        meta = getattr(tool, "metadata", None) or {}
        action = "allow" if meta.get("hitl") is False else "ask"
        rules.append(Rule(permission=tool.name, pattern="*", action=action))
    return Ruleset(origin=NAME, rules=rules)
