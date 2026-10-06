"""The revise tool: edit a copy of the user's Word, Excel or PowerPoint file as a new version; the file itself is never written.

The edits are checked on a scratch copy first, so a refused operation costs no
version (03, decisions 11 to 13). Word edits are always tracked changes.
"""

import time
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.agent.tool_endpoint.failed_renders import (
    FailedRunError,
    stop_after_three_failures,
)
from modules.agent.tool_endpoint.job_outcome import wait_for_outcome
from modules.agent.tool_endpoint.render_document import (
    CALL_SECONDS,
    STOP_RULE,
    WAIT_SECONDS,
)
from modules.agent.tool_endpoint.rendered_label import RenderedArtifact, queued_line
from modules.agent.tool_endpoint.revised_result import Revised, revised_result
from modules.agent.tool_endpoint.tool import Tool, ToolCallError, ToolResult
from modules.agent.tool_endpoint.turn_scope import TurnScope
from modules.artifacts.models import Artifact
from modules.artifacts.revised_copies.engines import apply_operations
from modules.artifacts.revised_copies.engines.package import PackageRefusedError
from modules.artifacts.revised_copies.engines.report import Report
from modules.artifacts.revised_copies.formats import RevisableFormat
from modules.artifacts.revised_copies.refusals import RevisedCopyRefusedError
from modules.artifacts.revised_copies.revision import REVISION_KEY
from modules.artifacts.revised_copies.service import (
    create_next_version,
    create_revised_copy,
)
from modules.artifacts.revised_copies.source_file import sha256_of, source_file
from modules.artifacts.revised_copies.versions import revision_base
from modules.artifacts.script_documents.version import version_of
from modules.documents.models import Document, DocumentStatus

TOOL_NAME = "revise_document"
MAX_OPERATIONS = 200
OPERATIONS = (
    "replace_text",
    "insert_paragraphs",
    "delete_paragraphs",
    "add_comment",
    "set_cell",
    "set_range",
    "delete_slide",
    "duplicate_slide",
)
_CELL_VALUE = {"type": ["string", "number", "boolean", "null"]}
# A failed or cancelled version is no copy the user has.
_KEPT = (DocumentStatus.PENDING, DocumentStatus.PROCESSING, DocumentStatus.READY)

LISTING: dict[str, Any] = {
    "name": TOOL_NAME,
    "description": (
        "Edit the user's own .docx, .xlsx, .xlsm or .pptx file as a revised copy: "
        "their file is never changed; each call makes the copy's next version in "
        "Studio. Load the surfsense-revisions skill first. Word edits are always "
        "tracked changes the user accepts or rejects, and can carry comments. "
        "Word: replace_text, insert_paragraphs, delete_paragraphs, add_comment, "
        "each anchored by a quote copied exactly from one paragraph. Excel: "
        "set_cell, set_range (values or formulas; charts and shapes are kept). "
        "PowerPoint: replace_text on a slide or its notes, delete_slide, "
        "duplicate_slide. All operations apply or none do. Returns the copy's "
        "artifact id and version, each operation's outcome, the counts of "
        "tracked changes and comments, the opening text (a workbook's summary) "
        "and up to four page previews as images; or, when nothing was saved, "
        "which operation was refused and why."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "document_id": {
                "type": "integer",
                "description": (
                    "The selected source file to revise, by the number at the end "
                    "of its file name. Gives version 1 of a new revised copy."
                ),
            },
            "artifact_id": {
                "type": "integer",
                "description": (
                    "A revised copy this tool made: the edits go on its newest "
                    "version. Give document_id or artifact_id, not both."
                ),
            },
            "operations": {
                "type": "array",
                "description": f"1 to {MAX_OPERATIONS} edits, applied in order.",
                "items": {
                    "type": "object",
                    "properties": {
                        "op": {"type": "string", "enum": list(OPERATIONS)},
                        "quote": {
                            "type": "string",
                            "description": (
                                "Text copied exactly from one paragraph, found "
                                "once: what to change or anchor to."
                            ),
                        },
                        "text": {
                            "type": "string",
                            "description": (
                                "The new text; for add_comment, the comment. A "
                                "newline in insert_paragraphs starts a paragraph."
                            ),
                        },
                        "through": {
                            "type": "string",
                            "description": (
                                "delete_paragraphs: a quote in the last paragraph "
                                "to delete."
                            ),
                        },
                        "style": {"type": "string"},
                        "comment": {
                            "type": "string",
                            "description": "A comment explaining the change.",
                        },
                        "internal": {
                            "type": "boolean",
                            "description": (
                                "The comment is for the user only: left out of "
                                "the file they send."
                            ),
                        },
                        "sheet": {"type": "string"},
                        "cell": {"type": "string", "description": "Like B7."},
                        "range": {"type": "string", "description": "Like A2:C4."},
                        "value": _CELL_VALUE,
                        "formula": {
                            "type": "string",
                            "description": "Like =SUM(B2:B6).",
                        },
                        "values": {
                            "type": "array",
                            "items": {"type": "array", "items": _CELL_VALUE},
                            "description": "set_range: rows of values.",
                        },
                        "slide": {
                            "type": "integer",
                            "description": "1-based, as the deck was sent.",
                        },
                        "where": {"type": "string", "enum": ["slide", "notes"]},
                    },
                    "required": ["op"],
                },
            },
        },
        "required": ["operations"],
    },
}


