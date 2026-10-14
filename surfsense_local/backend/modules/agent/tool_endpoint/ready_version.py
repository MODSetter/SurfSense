"""Reading a version Studio just finished, waiting out a write lock Studio may still hold."""

import time

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from modules.agent.tool_endpoint.tool import ToolCallError
from modules.artifacts.models import Artifact, ArtifactFileRole
from shared.config import get_storage_settings
from shared.db import is_locked


def read_ready(
    session: Session, artifact_id: int, deadline: float
) -> tuple[Artifact, str, bytes] | None:
    """The ready version, its text and its file; None if the database stayed busy to the deadline.

    Studio may hold the write lock past SQLite's busy wait while it saves another
    document; the version is made, so the read is tried again, not failed. Ends
    with no transaction open, since previews then wait on another process.
    """
    while True:
        try:
            session.expire_all()
            artifact = session.get(Artifact, artifact_id)
            if artifact is None:
                session.commit()
                raise ToolCallError(f"Artifact {artifact_id} was deleted once ready.")
            primary = next(
                f for f in artifact.files if f.role is ArtifactFileRole.PRIMARY
            )
            text = artifact.document.content or ""
            session.commit()
        except OperationalError as error:
            session.rollback()
            if not is_locked(error):
                raise
            if time.monotonic() >= deadline:
                return None
            continue
        data = (get_storage_settings().data_dir / primary.storage_key).read_bytes()
        return artifact, text, data
