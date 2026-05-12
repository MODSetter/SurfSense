"""Linear provider specialist subagent.

This file is intentionally standalone so provider specialists can be reviewed
and evolved independently (one provider per file).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from app.agents.new_chat.permissions import Rule, Ruleset
from app.agents.new_chat.subagents.constants import NON_PROVIDER_STATE_MUTATION_DENY
from app.services.mcp_oauth.registry import (
    LINEAR_MCP_READONLY_TOOL_NAMES,
    linear_mcp_original_tool_name,
)

if TYPE_CHECKING:
    from deepagents import SubAgent
    from langchain_core.language_models import BaseChatModel
    from langchain_core.tools import BaseTool


# Read vs write Linear MCP tools are defined in
# ``app.services.mcp_oauth.registry`` (``LINEAR_MCP_READONLY_TOOL_NAMES`` /
# ``LINEAR_MCP_WRITE_TOOL_NAMES``). Any other Linear-domain tool requires approval.

LINEAR_SYSTEM_PROMPT = """You are the linear_specialist subagent for SurfSense.

Role:
- You are the Linear domain specialist. Handle Linear-only requests accurately.

Primary objective:
- Resolve the user's Linear task and return a concise, auditable result.

Routing boundary:
- Use this subagent for Linear-domain tasks (issues, status, assignees, labels,
  teams, and project references).
- If the task is primarily non-Linear or cross-connector orchestration, return
  status=needs_input and hand control back to the parent with the exact next hop.

Execution steps:
1) Verify Linear access first (use get_connected_accounts if needed).
2) Prefer read/list tools first to gather current issue facts before concluding.
3) Track key identifiers in your reasoning: issue ID, issue key, team ID, label ID.
4) If required identifiers are missing, ask the parent for exactly what is missing.
5) Return a compact result with findings + evidence references.

Output format:
- status: success | needs_input | blocked | error
- summary: one short paragraph
- evidence: bullet list of concrete IDs / issue keys used
- next_step: one sentence (only when blocked or needs_input)

Constraints:
- Do not invent issue keys, IDs, or workflow state names.
- Mutating Linear operations are allowed only with explicit approval.
- If Linear connector access is unavailable, stop and return status=blocked.
"""


def _select_linear_tools(tools: Sequence[BaseTool]) -> list[BaseTool]:
    """Keep Linear tools plus minimal shared read utilities."""
    allowed_exact = {
        "get_connected_accounts",
        "read_file",
        "ls",
        "glob",
        "grep",
    }
    selected: list[BaseTool] = []
    for tool in tools:
        if tool.name in allowed_exact:
            selected.append(tool)
            continue
        if linear_mcp_original_tool_name(tool.name) is not None:
            selected.append(tool)
            continue
        if tool.name.startswith("linear_") or tool.name.endswith("_linear_issue"):
            selected.append(tool)
    return selected


def _is_linear_readonly_tool_name(name: str) -> bool:
    """Return True when a tool name maps to a read-only Linear MCP operation."""
    base = linear_mcp_original_tool_name(name)
    return base is not None and base in LINEAR_MCP_READONLY_TOOL_NAMES


def _is_linear_domain_tool_name(name: str) -> bool:
    """Return True for Linear-domain tools handled by this specialist."""
    if linear_mcp_original_tool_name(name) is not None:
        return True
    return name.startswith("linear_") or name.endswith("_linear_issue")


def _permission_middleware(*, selected_tools: Sequence[BaseTool]) -> Any:
    """Permission policy for Linear specialist."""
    from app.agents.new_chat.middleware.permission import PermissionMiddleware

    ask_tools = sorted(
        {
            tool.name
            for tool in selected_tools
            if _is_linear_domain_tool_name(tool.name)
            and not _is_linear_readonly_tool_name(tool.name)
        }
    )
    rules: list[Rule] = [Rule(permission="*", pattern="*", action="allow")]
    rules.extend(
        Rule(permission=name, pattern="*", action="deny")
        for name in NON_PROVIDER_STATE_MUTATION_DENY
    )
    rules.extend(Rule(permission=name, pattern="*", action="ask") for name in ask_tools)
    return PermissionMiddleware(
        rulesets=[Ruleset(rules=rules, origin="subagent_linear_specialist")]
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
        _permission_middleware(selected_tools=selected_tools),
        PatchToolCallsMiddleware(),
        DedupHITLToolCallsMiddleware(agent_tools=list(selected_tools)),
    ]


def build_linear_specialist_subagent(
    *,
    tools: Sequence[BaseTool],
    model: BaseChatModel | None = None,
    extra_middleware: Sequence[Any] | None = None,
) -> SubAgent:
    """Build the ``linear_specialist`` provider subagent spec."""
    selected_tools = _select_linear_tools(tools)
    spec: dict[str, Any] = {
        "name": "linear_specialist",
        "description": (
            "Linear operations specialist for issue and workflow requests, "
            "with strict evidence tracking and approval-gated mutating operations."
        ),
        "system_prompt": LINEAR_SYSTEM_PROMPT,
        "tools": selected_tools,
        "middleware": _wrap_subagent_middleware(
            selected_tools=selected_tools,
            extra_middleware=extra_middleware,
        ),
    }
    if model is not None:
        spec["model"] = model
    return spec  # type: ignore[return-value]
