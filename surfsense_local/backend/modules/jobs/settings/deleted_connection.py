"""A deleted connection names no checker: SQLite gives a deleted newest row's id to the next
connection added, and a checker still naming it would check on that one, which nobody chose."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

_FORGET = (
    text(
        "UPDATE job_settings SET checker = json_set(checker, '$.connection_id', NULL) "
        "WHERE json_extract(checker, '$.connection_id') = :id"
    ),
    # A queued run and Run again read the checker the run started with.
    text(
        "UPDATE artifacts SET artifact_metadata = json_set(artifact_metadata, "
        "'$.job_run.checker.connection_id', NULL) "
        "WHERE json_extract(artifact_metadata, '$.job_run.checker.connection_id') = :id"
    ),
)


def forget_connection(session: Session, connection_id: int) -> None:
    """In the deletion's own transaction, so no checker outlives the connection it names."""
    for statement in _FORGET:
        session.execute(statement, {"id": connection_id})
