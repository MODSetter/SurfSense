"""``ChatMessageActionParams`` — params for the ``chat_message`` action type."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ChatMessageActionParams(BaseModel):
    """Post one turn into an existing chat thread from an automation step."""

    model_config = ConfigDict(extra="forbid")

    thread_id: int = Field(
        ...,
        description="NewChatThread id (the LangGraph thread) to post the turn into.",
    )
    message: str = Field(
        ...,
        min_length=1,
        description="Message sent as the user turn; rendered at execute time.",
    )
