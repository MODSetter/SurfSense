from datetime import datetime

from pydantic import BaseModel, Field


class PromptCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    prompt: str = Field(..., min_length=1)
    mode: str = Field(..., pattern="^(transform|explore)$")
    search_space_id: int | None = None
    is_public: bool = False


class PromptUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    prompt: str | None = Field(None, min_length=1)
    mode: str | None = Field(None, pattern="^(transform|explore)$")
    is_public: bool | None = None


class PromptRead(BaseModel):
    id: int
    name: str
    prompt: str
    mode: str
    search_space_id: int | None
    is_public: bool
    version: int
    created_at: datetime

    class Config:
        from_attributes = True


class PublicPromptRead(PromptRead):
    author_name: str | None = None
