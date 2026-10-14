"""The document tool: run a script that writes a Word file, a PDF, a deck or a workbook, kept as a version in Studio.

The tool waits for the run, since the model fixes its script from the error
(07-create-and-edit-mvp, decision 5).
"""

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from modules.agent.tool_endpoint.document_size import document_size
from modules.agent.tool_endpoint.failed_renders import (
    RENDERS,
    FailedRunError,
    stop_after_three_failures,
)
from modules.agent.tool_endpoint.job_outcome import JobOutcome, wait_for_outcome
from modules.agent.tool_endpoint.ready_version import read_ready
from modules.agent.tool_endpoint.registration import TOOL_CALL_SECONDS
from modules.agent.tool_endpoint.rendered_label import (
    TOOL_NAME,
    RenderedArtifact,
    first_line,
    queued_line,
)
from modules.agent.tool_endpoint.same_title_documents import refuse_same_title
from modules.agent.tool_endpoint.tool import (
    InlineImage,
    Tool,
    ToolCallError,
    ToolResult,
)
from modules.agent.tool_endpoint.turn_scope import TurnScope
from modules.agent.tool_endpoint.version_pages import version_pages
from modules.artifacts.models import Artifact
from modules.artifacts.script_documents.script_error import is_script_error
from modules.artifacts.script_documents.service import (
    ScriptDocumentRefusedError,
    create_script_document,
    inherited_template,
)
from modules.artifacts.script_documents.spec import DOCUMENT_FORMATS, FORMAT_NAMES
from modules.artifacts.script_documents.version import version_of
from modules.documents.models import DocumentStatus
from modules.documents.source_figures import parse_figure_name
from modules.workspaces.models import Workspace

logger = logging.getLogger(__name__)

# The script may run 120 s (worker/document_script/run.py) once the job starts;
# the rest is room for the job's own steps.
WAIT_SECONDS = 150
# The whole call answers by then: past TOOL_CALL_SECONDS opencode reports a bare
# timeout, and the model renders a version that was made again. The 10 s spare
# covers SQLite's 5 s busy waits and drawing the pages.
CALL_SECONDS = TOOL_CALL_SECONDS - 10
# Enough of the text for the model to see the document took the shape it meant.
TEXT_CHARS = 1500
WORKBOOK_HAS_NO_PAGES = (
    "No page previews: a workbook has no pages. Check the summary above against "
    "what the user asked: each sheet, its header row, its values and its formulas."
)
STOP_RULE = (
    "If this is your third failed run for this request, stop and tell the user "
    "what failed."
)

LISTING: dict[str, Any] = {
    "name": TOOL_NAME,
    "description": (
        "Run a Python script that writes a Word document, a PDF, a PowerPoint deck "
        "or an Excel workbook, and keep the file in Studio as a new version. Load "
        "the surfsense-documents skill first. Waits for the run, then returns the "
        "artifact's id and version, its opening text (a workbook's summary) and "
        "up to four page previews as images to check, or the error to fix."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "The document's title, as Studio lists it.",
            },
            "format": {
                "type": "string",
                "enum": list(DOCUMENT_FORMATS),
                "description": (
                    "docx for a Word document, pdf for a PDF, pptx for a PowerPoint "
                    "deck, xlsx for an Excel workbook."
                ),
            },
            "script": {
                "type": "string",
                "description": (
                    "The whole Python script. It saves the document at the path "
                    "in the OUTPUT_PATH environment variable."
                ),
            },
            "artifact_id": {
                "type": "integer",
                "description": (
                    "To change a document you rendered: its artifact id. The "
                    "result is its next version. Leave out for a new document."
                ),
            },
            "images": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Names of the images the script places: source images from "
                    "surfsense_list_images, or charts from surfsense_analyze_data; "
                    "each is at IMAGES_DIR/<name>.png."
                ),
            },
            "template_source_id": {
                "type": "integer",
                "description": (
                    "A source to start from so the result keeps its look: a .docx "
                    "source for docx, a .pptx source for pptx, by the number at the "
                    "end of its file name. The script opens a copy at "
                    "TEMPLATE_PATH. A next version keeps its template when this is "
                    "left out."
                ),
            },
        },
        "required": ["title", "format", "script"],
    },
}


@dataclass(frozen=True)
class _Request:
    title: str
    format: Any  # checked by the service, which says what it accepts
    script: str
    base_artifact_id: int | None
    images: list[str]
    template_source_id: int | None


@dataclass(frozen=True)
class _Started:
    artifact_id: int
    version: int
    title: str


