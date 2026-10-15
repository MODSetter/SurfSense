from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt

from modules.folders.names import FolderName

# The product's job roles (06-product-shape); a folder keeps one through renames.
Role = Literal["evidence", "target", "playbook", "library"]


class FolderCreate(BaseModel):
    """A new Library folder. No parent means the top of the Library."""

    model_config = ConfigDict(extra="forbid")

    parent_id: PositiveInt | None = None
    name: FolderName
    role: Role | None = None


class FolderUpdate(BaseModel):
    """Rename, move and/or set the role. Unset fields are left alone; a null
    `role` clears it."""

    model_config = ConfigDict(extra="forbid")

    name: FolderName | None = None
    parent_id: PositiveInt | None = None
    role: Role | None = None


class FolderRead(BaseModel):
    """One folder. A root's own folder has no parent and is never a row in the tree."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    parent_id: int | None
    root_id: int
    name: str
    role: str | None
    created_at: datetime
    updated_at: datetime


class FolderSummary(BaseModel):
    """What deleting a folder removes, for the dialog that asks first."""

    # Folders below it, not counting itself.
    folders: int
    # Files and notes anywhere below it.
    sources: int
    # Studio outputs filed below it.
    artifacts: int


class DocumentMove(BaseModel):
    """Sources to file in one folder."""

    model_config = ConfigDict(extra="forbid")

    document_ids: Annotated[list[PositiveInt], Field(min_length=1, max_length=1000)]
    folder_id: PositiveInt


class SkippedMove(BaseModel):
    """A source left where it was, and why."""

    document_id: int
    reason: Literal["duplicate"]
    # The source in the target folder holding the same bytes.
    duplicate_of: int


class MoveOutcome(BaseModel):
    moved: list[int]
    skipped: list[SkippedMove]


class CancelOutcome(BaseModel):
    """The sources whose reads were stopped."""

    cancelled: list[int]
