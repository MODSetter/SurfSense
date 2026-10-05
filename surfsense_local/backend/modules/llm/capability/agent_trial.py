"""The user's opt-in to try the agent on a model nobody has measured.

Kept under `agent_trial` in the selection's settings, so it belongs to that
model and goes when the slot takes another. Only this module reads or writes it.
"""

from modules.llm.models import SelectedModel

__all__ = ["agent_trial", "set_agent_trial"]

KEY = "agent_trial"


def agent_trial(selected: SelectedModel) -> bool:
    return (selected.settings or {}).get(KEY) is True


def set_agent_trial(selected: SelectedModel, enabled: bool) -> None:
    # Reassigned, not mutated: a JSON column tracks assignment only.
    settings = {
        key: value for key, value in (selected.settings or {}).items() if key != KEY
    }
    if enabled:
        settings[KEY] = True
    selected.settings = settings or None
