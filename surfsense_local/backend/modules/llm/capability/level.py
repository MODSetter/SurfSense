"""The four things a selected model can be, by what the ladder measured of it."""

from enum import StrEnum

__all__ = ["AGENT_LEVELS", "Level"]


class Level(StrEnum):
    # Measured and passed the bar: new chats run the agent, Studio drafts by script.
    AGENT = "agent"
    # Measured and near the bar: the agent, which may need a nudge.
    AGENT_LIMITED = "agent_limited"
    # Measured and failed: no agent, Studio drafts by Markdown.
    STUDIO_ONLY = "studio_only"
    # No row holds for it: today's behaviour, and the agent only on the user's opt-in.
    NOT_MEASURED = "not_measured"


AGENT_LEVELS = frozenset({Level.AGENT, Level.AGENT_LIMITED})
