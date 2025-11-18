from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl

from app.db import SocialMediaPlatform


class SocialMediaLinkBase(BaseModel):
    platform: SocialMediaPlatform
    url: str = Field(..., max_length=500)
    label: str | None = Field(None, max_length=100)
    display_order: int = Field(default=0, ge=0)
    is_active: bool = Field(default=True)


class SocialMediaLinkCreate(SocialMediaLinkBase):
    pass


class SocialMediaLinkUpdate(BaseModel):
    platform: SocialMediaPlatform | None = None
    url: str | None = Field(None, max_length=500)
    label: str | None = Field(None, max_length=100)
    display_order: int | None = Field(None, ge=0)
    is_active: bool | None = None


class SocialMediaLinkRead(SocialMediaLinkBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class SocialMediaLinkPublic(BaseModel):
    """Public-facing schema with only necessary fields for display"""
    id: int
    platform: SocialMediaPlatform
    url: str
    label: str | None

    model_config = {"from_attributes": True}
