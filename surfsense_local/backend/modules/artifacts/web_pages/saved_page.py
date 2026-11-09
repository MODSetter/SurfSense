"""A page the agent wrote, kept as a version of its own page in Studio.

The page is the file, as a made file's is, so the job only indexes it; the
version keys are a script document's, so the thread links each version and
Studio's switcher lists them.
"""

from typing import Any

from sqlalchemy.orm import Session

from modules.artifacts.made_file import (
    MadeFileRefusedError,
    add_made_file,
    made_by,
    queue_made_file,
)
from modules.artifacts.models import Artifact
from modules.artifacts.script_documents.version import (
    ArtifactVersion,
    next_version_number,
    version_of,
)

# What `made_by` names for a page the agent saved: the only kind that takes a next version.
PAGE_TOOL = "save_page"


class PageRefusedError(Exception):
    """A page this service will not keep, in a sentence the caller passes on."""


def is_saved_page(metadata: dict[str, Any] | None) -> bool:
    made = made_by(metadata)
    return made is not None and made.get("tool") == PAGE_TOOL


def save_page_version(
    session: Session,
    workspace_id: int,
    *,
    title: str,
    page: bytes,
    working_path: str,
    base_artifact_id: int | None,
    chat_thread_id: int | None,
) -> Artifact:
    """v1 of a new page, or the next version of the page `base_artifact_id` names; committed and queued."""
    parent = _base(session, workspace_id, base_artifact_id)
    try:
        artifact = add_made_file(
            session,
            workspace_id,
            title=title,
            format="html",
            data=page,
            made_by={"tool": PAGE_TOOL, "path": working_path},
            document_ids=[],
            artifact_ids=[],
            chat_thread_id=chat_thread_id,
        )
    except MadeFileRefusedError as refused:
        raise PageRefusedError(str(refused)) from refused
    if parent is None:
        version = ArtifactVersion(root=artifact.id, number=1, parent=None)
    else:
        root = parent.root
        number = next_version_number(session, workspace_id, root)
        version = ArtifactVersion(root=root, number=number, parent=base_artifact_id)
    artifact.artifact_metadata = {
        **artifact.artifact_metadata,
        "version": version.as_metadata(),
    }
    queue_made_file(session, artifact)
    return artifact


def _base(
    session: Session, workspace_id: int, base_artifact_id: int | None
) -> ArtifactVersion | None:
    if base_artifact_id is None:
        return None
    base = session.get(Artifact, base_artifact_id)
    if base is None or base.workspace_id != workspace_id:
        raise PageRefusedError(
            f"There is no artifact {base_artifact_id} in this workspace."
        )
    version = version_of(base.artifact_metadata)
    if not is_saved_page(base.artifact_metadata) or version is None:
        raise PageRefusedError(
            f"Artifact {base_artifact_id} is not a page you saved with "
            "surfsense_save_page, so it takes no version here: save a new page "
            "without artifact_id."
        )
    return version
