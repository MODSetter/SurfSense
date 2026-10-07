"""The mode the user last started a chat in with a model, its default for new chats.

Kept under `chat_mode` in the selection's settings, so it belongs to that model
and goes when the slot takes another. Only this module reads or writes it.
"""

from modules.llm.capability.modes.mode import ChatMode
from modules.llm.models import SelectedModel

__all__ = ["remember_mode", "remembered_mode"]

KEY = "chat_mode"
# The opt-in to try the agent the modes replaced: on, it reads as Agentic.
_TRIAL = "agent_trial"


def remembered_mode(selected: SelectedModel) -> ChatMode | None:
    settings = selected.settings or {}
    stored = settings.get(KEY)
    if stored in set(ChatMode):
        return ChatMode(stored)
    return ChatMode.AGENTIC if settings.get(_TRIAL) is True else None


def remember_mode(selected: SelectedModel, mode: ChatMode) -> None:
    # Reassigned, not mutated: a JSON column tracks assignment only.
    settings = {
        key: value
        for key, value in (selected.settings or {}).items()
        if key not in (KEY, _TRIAL)
    }
    settings[KEY] = mode.value
    selected.settings = settings
