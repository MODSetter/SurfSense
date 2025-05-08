from pydantic import BaseModel, ConfigDict
from .base import IDModel, TimestampModel

class ChunkBase(BaseModel):
    content: str
    document_id: int

class ChunkCreate(ChunkBase):
    pass

class ChunkUpdate(ChunkBase):
    pass

class ChunkRead(ChunkBase, IDModel, TimestampModel):
    model_config = ConfigDict(from_attributes=True) 