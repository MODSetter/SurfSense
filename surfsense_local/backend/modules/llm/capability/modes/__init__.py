"""Basic (Q&A) or Agentic: what a new chat on the selected model may be."""

from modules.llm.capability.modes.mode import ChatMode
from modules.llm.capability.modes.new_chat import NewChatModes, new_chat_modes
from modules.llm.capability.modes.remembered import remember_mode, remembered_mode

__all__ = [
    "ChatMode",
    "NewChatModes",
    "new_chat_modes",
    "remember_mode",
    "remembered_mode",
]
