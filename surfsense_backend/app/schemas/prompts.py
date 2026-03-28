from datetime import datetime

from pydantic import BaseModel, Field


class PromptCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    prompt: str = Field(..., min_length=1)
    mode: str = Field(..., pattern="^(transform|explore)$")
    icon: str | None = Field(None, max_length=50)
    search_space_id: int | None = None


class PromptUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    prompt: str | None = Field(None, min_length=1)
    mode: str | None = Field(None, pattern="^(transform|explore)$")
    icon: str | None = Field(None, max_length=50)


class PromptRead(BaseModel):
    id: int
    name: str
    prompt: str
    mode: str
    icon: str | None
    search_space_id: int | None
    created_at: datetime

    class Config:
        from_attributes = True
