from pydantic import BaseModel
from .base import IDModel, TimestampModel

class ChunkBase(BaseModel):
    content: str
    document_id: int

class ChunkCreate(ChunkBase):
    pass

class ChunkUpdate(ChunkBase):
    pass

class ChunkRead(ChunkBase, IDModel, TimestampModel):
    class Config:
        from_attributes = True 