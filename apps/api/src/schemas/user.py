from typing import ClassVar, Sequence

from pydantic import BaseModel, EmailStr


class User(BaseModel):
    id: str
    forename: str
    surname: str
    email: EmailStr
    table_name: ClassVar[str] = "user"


class UserCreate(BaseModel):
    forename: str
    surname: str
    email: EmailStr


class UserUpdate(BaseModel):
    forename: str
    surname: str
    email: EmailStr


class ResponseMessage(BaseModel):
    message: str


class UserSearchResults(BaseModel):
    results: Sequence[User]
