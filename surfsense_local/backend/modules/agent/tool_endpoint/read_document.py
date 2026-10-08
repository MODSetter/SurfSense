"""The read tool: the script behind a document the agent rendered, a revised copy as it reads now, or a workbook's cells."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.agent.tool_endpoint.read_revised_copy import read_revised_copy
from modules.agent.tool_endpoint.read_workbook import read_source_workbook
from modules.agent.tool_endpoint.script_page import (
    OffsetOutOfRangeError,
    ScriptPage,
    page_of,
)
from modules.agent.tool_endpoint.tool import Tool, ToolCallError
from modules.agent.tool_endpoint.turn_scope import TurnScope
from modules.artifacts.models import Artifact
from modules.artifacts.revised_copies.revision import revision_of
from modules.artifacts.script_documents.service import MADE_IN_STUDIO
from modules.artifacts.script_documents.spec import FORMAT_NAMES, document_script
from modules.artifacts.script_documents.version import version_of
from modules.artifacts.studio_documents.recipe import studio_made
from modules.documents.models import DocumentStatus

LISTING: dict[str, Any] = {
    "name": "read_document",
    "description": (
        "Read the script behind a document you made with "
        "surfsense_render_document, as its newest version has it, with that "
        "version's number and artifact id. Read it before changing the document. "
        "A long script comes a page of lines at a time: each result says which "
        "lines it holds, and the offset to call again with for the rest. Given "
        "the document_id of a selected .xlsx or .xlsm source, it returns the "
        "workbook's cells instead: each sheet's name and used range, then every "
        "non-empty cell as its address and value or formula. Read them before "
        "revising a workbook. Given the artifact_id of a revised copy, it returns "
        "the copy as it reads now: a Word copy's text with every author's tracked "
        "changes marked and its comments, a workbook's cells, or each slide's text."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "artifact_id": {
                "type": "integer",
                "description": (
                    "The artifact id of any version of the document, or of a "
                    "revised copy."
                ),
            },
            "document_id": {
                "type": "integer",
                "description": (
                    "A selected .xlsx or .xlsm source, by the number at the end "
                    "of its file name. Give artifact_id or document_id, not both."
                ),
            },
            "sheet": {
                "type": "string",
                "description": "A workbook's sheet to read alone. Leave out for all.",
            },
            "offset": {
                "type": "integer",
                "description": (
                    "The line to start reading from, 1 for the first; for a "
                    "workbook, the row. Leave out to start at the top."
                ),
            },
        },
    },
}


def read(session: Session, scope: TurnScope, arguments: dict[str, Any]) -> str:
    """The newest version's number, title, format and script, whichever version was named.

    An artifact is the agent's output, not a source, so any turn may read it;
    a workbook source keeps to the turn's ticks.
    """
    workspace_id = scope.workspace_id
    artifact_id = arguments.get("artifact_id")
    document_id = arguments.get("document_id")
    if artifact_id is not None and document_id is not None:
        raise ToolCallError(
            "Give artifact_id to read a document you made, or document_id to read "
            "a workbook source; one of them, not both."
        )
    if document_id is not None:
        if not isinstance(document_id, int) or isinstance(document_id, bool):
            raise ToolCallError("document_id must be a number, or left out.")
        return read_source_workbook(session, scope, document_id, arguments)
    if not isinstance(artifact_id, int) or isinstance(artifact_id, bool):
        raise ToolCallError("Give the artifact_id of a document you rendered.")
    # Null is how many models leave an optional field out.
    offset = arguments.get("offset")
    offset = 1 if offset is None else offset
    named = session.get(Artifact, artifact_id)
    if named is None or named.workspace_id != workspace_id:
        raise ToolCallError(f"There is no artifact {artifact_id} in this workspace.")
    if revision_of(named.artifact_metadata) is not None:
        return read_revised_copy(session, scope, named, arguments)
    if studio_made(named.artifact_metadata):
        raise ToolCallError(MADE_IN_STUDIO)
    version = version_of(named.artifact_metadata)
    if version is None or document_script(named.artifact_metadata) is None:
        raise ToolCallError(
            f"Artifact {artifact_id} was made by Studio and keeps no script, so it "
            "has no script to read or change here."
        )

    newest = _newest_version(session, workspace_id, version.root)
    script = document_script(newest.artifact_metadata)
    number = version_of(newest.artifact_metadata).number
    kind = FORMAT_NAMES[newest.format]
    article = "an" if kind[0] in "AEIOU" else "a"
    images = ", ".join(script.images) if script.images else "none"
    # The next version keeps it unless its render names another.
    template = (
        [f"Template source it starts from: {script.template_source_id}"]
        if script.template_source_id is not None
        else []
    )
    page = _page(script.text, offset)
    return "\n".join(
        [
            f'"{newest.document.title}" is {article} {kind}. Its newest is version '
            f"{number}, artifact {newest.id}, {_status(newest)}. Render its next "
            f"version with artifact_id {newest.id}.",
            f"Source images it places: {images}",
            *template,
            "",
            f"Script, lines {page.first}-{page.last} of {page.total}:",
            page.text + _rest(page),
        ]
    )


def _page(script: str, offset: object) -> ScriptPage:
    """The page from that line, or a refusal naming the offsets there are."""
    if isinstance(offset, int) and not isinstance(offset, bool):
        try:
            return page_of(script, offset)
        except OffsetOutOfRangeError:
            pass
    lines = page_of(script, 1).total
    raise ToolCallError(
        f"The script has {lines} lines: give an offset from 1 to {lines}, or leave "
        "it out to start at the top."
    )


def _rest(page: ScriptPage) -> str:
    """Where the next page starts, after a blank line; nothing after the last page.

    Only the last line can lack its newline, so an earlier page ends with one.
    """
    if page.last == page.total:
        return ""
    return (
        f"\nThe script goes on past line {page.last}. Call "
        f"surfsense_read_document again with offset {page.last + 1} for the next "
        "lines, and read to the end before you change the document."
    )


def _newest_version(session: Session, workspace_id: int, root: int) -> Artifact:
    """The agent's newest script: a lineage begun before 07's decision 8 held may hold Studio's."""
    version = Artifact.artifact_metadata["version"]
    scripts = session.scalars(
        select(Artifact)
        .where(
            Artifact.workspace_id == workspace_id,
            version["root"].as_integer() == root,
            Artifact.artifact_metadata["spec"]["kind"].as_string() == "python",
        )
        .order_by(version["number"].as_integer().desc())
    )
    # The named version is the agent's, so one is always found.
    return next(a for a in scripts if not studio_made(a.artifact_metadata))


def _status(artifact: Artifact) -> str:
    """Whether the newest version rendered; a failed one's script still has its error."""
    document = artifact.document
    if document.status is DocumentStatus.FAILED:
        reason = (document.error_message or "").strip().splitlines()[:1]
        return f"which failed ({reason[0]})" if reason else "which failed"
    return document.status.value


READ_DOCUMENT = Tool(listing=LISTING, run=read)