def render(
    session: Session, scope: TurnScope, arguments: dict[str, Any]
) -> str | ToolResult:
    """Create the version in one short transaction, wait for its job, and say how it went.

    Continuing a document needs no scope, since it is the agent's output; placing
    a source's image does.
    """
    began = time.monotonic()
    deadline = began + CALL_SECONDS
    request = _request(arguments)
    _refuse_unselected_images(scope, request.images)
    _refuse_unselected_template(session, scope, request)
    if request.base_artifact_id is None and scope.known:
        refuse_same_title(session, scope.thread_id, request.title, request.format)
    started = _start(session, scope, request)
    wait = min(WAIT_SECONDS, deadline - time.monotonic())
    outcome = wait_for_outcome(session, started.artifact_id, wait)
    if outcome is None:
        raise ToolCallError(
            f"Artifact {started.artifact_id} was deleted before it was ready."
        )
    if outcome.status is DocumentStatus.READY:
        return _made(session, scope.folder, started, deadline)
    if outcome.status is DocumentStatus.FAILED:
        raise FailedRunError(_failed(started, outcome))
    if outcome.status is DocumentStatus.CANCELLED:
        raise ToolCallError(
            f"{_version_of(started)} was cancelled in Studio. Ask the user before "
            "rendering it again."
        )
    # The first line lets the thread link the version once Studio has made it.
    queued = RenderedArtifact(started.artifact_id, started.title, started.version)
    return (
        f"{queued_line(queued)}\n"
        f"{_version_of(started)} is still being made after "
        f"{time.monotonic() - began:.0f} s, "
        "behind other Studio work. It appears in Studio when it is ready: tell the "
        "user so, and do not render it again."
    )


def _request(arguments: dict[str, Any]) -> _Request:
    """The call's arguments, refused in a sentence naming the one to fix."""
    title, script = arguments.get("title"), arguments.get("script")
    # Null is how many models leave an optional field out.
    base = arguments.get("artifact_id")
    images = arguments.get("images")
    images = [] if images is None else images
    template = arguments.get("template_source_id")
    if not isinstance(title, str):
        raise ToolCallError("Give the document a title.")
    if not isinstance(script, str):
        raise ToolCallError(
            "Give the script: Python that saves the document at OUTPUT_PATH."
        )
    if base is not None and (not isinstance(base, int) or isinstance(base, bool)):
        raise ToolCallError(
            "artifact_id must be the number of a document you rendered, or left out."
        )
    if not isinstance(images, list) or not all(isinstance(i, str) for i in images):
        raise ToolCallError(
            "images must be a list of names from surfsense_list_images, or left out."
        )
    if template is not None and (
        not isinstance(template, int) or isinstance(template, bool)
    ):
        raise ToolCallError(
            "template_source_id must be the number at the end of a source's file "
            "name, or left out."
        )
    return _Request(title, arguments.get("format"), script, base, images, template)


def _refuse_unselected_images(scope: TurnScope, images: list[str]) -> None:
    """An image is its source's content: one from a source the turn may not use is refused."""
    if not images:
        return
    selected = scope.selected()
    for name in images:
        parsed = parse_figure_name(name)
        # A name no source has is the service's to refuse, as before.
        if parsed is not None and parsed[0] not in selected:
            raise ToolCallError(
                f'Image "{name}" comes from source {parsed[0]}, which is not '
                "selected for this request. Place only images from the selected "
                "sources, or ask the user to select that one."
            )


def _refuse_unselected_template(
    session: Session, scope: TurnScope, request: _Request
) -> None:
    """A template is its source's content; one a next version keeps is held to the turn too."""
    if request.template_source_id is not None:
        scope.refuse_unselected([request.template_source_id])
        return
    kept = inherited_template(session, scope.workspace_id, request.base_artifact_id)
    session.rollback()  # a read only; the version is made in its own transaction
    if kept is None:
        return
    try:
        scope.refuse_unselected([kept])
    except ToolCallError as refused:
        raise ToolCallError(
            f"Artifact {request.base_artifact_id} starts from template source "
            f"{kept}, which is not selected for this request. {refused}"
        ) from refused


def _start(session: Session, scope: TurnScope, request: _Request) -> _Started:
    """The pending version and its queued job, committed so the worker finds them."""
    try:
        artifact = _create(session, scope, request)
    except ToolCallError:
        session.rollback()  # a refusal leaves its reads open
        raise
    version = version_of(artifact.artifact_metadata)
    assert version is not None  # the service gave it one
    return _Started(artifact.id, version.number, request.title.strip())


