"""The document tool: run a script that writes a Word file or a PDF, kept as a version in Studio.

The tool waits for the run, since the model fixes its script from the error
(07-create-and-edit-mvp, decision 5).
"""

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from modules.agent.opencode_config import CONFIG_FILE, declares_image_input
from modules.agent.previews import previews_for
from modules.agent.tool_endpoint.document_size import document_size
from modules.agent.tool_endpoint.job_outcome import JobOutcome, wait_for_outcome
from modules.agent.tool_endpoint.registration import TOOL_CALL_SECONDS
from modules.agent.tool_endpoint.rendered_label import (
    TOOL_NAME,
    RenderedArtifact,
    first_line,
    queued_line,
)
from modules.agent.tool_endpoint.tool import Tool, ToolCallError
from modules.artifacts.formats import FORMATS_BY_KEY
from modules.artifacts.models import Artifact, ArtifactFileRole
from modules.artifacts.script_documents.script_error import is_script_error
from modules.artifacts.script_documents.service import (
    ScriptDocumentRefusedError,
    create_script_document,
)
from modules.artifacts.script_documents.spec import DOCUMENT_FORMATS
from modules.artifacts.script_documents.version import version_of
from modules.documents.models import DocumentStatus
from modules.workspaces.models import Workspace
from shared.config import get_storage_settings
from shared.db import is_locked

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
# The snapshot page lays Word out with docx-preview, told to skip both
# (frontend/src/features/docx-snapshot/snapshot-page.ts).
WORD_PREVIEWS_LEAVE_OUT = (
    "Word previews leave out headers and footers: a logo or page number placed "
    "there is in the document even though no preview shows it."
)
STOP_RULE = (
    "If this is your third failed run for this request, stop and tell the user "
    "what failed."
)

LISTING: dict[str, Any] = {
    "name": TOOL_NAME,
    "description": (
        "Run a Python script that writes a Word document or a PDF, and keep the "
        "file in Studio as a new version. Load the surfsense-documents skill "
        "first. Waits for the run, then returns the artifact's id and version, "
        "its opening text and page previews to check, or the error to fix."
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
                "description": "docx for a Word document, pdf for a PDF.",
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
                    "Names from surfsense_list_images of the source images the "
                    "script places; each is at IMAGES_DIR/<name>.png."
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


@dataclass(frozen=True)
class _Started:
    artifact_id: int
    version: int
    title: str


def render(session: Session, workspace_id: int, arguments: dict[str, Any]) -> str:
    """Create the version in one short transaction, wait for its job, and say how it went."""
    began = time.monotonic()
    deadline = began + CALL_SECONDS
    request = _request(arguments)
    started = _start(session, workspace_id, request)
    wait = min(WAIT_SECONDS, deadline - time.monotonic())
    outcome = wait_for_outcome(session, started.artifact_id, wait)
    if outcome is None:
        raise ToolCallError(
            f"Artifact {started.artifact_id} was deleted before it was ready."
        )
    if outcome.status is DocumentStatus.READY:
        return _made(session, workspace_id, started, deadline)
    if outcome.status is DocumentStatus.FAILED:
        raise ToolCallError(_failed(started, outcome))
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
    return _Request(title, arguments.get("format"), script, base, images)


def _start(session: Session, workspace_id: int, request: _Request) -> _Started:
    """The pending version and its queued job, committed so the worker finds them."""
    try:
        artifact = _create(session, workspace_id, request)
    except ToolCallError:
        session.rollback()  # a refusal leaves its reads open
        raise
    version = version_of(artifact.artifact_metadata)
    assert version is not None  # the service gave it one
    return _Started(artifact.id, version.number, request.title.strip())


def _create(session: Session, workspace_id: int, request: _Request) -> Artifact:
    workspace = session.get(Workspace, workspace_id)
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
        )
    except ScriptDocumentRefusedError as refused:
        raise ToolCallError(str(refused)) from refused


def _made(
    session: Session, workspace_id: int, started: _Started, deadline: float
) -> str:
    """What the ready version holds, and the pages the agent can look at by the deadline."""
    rendered = RenderedArtifact(started.artifact_id, started.title, started.version)
    read = _read_ready(session, started, deadline)
    if read is None:
        return (
            f"{first_line(rendered)}\nIt is ready in Studio. Its text and page "
            "previews could not be read while Studio was busy: tell the user it is "
            "ready, and do not render it again."
        )
    artifact, text, data = read
    size = document_size(artifact.format, data, text)
    kind = f"{FORMATS_BY_KEY[artifact.format].label} document"
    return "\n".join(
        [
            first_line(rendered),
            f"A {kind} of {size}. Its text begins:",
            "",
            _opening(text),
            "",
            _previews(artifact, workspace_id, deadline),
        ]
    )


def _read_ready(
    session: Session, started: _Started, deadline: float
) -> tuple[Artifact, str, bytes] | None:
    """The ready version, its text and its file; None if the database stayed busy to the deadline.

    Studio may hold the write lock past SQLite's busy wait while it saves another
    document; the version is made, so the read is tried again, not failed.
    """
    while True:
        try:
            session.expire_all()
            artifact = session.get(Artifact, started.artifact_id)
            if artifact is None:
                session.commit()
                raise ToolCallError(
                    f"Artifact {started.artifact_id} was deleted once ready."
                )
            primary = next(
                f for f in artifact.files if f.role is ArtifactFileRole.PRIMARY
            )
            text = artifact.document.content or ""
            # A Word preview waits on Electron; no transaction may be open meanwhile.
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


def _opening(text: str) -> str:
    if len(text) <= TEXT_CHARS:
        return text
    return f"{text[:TEXT_CHARS]}… ({len(text) - TEXT_CHARS:,} more characters)"


def _previews(artifact: Artifact, workspace_id: int, deadline: float) -> str:
    """The preview pages as paths the agent's `read` opens, and why any are missing."""
    if not declares_image_input(get_storage_settings().agent_dir / CONFIG_FILE):
        return (
            "No page previews: the selected model cannot read images. Check the "
            "script and the text above instead."
        )
    try:
        previews = previews_for(artifact, time_left=deadline - time.monotonic())
    # The version is made; a preview that breaks must not send the model to make it again.
    except Exception:
        logger.exception("previews of artifact %s failed", artifact.id)
        return "No page previews: drawing them failed."
    if not previews.pages:
        return f"No page previews: {previews.reason or 'none were drawn.'}"
    folder = get_storage_settings().agent_working_dir(workspace_id)
    pages = [f"- {_relative(page, folder)}" for page in previews.pages]
    missing = [previews.reason] if previews.reason else []
    left_out = [WORD_PREVIEWS_LEAVE_OUT] if artifact.format == "docx" else []
    return "\n".join(
        ["Page previews to check with `read`:", *pages, *missing, *left_out]
    )


def _relative(page: Path, folder: Path) -> str:
    """As the agent names files: from its own folder, with forward slashes."""
    return page.relative_to(folder).as_posix()


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


RENDER_DOCUMENT = Tool(listing=LISTING, run=render, waits=True)
