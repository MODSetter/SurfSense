from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from sqlalchemy import JSON
from .base import IDModel, TimestampModel
from app.db import ChatType

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
    
    
class ClientMessage(BaseModel):
    role: str
    content: str
    experimental_attachments: Optional[List[ClientAttachment]] = None
    toolInvocations: Optional[List[ToolInvocation]] = None
    
class AISDKChatRequest(BaseModel):
    messages: List[ClientMessage]
    data: Optional[Dict[str, Any]] = None

class ChatCreate(ChatBase):
    pass

class ChatUpdate(ChatBase):
    pass

class ChatRead(ChatBase, IDModel, TimestampModel):
    class Config:
        from_attributes = True 