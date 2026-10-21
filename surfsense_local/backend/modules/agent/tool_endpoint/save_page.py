"""The page tool: keep a web page the agent wrote under outputs/ as a version in Studio (ADR 0066).

The agent writes the HTML with its own tools; this reads the file, adds the kit
it asks for and the no-network policy, and waits for the index so the page is
ready when the model looks at its screenshots.
"""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from modules.agent.thread_folder.layout import OUTPUTS
from modules.agent.tool_endpoint.failed_renders import (
    RENDERS,
    FailedRunError,
    stop_after_three_failures,
)
from modules.agent.tool_endpoint.job_outcome import wait_for_outcome
from modules.agent.tool_endpoint.page_kit import with_kits
from modules.agent.tool_endpoint.ready_version import read_ready
from modules.agent.tool_endpoint.registration import TOOL_CALL_SECONDS
from modules.agent.tool_endpoint.rendered_label import (
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
from modules.artifacts.script_documents.version import version_of
from modules.artifacts.web_pages.no_network import without_network
from modules.artifacts.web_pages.outside_resources import outside_resources
from modules.artifacts.web_pages.page_checks import (
    PageCheckError,
    checked_page,
    too_large,
)
from modules.artifacts.web_pages.saved_page import PageRefusedError, save_page_version
from modules.documents.models import DocumentStatus

# Room for a page's inline SVG, script and a few data-URL images; a page past it
# is better split or drawn as SVG than shipped as pictures.
PAGE_BYTES = 5 * 1024 * 1024
# Indexing a page takes seconds; the rest of the call is for its screenshots.
WAIT_SECONDS = 60
CALL_SECONDS = TOOL_CALL_SECONDS - 10
TEXT_CHARS = 1500
LOOK_AT_EVERY_SCREEN = (
    "Look at every one before you answer: text that overflows or overlaps, a "
    "chart that did not draw, colours that do not read. If one is wrong, edit the "
    "file, save it again and look at the new screenshots too."
)
NO_SCREENSHOTS_TEXT_ONLY = (
    "No screenshots: the selected model cannot read images. Check the page's "
    "HTML and the text above instead."
)

TOOL_NAME = "save_page"

LISTING: dict[str, Any] = {
    "name": TOOL_NAME,
    "description": (
        "Keep a web page you wrote as an HTML file under outputs/ in Studio, as a "
        "new version. Load the surfsense-html skill first. Waits until the page is "
        "ready, then returns the artifact's id and version, its opening text, any "
        "outside resources the viewer will block, and up to four screenshots to "
        "check."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": (
                    "The page's file, from your folder: outputs/<name>.html. It "
                    "stays where it is, for the next edit."
                ),
            },
            "title": {
                "type": "string",
                "description": "The page's title, as Studio lists it.",
            },
            "artifact_id": {
                "type": "integer",
                "description": (
                    "To change a page you saved: its artifact id. The result is "
                    "its next version. Leave out for a new page."
                ),
            },
        },
        "required": ["path", "title"],
    },
}


@dataclass(frozen=True)
class _Request:
    path: str
    title: str
    base_artifact_id: int | None


def save(
    session: Session, scope: TurnScope, arguments: dict[str, Any]
) -> str | ToolResult:
    """Check and store the page in one short transaction, wait for its index, and show it."""
    deadline = time.monotonic() + CALL_SECONDS
    request = _request(arguments)
    file = _working_file(scope.folder, request.path)
    page = _page(file)
    notes = _blocked(page)
    if request.base_artifact_id is None and scope.known:
        refuse_same_title(session, scope.thread_id, request.title, "html")
    try:
        artifact = save_page_version(
            session,
            scope.workspace_id,
            title=request.title,
            page=without_network(page).encode("utf-8"),
            working_path=file.relative_to(scope.folder.resolve()).as_posix(),
            base_artifact_id=request.base_artifact_id,
            chat_thread_id=scope.thread_id if scope.known else None,
        )
    except PageRefusedError as refused:
        session.rollback()
        raise ToolCallError(str(refused)) from refused
    version = version_of(artifact.artifact_metadata)
    assert version is not None  # the service gave it one
    saved = RenderedArtifact(
        artifact.id, " ".join(request.title.split()), version.number
    )
    working = file.relative_to(scope.folder.resolve()).as_posix()

    outcome = wait_for_outcome(
        session, artifact.id, min(WAIT_SECONDS, deadline - time.monotonic())
    )
    if outcome is None:
        raise ToolCallError(f"Artifact {artifact.id} was deleted before it was ready.")
    if outcome.status is DocumentStatus.FAILED:
        raise FailedRunError(
            f'Version {saved.version} of "{saved.title}" (artifact {saved.id}) '
            f"failed: {outcome.error_message or 'no reason given'}\n\n"
            f"Save it again with artifact_id {saved.id}; if it fails the same way, "
            "tell the user what failed."
        )
    if outcome.status is DocumentStatus.CANCELLED:
        raise ToolCallError(
            f"Artifact {saved.id} was cancelled in Studio. Ask the user before "
            "saving it again."
        )
    if outcome.status is not DocumentStatus.READY:
        return (
            f"{queued_line(saved)}\nIt is still being indexed, behind other Studio "
            "work, and appears in Studio when ready: tell the user so, and do not "
            "save it again."
        )
    return _shown(session, scope, saved, working, notes, deadline)


