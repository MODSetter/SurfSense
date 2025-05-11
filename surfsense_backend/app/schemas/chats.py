from typing import Any, Dict, List, Optional

from app.db import ChatType
from pydantic import BaseModel, ConfigDict

from .base import IDModel, TimestampModel


class ChatBase(BaseModel):
    type: ChatType
    title: str
    initial_connectors: Optional[List[str]] = None
    messages: List[Any]
    search_space_id: int
    

class ClientAttachment(BaseModel):
    name: str
    contentType: str
    url: str


class ToolInvocation(BaseModel):
    toolCallId: str
    toolName: str
    args: dict
    result: dict
    
    
# class ClientMessage(BaseModel):
#     role: str
#     content: str
#     experimental_attachments: Optional[List[ClientAttachment]] = None
#     toolInvocations: Optional[List[ToolInvocation]] = None
    
class AISDKChatRequest(BaseModel):
    messages: List[Any]
    data: Optional[Dict[str, Any]] = None

class ChatCreate(ChatBase):
    pass

class ChatUpdate(ChatBase):
    pass

class ChatRead(ChatBase, IDModel, TimestampModel):
    model_config = ConfigDict(from_attributes=True) 