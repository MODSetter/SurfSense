import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .base import IDModel, TimestampModel

class InferenceParams(BaseModel):
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(None, ge=0)
    top_k: int | None = Field(None, ge=0)
    top_p: int | None = Field(None, ge=0, le=1)


class SearchSpaceBase(BaseModel):
    name: str
    description: str | None = None
    inference_params: InferenceParams | None = None


class SearchSpaceCreate(SearchSpaceBase):
    pass


class SearchSpaceUpdate(SearchSpaceBase):
    name: str | None = None
    description: str | None = None
    inference_params: InferenceParams | None = None


class SearchSpaceRead(SearchSpaceBase, IDModel, TimestampModel):
    id: int
    created_at: datetime
    user_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)
