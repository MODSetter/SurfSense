"""What a new chat on the selected model may be, and which mode it starts in.

Every model may choose Agentic; only a technical gate keeps it out. A score
decides the default alone: Agentic for a model measured at an agent level on a
remote host, Basic for the rest, and the user's last choice over both.
"""

from dataclasses import dataclass

from modules.llm.capability.agent_gate import ToolFacts, gate_block
from modules.llm.capability.level import AGENT_LEVELS, Level
from modules.llm.capability.modes.mode import ChatMode
from modules.llm.capability.modes.remembered import remembered_mode
from modules.llm.capability.resolve import Capability, Reason, capability_of
from modules.llm.models import SelectedModel
from shared.config import get_agent_settings

__all__ = ["NewChatModes", "new_chat_modes"]


@dataclass(frozen=True)
class NewChatModes:
    agentic_allowed: bool
    # The technical gate when Agentic is not allowed: `agent_not_installed`,
    # `tool_calls_unsupported` or `window_below_floor`.
    blocked: str | None
    default_mode: ChatMode
    # What the interface says beside Agentic: `measured_pass`, `measured_near`,
    # `measured_below`, `assumed`, `local_copy` or `untested`.
    reason: Reason
    remembered_mode: ChatMode | None


def new_chat_modes(selected: SelectedModel, facts: ToolFacts) -> NewChatModes:
    """Synchronous and offline; `facts` are as much as the caller could read."""
    settings = get_agent_settings()
    switch = settings.agent_untested_models
    capability = capability_of(selected.name, selected.connection)
    blocked = (
        "agent_not_installed"
        if not settings.has_opencode()
        else gate_block(facts, window_floor=not switch)
    )
    remembered = remembered_mode(selected)
    if remembered is not None:
        default = remembered
    elif switch or capability.level in AGENT_LEVELS:
        default = ChatMode.AGENTIC
    else:
        default = ChatMode.BASIC
    return NewChatModes(
        agentic_allowed=blocked is None,
        blocked=blocked,
        default_mode=ChatMode.BASIC if blocked else default,
        reason=_agentic_reason(capability),
        remembered_mode=remembered,
    )


def _agentic_reason(capability: Capability) -> Reason:
    row = capability.row
    if row is not None and row.assumed:
        # Never run, here or on its full-size version.
        return Reason("assumed")
    if row is None or capability.level is Level.NOT_MEASURED:
        # A row that passed on a provider's host, read for a copy on the user's own.
        if row is not None and Level(row.level) in AGENT_LEVELS:
            return Reason("local_copy", {"host": row.host})
        return Reason("untested")
    counts: dict[str, str | int] = {
        "passed": row.passes.passed,
        "counted": row.passes.counted,
    }
    if capability.level is Level.STUDIO_ONLY:
        return Reason("measured_below", counts)
    if capability.level is Level.AGENT_LIMITED:
        return Reason("measured_near", counts)
    return Reason("measured_pass", counts)
