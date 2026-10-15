"""The mode the user last chose for a model, its default for new chats.

Kept under `chat_modes` in the chat slot's settings, one entry per model, so a
model's choice holds when the slot takes another and comes back. Only this
module reads or writes it.
"""

from modules.llm.capability.modes.mode import ChatMode
from modules.llm.models import SelectedModel

__all__ = ["carried_to_next_model", "mode_entry", "remember_mode", "remembered_mode"]

KEY = "chat_modes"
# The opt-in to try the agent the modes replaced: on, it reads as Agentic.
_TRIAL = "agent_trial"


def remembered_mode(selected: SelectedModel) -> ChatMode | None:
    settings = selected.settings or {}
    stored = _modes(selected).get(mode_entry(selected))
    if stored in set(ChatMode):
        return ChatMode(stored)
    return ChatMode.AGENTIC if settings.get(_TRIAL) is True else None


def remember_mode(
    selected: SelectedModel, mode: ChatMode, entry: str | None = None
) -> None:
    """`entry` is the model the mode was chosen on, read with the choice, since the
    slot may hold another by the time the chat opens; else the selected model."""
    # Reassigned, not mutated: a JSON column tracks assignment only.
    settings = {
        key: value
        for key, value in (selected.settings or {}).items()
        if key not in (KEY, _TRIAL)
    }
    settings[KEY] = {**_every_mode(selected), entry or mode_entry(selected): mode.value}
    selected.settings = settings


def carried_to_next_model(selected: SelectedModel) -> dict | None:
    """The settings the slot keeps when it takes another model: every model's mode.

    Read before the slot changes, so an old opt-in is kept as its model's Agentic.
    """
    modes = _every_mode(selected)
    return {KEY: modes} if modes else None


def mode_entry(selected: SelectedModel) -> str:
    """The provider, connection and name: the same name on another server is its own entry."""
    return f"{selected.provider}/{selected.connection_id or ''}/{selected.name}"


def _every_mode(selected: SelectedModel) -> dict[str, str]:
    """Each model's mode, the selected one's old opt-in kept as its Agentic."""
    modes = _modes(selected)
    current = remembered_mode(selected)
    if current is not None:
        modes[mode_entry(selected)] = current.value
    return modes


def _modes(selected: SelectedModel) -> dict[str, str]:
    stored = (selected.settings or {}).get(KEY)
    return dict(stored) if isinstance(stored, dict) else {}
