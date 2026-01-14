import uuid

from fastapi_users import schemas


class UserRead(schemas.BaseUser[uuid.UUID]):
    pages_limit: int
    pages_used: int
    display_name: str | None = None
    avatar_url: str | None = None


class UserCreate(schemas.BaseUserCreate):
    pass


class UserUpdate(schemas.BaseUserUpdate):
    display_name: str | None = None
    avatar_url: str | None = None
