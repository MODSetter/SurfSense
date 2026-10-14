"""Accept or reject every tracked change of a Word revised copy, as its next version."""

from typing import Literal

from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.artifacts.revised_copies.refusals import RevisedCopyRefusedError
from modules.artifacts.revised_copies.revision import change_count
from modules.artifacts.revised_copies.service import create_next_version
from modules.artifacts.revised_copies.versions import revision_base

Decision = Literal["accept_all", "reject_all"]


def decide_all(session: Session, artifact: Artifact, action: Decision) -> Artifact:
    """Start the version that accepts or rejects all; the newest one keeps its changes."""
    base = revision_base(session, artifact.workspace_id, artifact.id)
    if base.format.format != "docx":
        raise RevisedCopyRefusedError(
            "Only a Word revised copy has tracked changes to accept or reject."
        )
    if change_count(base.revision) == 0:
        raise RevisedCopyRefusedError(
            f"Version {base.version.number} has no tracked changes to decide."
        )
    return create_next_version(
        session,
        artifact.workspace_id,
        base,
        action=action,
        operations=[],
        chat_thread_id=base.artifact.chat_thread_id,
    )
