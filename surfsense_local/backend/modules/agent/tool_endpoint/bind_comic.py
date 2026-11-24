"""Bind the pictures the agent drew into one comic, kept in Studio as a PDF."""

import time
from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy.orm import Session

from modules.agent.tool_endpoint.failed_renders import FailedRunError
from modules.agent.tool_endpoint.job_outcome import wait_for_outcome
from modules.agent.tool_endpoint.registration import TOOL_CALL_SECONDS
from modules.agent.tool_endpoint.rendered_label import (
    RenderedArtifact,
    first_line,
    queued_line,
)
from modules.agent.tool_endpoint.same_title_documents import refuse_same_title
from modules.agent.tool_endpoint.tool import Tool, ToolCallError
from modules.agent.tool_endpoint.turn_scope import TurnScope
from modules.artifacts.comic.bound_comic import (
    FORMAT,
    ComicRefusedError,
    create_bound_comic,
)
from modules.artifacts.comic.kinds import MAX_PAGES
from modules.artifacts.comic.reading import DIRECTIONS, LAYOUTS, Direction, Layout
from modules.artifacts.script_documents.version import version_of
from modules.artifacts.waiting_renders.waits import waiting_sentence, waits_for
from modules.documents.models import DocumentStatus

TOOL_NAME = "bind_comic"

# Binding reads files and writes one PDF: seconds, unless Studio is busy.
WAIT_SECONDS = 60
CALL_SECONDS = TOOL_CALL_SECONDS - 10
LINE_CHARS = 2_000

LISTING: dict[str, Any] = {
    "name": TOOL_NAME,
    "description": (
        "Bind pictures you drew with surfsense_make_image in this chat into one "
        "comic, kept in Studio as a PDF: a comic of any kind, a picture book or a "
        "storyboard. Follow the surfsense-pictures skill's comics.md for the kind's "
        "layout and direction. Give every page in reading order. A page still being "
        "drawn may be named: the comic waits for it. To change a page, change its "
        "picture, then call this again with the comic's artifact_id and every page."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "The comic's title."},
            "pages": {
                "type": "array",
                "maxItems": MAX_PAGES,
                "items": {
                    "type": "object",
                    "properties": {
                        "image": {
                            "type": "string",
                            "description": "The picture's name, image-<id>.",
                        },
                        "lines": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Text set under the picture exactly: for a page "
                                "drawn without words or misspelt, a picture book's "
                                "text, a storyboard shot's note. Left out, none."
                            ),
                        },
                    },
                    "required": ["image"],
                },
                "description": "Every page, in reading order.",
            },
            "layout": {
                "type": "string",
                "enum": list(LAYOUTS),
                "description": (
                    "pages, the default: one picture a page. scroll: stacked down "
                    "one long page, as a webtoon reads."
                ),
            },
            "direction": {
                "type": "string",
                "enum": list(DIRECTIONS),
                "description": "rtl for a manga; ltr, the default, otherwise.",
            },
            "artifact_id": {
                "type": "integer",
                "description": (
                    "To change a comic you bound in this chat: its artifact id. The "
                    "result is its next version. Leave out for a new comic."
                ),
            },
        },
        "required": ["title", "pages"],
    },
}


@dataclass(frozen=True)
class _Request:
    title: str
    pages: list[tuple[str, tuple[str, ...]]]
    layout: Layout
    direction: Direction
    base_artifact_id: int | None


def bind(session: Session, scope: TurnScope, arguments: dict[str, Any]) -> str:
    """Create the comic's version in one short transaction, then wait for its job."""
    began = time.monotonic()
    scope.require_known()
    request = _request(arguments)
    if request.base_artifact_id is None:
        refuse_same_title(session, scope.thread_id, request.title, FORMAT)
    try:
        artifact = create_bound_comic(
            session,
            scope.workspace_id,
            scope.thread_id,
            title=request.title,
            pages=request.pages,
            layout=request.layout,
            direction=request.direction,
            base_artifact_id=request.base_artifact_id,
        )
    except ComicRefusedError as refused:
        session.rollback()
        raise ToolCallError(str(refused)) from refused
    version = version_of(artifact.artifact_metadata)
    made = RenderedArtifact(
        artifact.id,
        " ".join(request.title.split()),
        version.number if version is not None else 1,
    )
    waiting = waits_for(artifact.artifact_metadata)
    session.commit()
    if waiting:
        return f"{queued_line(made)}\n{waiting_sentence(waiting)}"

    wait = min(WAIT_SECONDS, began + CALL_SECONDS - time.monotonic())
    outcome = wait_for_outcome(session, made.id, wait)
    if outcome is None:
        raise ToolCallError(f"Artifact {made.id} was deleted before it was ready.")
    if outcome.status is DocumentStatus.READY:
        count = len(request.pages)
        return (
            f"{first_line(made)}\n"
            f"A comic of {count} {'page' if count == 1 else 'pages'}, bound as one "
            "PDF in Studio. To change a page, change its picture with "
            f"surfsense_make_image, then call this tool again with artifact_id "
            f"{made.id} and every page."
        )
    if outcome.status is DocumentStatus.FAILED:
        raise FailedRunError(
            f'The comic "{made.title}" (artifact {made.id}) failed: '
            f"{outcome.error_message or 'no reason given'}\n\nTell the user what failed."
        )
    if outcome.status is DocumentStatus.CANCELLED:
        raise ToolCallError(
            f"Artifact {made.id} was cancelled in Studio. Ask the user before "
            "binding it again."
        )
    return (
        f"{queued_line(made)}\n"
        f"The comic is still being bound after {time.monotonic() - began:.0f} s, "
        "behind other Studio work. It appears in Studio when it is ready: tell the "
        "user so, and do not bind it again."
    )


def _request(arguments: dict[str, Any]) -> _Request:
    """The call's arguments, refused in a sentence naming the one to fix."""
    title = arguments.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ToolCallError("Give the comic a title.")
    pages = arguments.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ToolCallError("Give the pages: every picture's name, in reading order.")
    if len(pages) > MAX_PAGES:
        raise ToolCallError(f"Bind at most {MAX_PAGES} pages.")
    layout = arguments.get("layout") or "pages"
    if layout not in LAYOUTS:
        raise ToolCallError(f"layout must be one of: {', '.join(LAYOUTS)}.")
    direction = arguments.get("direction") or "ltr"
    if direction not in DIRECTIONS:
        raise ToolCallError(f"direction must be one of: {', '.join(DIRECTIONS)}.")
    base = arguments.get("artifact_id")
    if base is not None and (not isinstance(base, int) or isinstance(base, bool)):
        raise ToolCallError(
            "artifact_id must be the number of a comic you bound, or left out."
        )
    return _Request(
        title.strip(),
        [_page(page) for page in pages],
        cast(Layout, layout),
        cast(Direction, direction),
        base,
    )


def _page(page: object) -> tuple[str, tuple[str, ...]]:
    if not isinstance(page, dict) or not isinstance(page.get("image"), str):
        raise ToolCallError('Each page is {"image": "image-<id>"}, with lines if any.')
    lines = page.get("lines") or []
    if not isinstance(lines, list) or not all(isinstance(line, str) for line in lines):
        raise ToolCallError("A page's lines must be a list of strings.")
    kept = tuple(line.strip()[:LINE_CHARS] for line in lines if line.strip())
    return page["image"].strip(), kept


BIND_COMIC = Tool(listing=LISTING, run=bind, waits=True)
