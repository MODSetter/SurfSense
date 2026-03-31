from datetime import datetime
from typing import Literal

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


class SystemPromptUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    prompt: str | None = Field(None, min_length=1)
    mode: str | None = Field(None, pattern="^(transform|explore)$")


class PromptRead(BaseModel):
    id: int | None
    name: str
    prompt: str
    mode: str
    search_space_id: int | None = None
    is_public: bool = False
    created_at: datetime | None = None
    source: Literal["system", "custom"]
    system_prompt_slug: str | None = None
    is_modified: bool = False

    class Config:
        from_attributes = True


class PublicPromptRead(PromptRead):
    author_name: str | None = None
