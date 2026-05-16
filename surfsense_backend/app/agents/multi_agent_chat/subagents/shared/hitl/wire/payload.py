"""Build the langchain HITL ``interrupt(...)`` payload — single source of truth.

Every approval path in the multi-agent stack — self-gated tool bodies that call
``request_approval``, and middleware-gated paths (``HumanInTheLoopMiddleware``,
``PermissionMiddleware``) — emits the SAME wire shape from this module so the
parallel-HITL routing layer (``task_tool``, ``resume_routing``) only ever sees
one format. SurfSense-specific extras (FE card discriminator, structured
context) ride alongside the langchain standard fields without colliding with
them.
"""

from __future__ import annotations

from typing import Any

LC_DECISION_APPROVE = "approve"
LC_DECISION_REJECT = "reject"
LC_DECISION_EDIT = "edit"

# ``approve_always`` is a SurfSense extension surfaced by ``PermissionMiddleware``
# so a single click can promote the matched pattern to a runtime allow rule and
# (for MCP tools) save it to the user's trusted-tools list. The FE renders an
# extra button when it appears in ``allowed_decisions``.
SURFSENSE_DECISION_APPROVE_ALWAYS = "approve_always"


def build_lc_hitl_payload(
    *,
    tool_name: str,
    args: dict[str, Any],
    allowed_decisions: list[str],
    interrupt_type: str,
    description: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the unified langchain HITL interrupt payload.

    Args:
        tool_name: The langchain tool's registered name (drives both the action
            request and the review config so the FE can pair them).
        args: Tool call arguments shown to the user. ``None`` is normalized to
            an empty dict so the FE always has a stable shape to render.
        allowed_decisions: Subset of
            ``[LC_DECISION_APPROVE, LC_DECISION_REJECT, LC_DECISION_EDIT,
            SURFSENSE_DECISION_APPROVE_ALWAYS]``. Other values are passed through
            but the FE may not render a control for them.
        interrupt_type: SurfSense card discriminator (``"gmail_email_send"``,
            ``"permission_ask"``, etc.); the FE keys off this to mount the
            right card.
        description: Optional human-readable line shown above the args block.
        context: Optional structured metadata (account info, matched permission
            rules, etc.) forwarded verbatim for richer card chrome.

    Returns:
        A dict suitable for ``langgraph.types.interrupt(...)``. Top-level
        ``action_requests`` and ``review_configs`` are what
        ``collect_pending_tool_calls`` reads at the routing layer; the
        SurfSense extensions (``interrupt_type``, ``context``) sit alongside
        them — langchain ignores unknown keys, so the contract stays clean.
    """
    request: dict[str, Any] = {"name": tool_name, "args": args or {}}
    if description:
        request["description"] = description

    payload: dict[str, Any] = {
        "action_requests": [request],
        "review_configs": [
            {
                "action_name": tool_name,
                "allowed_decisions": list(allowed_decisions),
            }
        ],
        "interrupt_type": interrupt_type,
    }
    if context:
        payload["context"] = context
    return payload


__all__ = [
    "LC_DECISION_APPROVE",
    "LC_DECISION_EDIT",
    "LC_DECISION_REJECT",
    "SURFSENSE_DECISION_APPROVE_ALWAYS",
    "build_lc_hitl_payload",
]
