from datetime import datetime
from pydantic import BaseModel, ConfigDict

class TimestampModel(BaseModel):
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class IDModel(BaseModel):
    id: int
    model_config = ConfigDict(from_attributes=True) 