"""Spill + clear-tool-uses passes to keep payloads under budget."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from langchain_core.tools import BaseTool

from app.agents.multi_agent_chat.main_agent.context_prune.prune_tool_names import (
    safe_exclude_tools,
)
from app.agents.new_chat.feature_flags import AgentFeatureFlags
from app.agents.new_chat.middleware import (
    ClearToolUsesEdit,
    SpillingContextEditingMiddleware,
    SpillToBackendEdit,
)

from ..shared.flags import enabled


def build_context_editing_mw(
    *,
    flags: AgentFeatureFlags,
    max_input_tokens: int | None,
    tools: Sequence[BaseTool],
    backend_resolver: Any,
) -> SpillingContextEditingMiddleware | None:
    if not enabled(flags, "enable_context_editing") or not max_input_tokens:
        return None
    spill_edit = SpillToBackendEdit(
        trigger=int(max_input_tokens * 0.55),
        clear_at_least=int(max_input_tokens * 0.15),
        keep=5,
        exclude_tools=safe_exclude_tools(tools),
        clear_tool_inputs=True,
    )
    clear_edit = ClearToolUsesEdit(
        trigger=int(max_input_tokens * 0.55),
        clear_at_least=int(max_input_tokens * 0.15),
        keep=5,
        exclude_tools=safe_exclude_tools(tools),
        clear_tool_inputs=True,
        placeholder="[cleared - older tool output trimmed for context]",
    )
    return SpillingContextEditingMiddleware(
        edits=[spill_edit, clear_edit],
        backend_resolver=backend_resolver,
    )