def _request(arguments: dict[str, Any]) -> _Request:
    path, title = arguments.get("path"), arguments.get("title")
    base = arguments.get("artifact_id")
    if not isinstance(path, str) or not path.strip():
        raise ToolCallError("Give the page's path, such as outputs/report.html.")
    if not isinstance(title, str):
        raise ToolCallError("Give the page a title.")
    if base is not None and (not isinstance(base, int) or isinstance(base, bool)):
        raise ToolCallError(
            "artifact_id must be the number of a page you saved, or left out."
        )
    return _Request(path.strip(), title, base)


def _working_file(folder: Path, path: str) -> Path:
    """The file under the thread's outputs/, links followed, so none points out of it."""
    outputs = (folder / OUTPUTS).resolve()
    file = (folder / path).resolve()
    if not file.is_relative_to(outputs):
        raise ToolCallError(
            f"Save only a page under {OUTPUTS}/ in your folder, such as "
            f"{OUTPUTS}/report.html."
        )
    if file.suffix.lower() not in (".html", ".htm"):
        raise ToolCallError("The page's file must end in .html.")
    if not file.is_file():
        raise ToolCallError(f"There is no file at {path}: write the page there first.")
    return file


def _page(file: Path) -> str:
    """The page as it will be stored, its kit written in; refused when it is no page."""
    try:
        size = file.stat().st_size
        if size > PAGE_BYTES:  # refused before it is read
            raise too_large(size, PAGE_BYTES)
        written = checked_page(file.read_bytes(), PAGE_BYTES)
        page = with_kits(written)
        checked_page(page.encode("utf-8"), PAGE_BYTES)
    except PageCheckError as refused:
        raise ToolCallError(str(refused)) from refused
    return page


def _blocked(page: str) -> list[str]:
    found = outside_resources(page)
    if not found:
        return []
    listed = "\n".join(f"- {url}" for url in found[:20])
    more = f"\n- and {len(found) - 20} more" if len(found) > 20 else ""
    return [
        "The viewer gives a page no network, so these will not load; inline them "
        f"as data: URLs or SVG, or use system fonts:\n{listed}{more}"
    ]


def _shown(
    session: Session,
    scope: TurnScope,
    saved: RenderedArtifact,
    working: str,
    notes: list[str],
    deadline: float,
) -> str | ToolResult:
    read = read_ready(session, saved.id, deadline)
    if read is None:
        return (
            f"{first_line(saved)}\nIt is ready in Studio. Its text and screenshots "
            "could not be read while Studio was busy: tell the user it is ready, and "
            "do not save it again."
        )
    artifact, text, data = read
    images: tuple[InlineImage, ...] = ()
    if scope.reads_images():
        check, images = version_pages(
            artifact, saved.version, scope.folder, deadline, look=LOOK_AT_EVERY_SCREEN
        )
    else:
        check = NO_SCREENSHOTS_TEXT_ONLY
    lines = [
        first_line(saved),
        f"A web page of {max(1, round(len(data) / 1024))} KB. Its text begins:",
        "",
        _opening(text),
        "",
        *notes,
        check,
        f"Its working file is {working}: to change the page, edit that file and save "
        f"it again with artifact_id {saved.id}.",
    ]
    made = "\n".join(lines)
    return ToolResult(made, images) if images else made


def _opening(text: str) -> str:
    if len(text) <= TEXT_CHARS:
        return text
    return f"{text[:TEXT_CHARS]}… ({len(text) - TEXT_CHARS:,} more characters)"


SAVE_PAGE = Tool(
    listing=LISTING, run=stop_after_three_failures(save, RENDERS), waits=True
)
