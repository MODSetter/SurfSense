from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PositiveInt

ScopeIds = Annotated[list[PositiveInt], Field(max_length=1000)]


class SourceScope(BaseModel):
    """Which sources a chat or a Studio job uses, as the user ticked them.

    Data, not a list: a ticked folder is dynamic, so a file added to it later is
    in scope. `document_ids` are added back after the folder exclusions, so one
    file can be ticked inside an unticked subfolder.
    """

    model_config = ConfigDict(extra="forbid")

    all: bool = False
    folder_ids: ScopeIds = []
    excluded_folder_ids: ScopeIds = []
    document_ids: ScopeIds = []
    excluded_document_ids: ScopeIds = []


ALL_SOURCES = SourceScope(all=True)


class ScopeCounts(BaseModel):
    """What a scope holds now. Only `ready` sources are searched."""

    ready: int = 0
    # Pending or processing: in scope, searched once indexed.
    indexing: int = 0
    # Failed or cancelled.
    failed: int = 0
    # Ids that no longer exist; dropped from the stored scope at its next write.
    removed: int = 0


class ScopeRead(BaseModel):
    """A stored or draft scope, with what it resolves to now."""

    source_scope: SourceScope
    counts: ScopeCounts
