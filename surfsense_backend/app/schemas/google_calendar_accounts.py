from uuid import UUID

from pydantic import BaseModel, ConfigDict


class GoogleCalendarAccountBase(BaseModel):
    user_id: UUID
    access_token: str
    refresh_token: str


class GoogleCalendarAccountCreate(GoogleCalendarAccountBase):
    pass


class GoogleCalendarAccountUpdate(BaseModel):
    access_token: str
    refresh_token: str


class GoogleCalendarAccountRead(BaseModel):
    user_id: UUID
    access_token: str
    refresh_token: str

    model_config = ConfigDict(from_attributes=True)
