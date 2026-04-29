"""Slack provider specialist subagent.

This file is intentionally standalone so provider specialists can be reviewed
and evolved independently (one provider per file).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from app.agents.new_chat.permissions import Rule, Ruleset
from app.agents.new_chat.subagents.constants import NON_PROVIDER_STATE_MUTATION_DENY

if TYPE_CHECKING:
    from deepagents import SubAgent
    from langchain_core.language_models import BaseChatModel
    from langchain_core.tools import BaseTool


# Slack MCP references used for this provider policy:
# - https://docs.slack.dev/ai/slack-mcp-server
# - https://www.npmjs.com/package/@modelcontextprotocol/server-slack
#
# We explicitly gate known write/mutation operations behind approval (`ask`)
# instead of relying on broad generic write heuristics.
SLACK_MUTATION_TOOL_NAMES: frozenset[str] = frozenset(
    {
        # modelcontextprotocol server
        "slack_post_message",
        "slack_reply_to_thread",
        "slack_add_reaction",
        # Slack-hosted MCP naming variants
        "slack_send_message",
        "slack_draft_message",
        "slack_create_canvas",
        "slack_update_canvas",
    }
)

SLACK_SYSTEM_PROMPT = """You are the slack_specialist subagent for SurfSense.

Role:
- You are the Slack domain specialist. Handle Slack-only requests accurately.

Primary objective:
- Resolve the user's Slack task and return a concise, auditable result.

Routing boundary:
- Use this subagent for Slack-domain tasks (channels, threads, users, messages,
  and Slack canvases).
- If the task is primarily non-Slack or cross-connector orchestration, return
  status=needs_input and hand control back to the parent with the exact next hop.

Execution steps:
1) Verify Slack access first (use get_connected_accounts if needed).
2) Prefer read/list tools first to gather facts before concluding.
3) Track key identifiers in your reasoning: channel ID, message ts, thread ts, user ID.
4) If required identifiers are missing, ask the parent for exactly what is missing.
5) Return a compact result with findings + evidence references.

Output format:
- status: success | needs_input | blocked | error
- summary: one short paragraph
- evidence: bullet list of concrete IDs / timestamps used
- next_step: one sentence (only when blocked or needs_input)

Constraints:
- Do not invent Slack IDs, channels, users, or message content.
- Mutating Slack operations are allowed only with explicit approval.
- If Slack connector access is unavailable, stop and return status=blocked.
"""


def _select_slack_tools(tools: Sequence[BaseTool]) -> list[BaseTool]:
    """Keep Slack tools plus minimal shared read utilities."""
    allowed_exact = {
        "get_connected_accounts",
        "read_file",
        "ls",
        "glob",
        "grep",
    }
    slack_prefix = "slack_"
    selected: list[BaseTool] = []
    for tool in tools:
        if tool.name in allowed_exact:
            selected.append(tool)
            continue
        if tool.name.startswith(slack_prefix):
            selected.append(tool)
    return selected


def _permission_middleware() -> Any:
    """Permission policy for Slack specialist.

    Intent:
    - Allow Slack-domain operations by default.
    - Gate known Slack mutating operations behind approval (`ask`).
    - Hard-deny non-Slack state mutations, especially KB virtual filesystem
      mutation and parent-context mutation tools.
    """
    from app.agents.new_chat.middleware.permission import PermissionMiddleware

    rules: list[Rule] = [Rule(permission="*", pattern="*", action="allow")]
    rules.extend(
        Rule(permission=name, pattern="*", action="deny")
        for name in NON_PROVIDER_STATE_MUTATION_DENY
    )
    rules.extend(
        Rule(permission=name, pattern="*", action="ask")
        for name in SLACK_MUTATION_TOOL_NAMES
    )
    return PermissionMiddleware(
        rulesets=[Ruleset(rules=rules, origin="subagent_slack_specialist")]
    )


def _wrap_subagent_middleware(
    *,
    selected_tools: Sequence[BaseTool],
    extra_middleware: Sequence[Any] | None,
) -> list[Any]:
    """Apply standard middleware chain used by other subagents."""
    from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware

    from app.agents.new_chat.middleware import DedupHITLToolCallsMiddleware

    return [
        *(extra_middleware or []),
        _permission_middleware(),
        PatchToolCallsMiddleware(),
        DedupHITLToolCallsMiddleware(agent_tools=list(selected_tools)),
    ]


def build_slack_specialist_subagent(
    *,
    tools: Sequence[BaseTool],
    model: BaseChatModel | None = None,
    extra_middleware: Sequence[Any] | None = None,
) -> SubAgent:
    """Build the ``slack_specialist`` provider subagent spec."""
    selected_tools = _select_slack_tools(tools)
    spec: dict[str, Any] = {
        "name": "slack_specialist",
        "description": (
            "Slack operations specialist for any Slack-domain request "
            "(channels, threads, users, and messages), with strict evidence "
            "tracking and approval-gated mutating operations."
        ),
        "system_prompt": SLACK_SYSTEM_PROMPT,
        "tools": selected_tools,
        "middleware": _wrap_subagent_middleware(
            selected_tools=selected_tools,
            extra_middleware=extra_middleware,
        ),
    }
    if model is not None:
        spec["model"] = model
    return spec  # type: ignore[return-value]