@dataclass(frozen=True)
class _Request:
    document_id: int | None
    artifact_id: int | None
    operations: list[dict[str, Any]]


@dataclass(frozen=True)
class _Input:
    path: Path
    format: RevisableFormat
    source_name: str
    base_number: int | None  # None for version 1 of a new copy


def revise(
    session: Session, scope: TurnScope, arguments: dict[str, Any]
) -> str | ToolResult:
    """Check the edits on a scratch copy, make the version, wait for it, and say how it went."""
    deadline = time.monotonic() + CALL_SECONDS
    request = _request(arguments)
    found = _input(session, scope, request)
    report, sha = _dry_run(found, request.operations)
    started = _start(session, scope, request, found, sha)
    outcome = wait_for_outcome(
        session, started.id, min(WAIT_SECONDS, deadline - time.monotonic())
    )
    if outcome is None:
        raise ToolCallError(f"Artifact {started.id} was deleted before it was ready.")
    named = f"Version {started.version} of the revised copy (artifact {started.id})"
    if outcome.status is DocumentStatus.FAILED:
        raise FailedRunError(
            f"{named} failed:\n{outcome.error_message or 'no reason given'}\n\n"
            f"{STOP_RULE}"
        )
    if outcome.status is DocumentStatus.CANCELLED:
        raise ToolCallError(
            f"{named} was cancelled in Studio. Ask the user before revising again."
        )
    if outcome.status is not DocumentStatus.READY:
        return (
            f"{queued_line(started)}\n{named} is still being made, behind other "
            "Studio work. It appears in Studio when it is ready: tell the user so, "
            "and do not revise it again."
        )
    return revised_result(
        session,
        scope.folder,
        Revised(started, found.source_name, found.base_number, report),
        deadline,
    )


def _request(arguments: dict[str, Any]) -> _Request:
    document_id = arguments.get("document_id")
    artifact_id = arguments.get("artifact_id")
    operations = arguments.get("operations")
    for name, value in (("document_id", document_id), ("artifact_id", artifact_id)):
        if value is not None and (
            not isinstance(value, int) or isinstance(value, bool)
        ):
            raise ToolCallError(f"{name} must be a number, or left out.")
    if (document_id is None) == (artifact_id is None):
        raise ToolCallError(
            "Give document_id to revise a source file, or artifact_id to revise a "
            "revised copy again; one of them, not both."
        )
    if (
        not isinstance(operations, list)
        or not 1 <= len(operations) <= MAX_OPERATIONS
        or not all(isinstance(op, dict) for op in operations)
    ):
        raise ToolCallError(
            f"operations must be a list of 1 to {MAX_OPERATIONS} objects, each "
            'with its "op".'
        )
    return _Request(document_id, artifact_id, operations)


