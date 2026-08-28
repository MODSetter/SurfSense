"""HTTP DTOs for workspace git remotes."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, HttpUrl


class RemoteStatusRead(BaseModel):
    provider: str
    url: str
    branch: str
    last_pushed_revision: str | None = None
    last_pushed_at: datetime | None = None
    last_push_error: str | None = None


class GithubAddRequest(BaseModel):
    provider: Literal["github"]
    url: HttpUrl
    installation_id: str = Field(min_length=1)
    branch: str = "main"


class GitlabAddRequest(BaseModel):
    provider: Literal["gitlab"]
    url: HttpUrl
    token: str = Field(min_length=1)
    branch: str = "main"


RemoteAddRequest = Annotated[
    GithubAddRequest | GitlabAddRequest,
    Field(discriminator="provider"),
]


class GithubInstallRead(BaseModel):
    url: str


class GithubRepoRead(BaseModel):
    full_name: str
    url: str
