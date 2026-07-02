"""``chat_message`` ``ActionDefinition`` registration."""

from __future__ import annotations

from ...store import register_action
from ...types import ActionDefinition
from .factory import build_handler
from .params import ChatMessageActionParams

CHAT_MESSAGE_ACTION = ActionDefinition(
    type="chat_message",
    name="Chat message",
    description="Post a message into an existing chat thread and run one durable, persisted agent turn.",
    params_model=ChatMessageActionParams,
    build_handler=build_handler,
)

register_action(CHAT_MESSAGE_ACTION)
