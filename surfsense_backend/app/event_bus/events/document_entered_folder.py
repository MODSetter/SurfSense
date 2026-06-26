"""``document.entered_folder``: a document became a member of a folder.

Fires once per arrival, however the document got there (upload, AI sort, move).
The payload carries the fields a user can filter a trigger on.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, computed_field

from app.event_bus.catalog import EventType, catalog

EVENT_TYPE = "document.entered_folder"


class DocumentEnteredFolderPayload(BaseModel):
    """Snapshot of the document at the moment it entered ``folder_id``.

    ``previous_folder_id`` is the folder it left, or ``None`` for a first
    placement. ``is_move`` derives from it and is emitted for filtering.
    """

    model_config = ConfigDict(extra="forbid")

    document_id: int
    folder_id: int
    previous_folder_id: int | None = None
    document_type: str
    title: str
    connector_id: int | None = None
    created_by_id: str | None = None

    @computed_field
    @property
    def is_move(self) -> bool:
        return self.previous_folder_id is not None


catalog.register(
    EventType(
        type=EVENT_TYPE,
        description="A document became a member of a folder.",
        payload_model=DocumentEnteredFolderPayload,
    )
)


def payload_if_entered_folder(
    *,
    document_id: int,
    workspace_id: int,
    new_folder_id: int | None,
    previous_folder_id: int | None,
    folder_id_changed: bool,
    status_state: str,
    document_type: str,
    title: str,
    connector_id: int | None,
    created_by_id: str | None,
) -> dict | None:
    """Return a publish payload if this commit represents a folder arrival, else None.

    ``folder_id_changed`` comes from SQLAlchemy attribute history — it is True
    only when ``folder_id`` actually changed in this transaction, preventing
    spurious events on unrelated saves.
    """
    if not folder_id_changed:
        return None
    if new_folder_id is None:
        return None
    if status_state != "ready":
        return None

    return {
        "event_type": EVENT_TYPE,
        "workspace_id": workspace_id,
        "payload": {
            "document_id": document_id,
            "folder_id": new_folder_id,
            "previous_folder_id": previous_folder_id,
            "document_type": document_type,
            "title": title,
            "connector_id": connector_id,
            "created_by_id": created_by_id,
        },
    }
