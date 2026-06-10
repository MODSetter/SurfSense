"""Self-gated approval entry point — pause from inside a tool body.

Sensitive connector tools (Gmail send, Notion delete, Linear issue create…)
call :func:`request_approval` to ask the user before performing the side
effect. The function emits the unified langchain HITL wire payload (so the
parallel-HITL routing layer in ``task_tool`` and ``resume_routing`` sees the
same shape it sees for middleware-gated approvals) and returns a typed
:class:`HITLResult`.

Synchronous on purpose: ``langgraph.types.interrupt`` raises ``GraphInterrupt``
inline; the langgraph runtime catches it. Making this ``async`` would only
move the throw site without changing semantics.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.types import interrupt

from app.agents.chat.multi_agent_chat.subagents.shared.hitl.wire import (
    LC_DECISION_APPROVE,
    LC_DECISION_EDIT,
    LC_DECISION_REJECT,
    build_lc_hitl_payload,
    parse_lc_envelope,
)

from .auto_approved import DEFAULT_AUTO_APPROVED_TOOLS
from .result import HITLResult

logger = logging.getLogger(__name__)

# Decisions a self-gated card may carry back. ``"always"`` is reserved for
# permission-rule promotion (middleware-gated path) and intentionally absent
# here.
_SELF_GATED_DECISIONS: list[str] = [
    LC_DECISION_APPROVE,
    LC_DECISION_REJECT,
    LC_DECISION_EDIT,
]


def request_approval(
    *,
    action_type: str,
    tool_name: str,
    params: dict[str, Any],
    context: dict[str, Any] | None = None,
    trusted_tools: list[str] | None = None,
    tool_call_id: str | None = None,
) -> HITLResult:
    """Pause the graph for user approval and return the user's decision.

    Args:
        action_type: FE card discriminator (``"gmail_email_send"``,
            ``"mcp_tool_call"``…). Forwarded as ``interrupt_type`` on the
            wire so the FE can mount the right card variant.
        tool_name: Registered langchain tool name (``"send_gmail_email"``…)
            shown in the card header and used for trust-list lookups.
        params: Original tool arguments. Rendered to the user and used as
            defaults when no edits are made.
        context: Rich metadata (account info, folder lists, MCP server name…)
            forwarded verbatim to the FE for richer card chrome.
        trusted_tools: Per-session allowlist; when ``tool_name`` is in it the
            interrupt is skipped and the tool runs immediately.
        tool_call_id: Caller's LangChain tool-call id. Required for tools
            running directly on the main agent; subagent-mounted tools omit
            it (the ``task`` chokepoint stamps it on re-raise — see
            :mod:`...checkpointed_subagent_middleware.propagation`).

    Returns:
        :class:`HITLResult` with ``rejected=True`` if the user declined or
        the resume envelope was unparseable; otherwise ``params`` carries
        the original args (or args shallow-merged with the user's edits on
        ``"edit"``).
    """
    if trusted_tools and tool_name in trusted_tools:
        logger.info("Tool %r is user-trusted — skipping HITL", tool_name)
        return HITLResult(rejected=False, decision_type="trusted", params=dict(params))

    if tool_name in DEFAULT_AUTO_APPROVED_TOOLS:
        logger.info(
            "Tool %r is in DEFAULT_AUTO_APPROVED_TOOLS — skipping HITL", tool_name
        )
        return HITLResult(
            rejected=False, decision_type="auto_approved", params=dict(params)
        )

    payload = build_lc_hitl_payload(
        tool_name=tool_name,
        args=params,
        allowed_decisions=_SELF_GATED_DECISIONS,
        interrupt_type=action_type,
        context=context,
    )
    if tool_call_id:
        payload["tool_call_id"] = tool_call_id
    approval = interrupt(payload)

    parsed = parse_lc_envelope(approval)
    logger.info("User decision for %r: %s", tool_name, parsed.decision_type)

    if parsed.decision_type == LC_DECISION_REJECT:
        return HITLResult(rejected=True, decision_type="reject", params=dict(params))

    # Anything outside approve/edit at this point is unexpected — fail closed
    # so a malformed FE envelope can't smuggle a side effect through.
    if parsed.decision_type not in (LC_DECISION_APPROVE, LC_DECISION_EDIT):
        logger.warning(
            "Unrecognized decision %r for %r — rejecting for safety",
            parsed.decision_type,
            tool_name,
        )
        return HITLResult(rejected=True, decision_type="error", params=dict(params))

    final_params = (
        {**params, **parsed.edited_args} if parsed.edited_args else dict(params)
    )
    return HITLResult(
        rejected=False, decision_type=parsed.decision_type, params=final_params
    )


__all__ = ["request_approval"]
