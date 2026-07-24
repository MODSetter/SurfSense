"""SurfSense's subagent contribution: deepagents spec + permission ruleset."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from deepagents import SubAgent

from app.agents.chat.multi_agent_chat.shared.permissions import Ruleset

# A context-hint provider receives the parent-agent ``runtime.state`` mapping
# and the ``description`` the orchestrator wrote, and returns a short string
# the runtime prepends to the subagent's first ``HumanMessage``. Used for
# things like "current workspace id is X" or "the user is in workspace Y" —
# never for full corpora, since the prepended text consumes the subagent's
# prompt budget on every invocation. Return ``None`` (or an empty string) to
# skip the hint for this call.
ContextHintProvider = Callable[[Mapping[str, Any], str], str | None]

# Custom key stashed on the deepagents ``SubAgent`` dict so the provider
# survives the trip from ``pack_subagent`` → registry → middleware →
# task_tool. ``deepagents.create_agent`` only extracts the keys it
# recognises, so an extra key here is dropped silently at compile time.
# The prefix avoids any collision with future deepagents fields.
SURF_CONTEXT_HINT_PROVIDER_KEY = "surf_context_hint_provider"

# Custom key carrying a zero-arg callable that builds the full deepagents
# ``SubAgent`` spec dict on demand. A descriptor dict carrying only
# ``name`` / ``description`` / this key lets the checkpointed subagent
# middleware register a subagent's catalog entry cheaply while deferring the
# expensive spec construction (e.g. the knowledge_base filesystem middleware,
# which builds ~13 tool schemas at ~150ms each) until the first
# ``task(name)`` call. Most turns never invoke a subagent, so this keeps the
# cost off the cold agent-build / time-to-first-token path.
SURF_LAZY_SPEC_FACTORY_KEY = "surf_lazy_spec_factory"


@dataclass(frozen=True, slots=True)
class SurfSenseSubagentSpec:
    """A subagent contribution from a SurfSense route.

    Attributes:
        spec: The deepagents-shaped dict handed to ``create_agent``. Holds
            only fields ``deepagents.SubAgent`` recognises.
        ruleset: Permission rules this subagent contributes. The orchestrator
            layers them into the subagent's :class:`PermissionMiddleware`,
            so each subagent owns its own ruleset without aliasing the
            shared rule engine.
        context_hint_provider: Optional callback invoked once per ``task(...)``
            invocation, immediately before the subagent runs. Its return
            value is prepended to the subagent's first ``HumanMessage`` so
            the subagent can see things it would otherwise have to discover
            (active workspace, KB root, current user timezone, etc.).
            Kept out of the deepagents ``spec`` because that dict is forwarded
            verbatim to upstream code and only recognises its own typed keys.
    """

    spec: SubAgent
    ruleset: Ruleset
    context_hint_provider: ContextHintProvider | None = None


__all__ = [
    "SURF_CONTEXT_HINT_PROVIDER_KEY",
    "SURF_LAZY_SPEC_FACTORY_KEY",
    "ContextHintProvider",
    "SurfSenseSubagentSpec",
]
