from typing import Any

from pydantic import BaseModel, ConfigDict

from app.db import ChatType

from .base import IDModel, TimestampModel


class ChatBase(BaseModel):
    type: ChatType
    title: str
    initial_connectors: list[str] | None = None
    messages: list[Any]
    search_space_id: int


class ChatBaseWithoutMessages(BaseModel):
    type: ChatType
    title: str
    search_space_id: int


class ClientAttachment(BaseModel):
    name: str
    content_type: str
    url: str


class ToolInvocation(BaseModel):
    tool_call_id: str
    tool_name: str
    args: dict
    result: dict


# class ClientMessage(BaseModel):
#     role: str
#     content: str
#     experimental_attachments: Optional[List[ClientAttachment]] = None
#     toolInvocations: Optional[List[ToolInvocation]] = None


class AISDKChatRequest(BaseModel):
    messages: list[Any]
    data: dict[str, Any] | None = None


class ChatCreate(ChatBase):
    pass


class ChatUpdate(ChatBase):
    pass


class ChatRead(ChatBase, IDModel, TimestampModel):
    model_config = ConfigDict(from_attributes=True)


class ChatReadWithoutMessages(ChatBaseWithoutMessages, IDModel, TimestampModel):
    model_config = ConfigDict(from_attributes=True)