def _input(session: Session, scope: TurnScope, request: _Request) -> _Input:
    """The file the edits apply to: the selected source's, or the copy's newest version."""
    try:
        if request.document_id is not None:
            scope.refuse_unselected([request.document_id])
            _refuse_second_copy(session, scope, request.document_id)
            source = source_file(session, scope.workspace_id, request.document_id)
            return _Input(source.path, source.format, source.path.name, None)
        # An artifact is the agent's own output: no source scope holds it.
        assert request.artifact_id is not None
        base = revision_base(session, scope.workspace_id, request.artifact_id)
        return _Input(
            base.path, base.format, base.revision["source_name"], base.version.number
        )
    except RevisedCopyRefusedError as refused:
        raise ToolCallError(str(refused)) from refused
    finally:
        session.rollback()  # reads only; the version is made in its own transaction


def _refuse_second_copy(session: Session, scope: TurnScope, document_id: int) -> None:
    """A second v1 of the same source in one chat splits its edits across two copies."""
    copies = session.scalars(
        select(Artifact)
        .join(Document, Artifact.document_id == Document.id)
        .where(
            Artifact.chat_thread_id == scope.thread_id,
            Artifact.artifact_metadata[REVISION_KEY][
                "derived_from_document_id"
            ].as_integer()
            == document_id,
            Document.status.in_(_KEPT),
        )
        .order_by(Artifact.id.desc())
    ).first()
    if copies is not None:
        root = version_of(copies.artifact_metadata)
        copy_id = root.root if root is not None else copies.id
        raise RevisedCopyRefusedError(
            f"This chat already revised source {document_id} as artifact {copy_id}: "
            f"pass artifact_id {copy_id} to add these edits as its next version."
        )


def _dry_run(found: _Input, operations: list[dict[str, Any]]) -> tuple[Report, str]:
    """The engine's report on a scratch copy, and that copy's checksum for the job to match."""
    with TemporaryDirectory(prefix="surfsense-revise-check-") as scratch:
        copy = Path(scratch) / f"input{found.format.suffix}"
        copy.write_bytes(found.path.read_bytes())
        sha = sha256_of(copy)
        try:
            report = apply_operations(
                found.format.format,
                copy,
                operations,
                Path(scratch) / f"out{found.format.suffix}",
            )
        except PackageRefusedError as refused:
            raise ToolCallError(
                f"{found.source_name} cannot be revised: {refused.message}"
            ) from refused
    if not report.saved:
        raise ToolCallError(
            "\n".join(
                [
                    "Nothing was saved.",
                    report.as_text(),
                    f"Fix the refused operation and send all {len(operations)} again.",
                ]
            )
        )
    return report, sha


def _start(
    session: Session,
    scope: TurnScope,
    request: _Request,
    found: _Input,
    sha: str,
) -> RenderedArtifact:
    """The pending version and its queued job, from the file the edits were checked on."""
    thread = scope.thread_id if scope.known else None
    try:
        if request.document_id is not None:
            source = source_file(session, scope.workspace_id, request.document_id)
            artifact = create_revised_copy(
                session,
                scope.workspace_id,
                source,
                source_sha256=sha,
                operations=request.operations,
                chat_thread_id=thread,
            )
        else:
            assert request.artifact_id is not None
            base = revision_base(session, scope.workspace_id, request.artifact_id)
            if base.version.number != found.base_number:
                raise RevisedCopyRefusedError(
                    f"Version {base.version.number} of this revised copy was made "
                    "while the edits were checked. Send them again."
                )
            artifact = create_next_version(
                session,
                scope.workspace_id,
                base,
                action="edit",
                operations=request.operations,
                chat_thread_id=thread,
            )
    except RevisedCopyRefusedError as refused:
        session.rollback()
        raise ToolCallError(str(refused)) from refused
    version = version_of(artifact.artifact_metadata)
    assert version is not None  # the service gave it one
    return RenderedArtifact(artifact.id, artifact.document.title, version.number)


REVISE_DOCUMENT = Tool(
    listing=LISTING, run=stop_after_three_failures(revise), waits=True
)
