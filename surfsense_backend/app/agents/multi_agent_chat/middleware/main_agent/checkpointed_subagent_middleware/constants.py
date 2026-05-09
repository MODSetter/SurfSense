"""Constants shared by the checkpointed subagent middleware."""

from __future__ import annotations

# Mirror of deepagents.middleware.subagents._EXCLUDED_STATE_KEYS.
EXCLUDED_STATE_KEYS = frozenset(
    {
        "messages",
        "todos",
        "structured_response",
        "skills_metadata",
        "memory_contents",
    }
)

# Match the parent graph's budget; the LangGraph default of 25 trips on
# multi-step subagent runs.
DEFAULT_SUBAGENT_RECURSION_LIMIT = 10_000
