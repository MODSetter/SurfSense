from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PATCreate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    expires_in_days: int | None = Field(default=None, gt=0)


class PATCreated(BaseModel):
    id: int
    label: str
    token: str
    prefix: str
    expires_at: datetime | None = None


class PATRead(BaseModel):
    id: int
    label: str
    prefix: str
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
