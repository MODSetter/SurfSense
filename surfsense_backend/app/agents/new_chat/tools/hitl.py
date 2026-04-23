"""Unified HITL (Human-in-the-Loop) approval utility.

Provides a single ``request_approval()`` function that encapsulates the
interrupt payload creation, decision parsing, and parameter merging logic
shared by every sensitive tool (native connectors and MCP tools alike).

Usage inside a tool::

    from app.agents.new_chat.tools.hitl import request_approval

    result = request_approval(
        action_type="gmail_email_send",
        tool_name="send_gmail_email",
        params={"to": to, "subject": subject, "body": body},
        context=context,
    )
    if result.rejected:
        return {"status": "rejected", "message": "User declined."}
    # result.params contains the final (possibly edited) parameters
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from langgraph.types import interrupt

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class HITLResult:
    """Outcome of a human-in-the-loop approval request."""

    rejected: bool
    decision_type: str
    params: dict[str, Any] = field(default_factory=dict)


def _parse_decision(approval: Any) -> tuple[str, dict[str, Any]]:
    """Extract the first valid decision and its edited parameters.

    Returns:
        (decision_type, edited_params) where *decision_type* is one of
        ``"approve"``, ``"edit"``, or ``"reject"`` and *edited_params* is
        the dict of user-modified arguments (empty when there are none).

    Raises:
        ValueError: when no usable decision dict can be found.
    """
    decisions_raw = approval.get("decisions", []) if isinstance(approval, dict) else []
    decisions = decisions_raw if isinstance(decisions_raw, list) else [decisions_raw]
    decisions = [d for d in decisions if isinstance(d, dict)]

    if not decisions:
        raise ValueError("No approval decision received")

    decision = decisions[0]
    decision_type: str = (
        decision.get("type") or decision.get("decision_type") or "approve"
    )

    edited_params: dict[str, Any] = {}
    edited_action = decision.get("edited_action")
    if isinstance(edited_action, dict):
        edited_args = edited_action.get("args")
        if isinstance(edited_args, dict):
            edited_params = edited_args
    elif isinstance(decision.get("args"), dict):
        edited_params = decision["args"]

    return decision_type, edited_params


def request_approval(
    *,
    action_type: str,
    tool_name: str,
    params: dict[str, Any],
    context: dict[str, Any] | None = None,
    trusted_tools: list[str] | None = None,
) -> HITLResult:
    """Pause the graph for user approval and return the decision.

    This is a **synchronous** helper (not ``async``) because
    ``langgraph.types.interrupt`` is itself synchronous — it raises a
    ``GraphInterrupt`` exception that the LangGraph runtime catches.

    Parameters
    ----------
    action_type:
        A label that the frontend uses to select the correct approval card
        (e.g. ``"gmail_email_send"``, ``"mcp_tool_call"``).
    tool_name:
        The registered LangChain tool name (e.g. ``"send_gmail_email"``).
    params:
        The original tool arguments.  These are shown in the approval card
        and used as defaults when the user does not edit anything.
    context:
        Rich metadata from a ``*ToolMetadataService`` (accounts, folders,
        labels, etc.).  For MCP tools this can hold the server name and
        tool description.
    trusted_tools:
        An allow-list of tool names the user has previously marked as
        "Always Allow".  If *tool_name* appears in this list, HITL is
        skipped and the tool executes immediately.

    Returns
    -------
    HITLResult
        ``result.rejected`` is ``True`` when the user chose to deny the
        action.  Otherwise ``result.params`` contains the final parameter
        dict — either the originals or the user-edited version merged on
        top.
    """
    if trusted_tools and tool_name in trusted_tools:
        logger.info("Tool '%s' is user-trusted — skipping HITL", tool_name)
        return HITLResult(rejected=False, decision_type="trusted", params=dict(params))

    approval = interrupt(
        {
            "type": action_type,
            "action": {"tool": tool_name, "params": params},
            "context": context or {},
        }
    )

    try:
        decision_type, edited_params = _parse_decision(approval)
    except ValueError:
        logger.warning("No approval decision received for %s — rejecting for safety", tool_name)
        return HITLResult(rejected=True, decision_type="error", params=params)

    logger.info("User decision for %s: %s", tool_name, decision_type)

    if decision_type == "reject":
        return HITLResult(rejected=True, decision_type="reject", params=params)

    final_params = {**params, **edited_params} if edited_params else dict(params)
    return HITLResult(rejected=False, decision_type=decision_type, params=final_params)