def _create(session: Session, scope: TurnScope, request: _Request) -> Artifact:
    workspace = session.get(Workspace, scope.workspace_id)
    if workspace is None:
        raise ToolCallError("This workspace no longer exists.")
    try:
        return create_script_document(
            session,
            workspace,
            title=request.title,
            format=request.format,
            script=request.script,
            base_artifact_id=request.base_artifact_id,
            image_names=request.images,
            template_source_id=request.template_source_id,
            chat_thread_id=scope.thread_id if scope.known else None,
        )
    except ScriptDocumentRefusedError as refused:
        raise ToolCallError(str(refused)) from refused


def _made(
    session: Session, folder: Path, started: _Started, deadline: float
) -> str | ToolResult:
    """What the ready version holds, and the pages drawn by the deadline, as images."""
    rendered = RenderedArtifact(started.artifact_id, started.title, started.version)
    read = read_ready(session, started.artifact_id, deadline)
    if read is None:
        return (
            f"{first_line(rendered)}\nIt is ready in Studio. Its text and page "
            "previews could not be read while Studio was busy: tell the user it is "
            "ready, and do not render it again."
        )
    artifact, text, data = read
    size = document_size(artifact.format, data, text)
    kind = FORMAT_NAMES[artifact.format]
    article = "An" if kind[0] in "AEIOU" else "A"
    # A workbook has no pages to look at, so its whole summary is the check.
    images: tuple[InlineImage, ...] = ()
    if artifact.format == "xlsx":
        heading, body = "Its summary:", text
        check = "\n".join(
            [*_recalculation(artifact.artifact_metadata), WORKBOOK_HAS_NO_PAGES]
        )
    else:
        heading, body = "Its text begins:", _opening(text)
        check, images = version_pages(artifact, started.version, folder, deadline)
    made = "\n".join(
        [
            first_line(rendered),
            f"{article} {kind} of {size}. {heading}",
            "",
            body,
            "",
            check,
        ]
    )
    return ToolResult(made, images) if images else made


def _opening(text: str) -> str:
    if len(text) <= TEXT_CHARS:
        return text
    return f"{text[:TEXT_CHARS]}… ({len(text) - TEXT_CHARS:,} more characters)"


def _recalculation(metadata: dict[str, Any] | None) -> list[str]:
    """Whether the formula values the summary and Studio show are real, from what the job recorded."""
    record = (metadata or {}).get("recalculation")
    if not isinstance(record, dict):
        return []
    if record.get("by"):
        blank = record.get("left_blank") or 0
        lines = [
            f"{record['by']} recalculated the workbook: the summary and Studio show "
            f"the values of {_count(record['formulas'], 'formula')}, saved in the "
            "file, and Excel recalculates again on open."
        ]
        if blank:
            lines.append(
                f"{_count(blank, 'formula')} had no value (an error or an "
                "unsupported function) and are left blank: check them."
            )
        return lines
    return [
        f"Values not recalculated: {record.get('reason') or 'no reason given'} "
        "Studio and the summary show what the script saved for "
        f"{_count(record['formulas'], 'formula')} (often blank or 0) until the "
        "file is opened in Excel, so check each formula itself, not a total shown "
        "for it."
    ]


def _count(n: int, unit: str) -> str:
    return f"{n} {unit}" if n == 1 else f"{n} {unit}s"


def _version_of(started: _Started) -> str:
    return (
        f'Version {started.version} of "{started.title}" '
        f"(artifact {started.artifact_id})"
    )


def _failed(started: _Started, outcome: JobOutcome) -> str:
    """The run's error and traceback tail, what to do next, and the stop rule.

    Only a failure of the script itself sends the model to rewrite it.
    """
    reason = outcome.error_message or "no reason given"
    if is_script_error(outcome.error_message):
        return "\n\n".join(
            [
                f"{_version_of(started)} failed:\n{reason}",
                "Fix the script and render it again with artifact_id "
                f"{started.artifact_id}.\n{STOP_RULE}",
            ]
        )
    return "\n\n".join(
        [
            f"{_version_of(started)} failed, but not in its script:\n{reason}",
            "Render the same script again with artifact_id "
            f"{started.artifact_id}; if it fails the same way, tell the user what "
            f"failed.\n{STOP_RULE}",
        ]
    )


RENDER_DOCUMENT = Tool(
    listing=LISTING, run=stop_after_three_failures(render, RENDERS), waits=True
)
