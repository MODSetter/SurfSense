"""The Studio tool: start a Studio job from the sources the agent names."""

from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from modules.agent.sources_folder import SOURCES
from modules.agent.tool_endpoint.registration import SERVER
from modules.agent.tool_endpoint.rendered_label import TOOL_NAME as RENDER_TOOL
from modules.agent.tool_endpoint.tool import Tool, ToolCallError
from modules.agent.tool_endpoint.turn_scope import TurnScope
from modules.artifacts.formats import FORMATS, FORMATS_BY_KEY
from modules.artifacts.schemas import StudioJobCreate
from modules.artifacts.script_documents.spec import DOCUMENT_FORMATS
from modules.artifacts.service import create_artifact_job
from modules.embedding.active import EmbeddingNotChosenError, require_active_index
from modules.workspaces.models import Workspace

# Studio's own cap on a request's instructions (StudioJobCreate.prompt).
INSTRUCTIONS_CHARS = 2000

# Office files and PDFs are scripts the agent renders: Studio's draft keeps none to edit.
_KEYS = [fmt.key for fmt in FORMATS if fmt.key not in DOCUMENT_FORMATS]

# Written out flat, and the same on every turn, so a local model's prompt cache holds.
LISTING: dict[str, Any] = {
    "name": "create_artifact",
    "description": (
        "Start a Studio job that makes a deliverable from the user's sources, such "
        "as a quiz, a mind map or a podcast. It returns at once; the result appears "
        "in Studio when it is ready."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "format": {
                "type": "string",
                "enum": _KEYS,
                "description": "What to make. html is a web page.",
            },
            "source_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": (
                    "The sources to make it from: the number in brackets at the "
                    f"end of each file name in {SOURCES}/."
                ),
            },
            "instructions": {
                "type": "string",
                "description": (
                    "What the user asked for: the focus, the audience, the length. "
                    f"At most {INSTRUCTIONS_CHARS:,} characters."
                ),
            },
        },
        "required": ["format", "source_ids"],
    },
}


def start(session: Session, scope: TurnScope, arguments: dict[str, Any]) -> str:
    """Start the job as Studio's own route would; Studio's reason when it cannot."""
    key = arguments.get("format")
    if key in DOCUMENT_FORMATS:
        raise ToolCallError(
            "Make a Word document, a PDF, a PowerPoint deck or an Excel workbook "
            f"with {SERVER}_{RENDER_TOOL}, after loading the surfsense-documents skill."
        )
    fmt = FORMATS_BY_KEY.get(key) if key in _KEYS else None
    if fmt is None:
        raise ToolCallError(f"Name a format, one of: {', '.join(_KEYS)}.")
    source_ids = arguments.get("source_ids")
    if (
        not isinstance(source_ids, list)
        or not source_ids
        or not all(isinstance(source_id, int) for source_id in source_ids)
    ):
        raise ToolCallError(
            "Name at least one source: the number in brackets at the end of its "
            f"file name in {SOURCES}/."
        )
    scope.refuse_unselected(source_ids)
    instructions = arguments.get("instructions")
    if instructions is not None and (
        not isinstance(instructions, str)
        or len(instructions.strip()) > INSTRUCTIONS_CHARS
    ):
        raise ToolCallError(
            f"Give the instructions as text of at most {INSTRUCTIONS_CHARS:,} characters."
        )
    # Studio's route refuses the same way: its passages are found through the index.
    try:
        require_active_index(session)
    except EmbeddingNotChosenError as error:
        raise ToolCallError(
            "Studio is not ready on this computer: no embedding model is chosen yet."
        ) from error
    workspace = session.get(Workspace, scope.workspace_id)
    if workspace is None:
        raise ToolCallError("This workspace no longer exists.")
    payload = StudioJobCreate(
        format=fmt.key, document_ids=source_ids, prompt=instructions or None
    )
    try:
        create_artifact_job(session, workspace, payload)
    except HTTPException as refused:
        raise ToolCallError(
            f'Studio could not start "{fmt.label}": {_sentence(refused.detail)}'
        ) from refused
    count = len(set(source_ids))
    sources = "source" if count == 1 else "sources"
    return (
        f'Studio started "{fmt.label}" from {count} {sources}. It appears in Studio '
        "when it is ready."
    )


def _sentence(detail: object) -> str:
    """Studio's reason, ended as a sentence."""
    text = str(detail).strip()
    return text if text.endswith(".") else f"{text}."


CREATE_ARTIFACT = Tool(listing=LISTING, run=start)
