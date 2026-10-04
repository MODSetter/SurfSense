"""The read tool: the script behind a document the agent rendered, as its newest version has it."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.agent.tool_endpoint.tool import Tool, ToolCallError
from modules.artifacts.formats import FORMATS_BY_KEY
from modules.artifacts.models import Artifact
from modules.artifacts.script_documents.spec import document_script
from modules.artifacts.script_documents.version import version_of
from modules.documents.models import DocumentStatus

LISTING: dict[str, Any] = {
    "name": "read_document",
    "description": (
        "Read the script behind a document you made with "
        "surfsense_render_document, as its newest version has it, with that "
        "version's number and artifact id. Read it before changing the document."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "artifact_id": {
                "type": "integer",
                "description": "The artifact id of any version of the document.",
            }
        },
        "required": ["artifact_id"],
    },
}


def read(session: Session, workspace_id: int, arguments: dict[str, Any]) -> str:
    """The newest version's number, title, format and script, whichever version was named."""
    artifact_id = arguments.get("artifact_id")
    if not isinstance(artifact_id, int) or isinstance(artifact_id, bool):
        raise ToolCallError("Give the artifact_id of a document you rendered.")
    named = session.get(Artifact, artifact_id)
    if named is None or named.workspace_id != workspace_id:
        raise ToolCallError(f"There is no artifact {artifact_id} in this workspace.")
    version = version_of(named.artifact_metadata)
    if version is None or document_script(named.artifact_metadata) is None:
        raise ToolCallError(
            f"Artifact {artifact_id} was made by Studio and keeps no script, so it "
            "has no script to read or change here."
        )

    newest = _newest_version(session, workspace_id, version.root)
    script = document_script(newest.artifact_metadata)
    number = version_of(newest.artifact_metadata).number
    kind = f"{FORMATS_BY_KEY[newest.format].label} document"
    images = ", ".join(script.images) if script.images else "none"
    return "\n".join(
        [
            f'"{newest.document.title}" is a {kind}. Its newest is version {number}, '
            f"artifact {newest.id}, {_status(newest)}. Render its next version with "
            f"artifact_id {newest.id}.",
            f"Source images it places: {images}",
            "",
            "Script:",
            script.text,
        ]
    )


def _newest_version(session: Session, workspace_id: int, root: int) -> Artifact:
    version = Artifact.artifact_metadata["version"]
    return session.scalars(
        select(Artifact)
        .where(
            Artifact.workspace_id == workspace_id,
            version["root"].as_integer() == root,
        )
        .order_by(version["number"].as_integer().desc())
        .limit(1)
    ).one()


def _status(artifact: Artifact) -> str:
    """Whether the newest version rendered; a failed one's script still has its error."""
    document = artifact.document
    if document.status is DocumentStatus.FAILED:
        reason = (document.error_message or "").strip().splitlines()[:1]
        return f"which failed ({reason[0]})" if reason else "which failed"
    return document.status.value


READ_DOCUMENT = Tool(listing=LISTING, run=read)
