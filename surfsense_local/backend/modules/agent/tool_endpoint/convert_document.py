"""The convert tool: a Word document or deck, the agent's own or a selected source, as a new PDF in Studio.

LibreOffice converts a copy in a Studio job; the tool waits for it, as a render
does, and shows the PDF's first pages. It is always listed and refused in a
sentence while Office support is off: listing it only while on would change
the tool list mid-thread and break a local model's prompt cache.
"""

import time
from typing import Any

from sqlalchemy.orm import Session

from modules.agent.tool_endpoint.document_size import document_size
from modules.agent.tool_endpoint.job_outcome import wait_for_outcome
from modules.agent.tool_endpoint.ready_version import read_ready
from modules.agent.tool_endpoint.registration import TOOL_CALL_SECONDS
from modules.agent.tool_endpoint.rendered_label import (
    RenderedArtifact,
    first_line,
    queued_line,
)
from modules.agent.tool_endpoint.tool import Tool, ToolCallError, ToolResult
from modules.agent.tool_endpoint.turn_scope import TurnScope
from modules.agent.tool_endpoint.version_pages import version_pages
from modules.artifacts.converted_documents.conversion import Conversion
from modules.artifacts.converted_documents.input_file import ConversionRefusedError
from modules.artifacts.converted_documents.service import create_conversion
from modules.artifacts.models import Artifact
from modules.documents.models import DocumentStatus
from modules.office_support import engine
from modules.workspaces.models import Workspace

TOOL_NAME = "convert_document"
# The job's own limit is 120 s (worker/studio/converted_document); then indexing.
WAIT_SECONDS = 150
CALL_SECONDS = TOOL_CALL_SECONDS - 10
TEXT_CHARS = 1000
OFFICE_OFF = (
    "Converting to PDF needs Office support, which is off on this computer. Tell "
    "the user they can turn it on in Settings > Office support, then ask you again."
)
LOOK_AT_THE_PDF = (
    "Look at every one before you answer; if the layout is wrong, fix the Word or "
    "PowerPoint version, render it again and convert the new version."
)

LISTING: dict[str, Any] = {
    "name": TOOL_NAME,
    "description": (
        "Convert a Word document or PowerPoint deck to PDF with LibreOffice: one you "
        "rendered (artifact_id, any version) or a selected .docx or .pptx source "
        "(document_id). The PDF is a new document in Studio; the file converted is "
        "never changed. Waits for the conversion, then returns the PDF's artifact "
        "id, its page count, its opening text and up to four page previews as "
        "images. Needs Office support: refused while it is off."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "artifact_id": {
                "type": "integer",
                "description": (
                    "A Word or PowerPoint version you rendered. Leave out to "
                    "convert a source."
                ),
            },
            "document_id": {
                "type": "integer",
                "description": (
                    "A selected source: the number in brackets at the end of its "
                    "file name in sources/. Leave out to convert an artifact."
                ),
            },
            "format": {
                "type": "string",
                "enum": ["pdf"],
                "description": "The format to convert to.",
            },
        },
        "required": ["format"],
    },
}


def convert(
    session: Session, scope: TurnScope, arguments: dict[str, Any]
) -> str | ToolResult:
    """Queue the conversion in one short transaction, wait for it, and show the PDF."""
    deadline = time.monotonic() + CALL_SECONDS
    conversion = _conversion(arguments)
    office = engine.office_engine()
    if office is None:
        raise ToolCallError(OFFICE_OFF)
    if conversion.document_id is not None:
        scope.refuse_unselected([conversion.document_id])
    made = _start(session, scope, conversion)
    queued = RenderedArtifact(made.id, made.document.title, 1)
    outcome = wait_for_outcome(
        session, made.id, min(WAIT_SECONDS, deadline - time.monotonic())
    )
    if outcome is None:
        raise ToolCallError(f"Artifact {made.id} was deleted before it was ready.")
    if outcome.status is DocumentStatus.FAILED:
        raise ToolCallError(
            f"Converting to PDF failed: {outcome.error_message or 'no reason given'}"
        )
    if outcome.status is DocumentStatus.CANCELLED:
        raise ToolCallError(
            f"The PDF (artifact {made.id}) was cancelled in Studio. Ask the user "
            "before converting again."
        )
    if outcome.status is not DocumentStatus.READY:
        return (
            f"{queued_line(queued)}\nThe PDF is still being made, behind other "
            "Studio work. It appears in Studio when it is ready: tell the user so, "
            "and do not convert again."
        )
    return _converted(session, scope, queued, office.name, conversion, deadline)


def _conversion(arguments: dict[str, Any]) -> Conversion:
    # Null is how many models leave an optional field out.
    artifact_id, document_id = (
        arguments.get("artifact_id"),
        arguments.get("document_id"),
    )
    if arguments.get("format") != "pdf":
        raise ToolCallError("format must be pdf: PDF is the one format offered.")
    for name, value in (("artifact_id", artifact_id), ("document_id", document_id)):
        if value is not None and (
            not isinstance(value, int) or isinstance(value, bool)
        ):
            raise ToolCallError(f"{name} must be a number, or left out.")
    if (artifact_id is None) == (document_id is None):
        raise ToolCallError(
            "Give exactly one of artifact_id (a version you rendered) and "
            "document_id (a selected source)."
        )
    return Conversion(artifact_id=artifact_id, document_id=document_id)


def _start(session: Session, scope: TurnScope, conversion: Conversion) -> Artifact:
    workspace = session.get(Workspace, scope.workspace_id)
    if workspace is None:
        raise ToolCallError("This workspace no longer exists.")
    try:
        return create_conversion(
            session,
            workspace,
            conversion,
            chat_thread_id=scope.thread_id if scope.known else None,
        )
    except ConversionRefusedError as refused:
        session.rollback()  # a refusal leaves its reads open
        raise ToolCallError(str(refused)) from refused


def _converted(
    session: Session,
    scope: TurnScope,
    made: RenderedArtifact,
    office: str,
    conversion: Conversion,
    deadline: float,
) -> str | ToolResult:
    read = read_ready(session, made.id, deadline)
    if read is None:
        return (
            f"{first_line(made)}\nThe PDF is ready in Studio. Its text and page "
            "previews could not be read while Studio was busy: tell the user it is "
            "ready, and do not convert again."
        )
    artifact, text, data = read
    origin = (
        f"artifact {conversion.artifact_id}"
        if conversion.artifact_id is not None
        else f"source {conversion.document_id}"
    )
    opening = text if len(text) <= TEXT_CHARS else f"{text[:TEXT_CHARS]}…"
    check, images = version_pages(artifact, 1, scope.folder, deadline, LOOK_AT_THE_PDF)
    made_text = "\n".join(
        [
            first_line(made),
            f"A PDF of {document_size('pdf', data, text)}, converted by {office} "
            f"from {origin}, which is unchanged. Its text begins:",
            "",
            opening,
            "",
            check,
        ]
    )
    return ToolResult(made_text, images) if images else made_text


CONVERT_DOCUMENT = Tool(listing=LISTING, run=convert, waits=True)
