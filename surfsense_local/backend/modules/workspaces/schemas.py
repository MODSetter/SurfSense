from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

# Stripped before the length check, so a name of spaces fails rather than
# becoming a row the switcher renders as blank.
WorkspaceName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]


class WorkspaceCreate(BaseModel):
    """Fields a client supplies when opening a workspace."""

    name: WorkspaceName


class WorkspaceUpdate(BaseModel):
    """Fields a client may change on an existing workspace."""

    name: WorkspaceName


class WorkspaceRead(BaseModel):
    """A workspace as the API returns it."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime
    updated_at: datetime
