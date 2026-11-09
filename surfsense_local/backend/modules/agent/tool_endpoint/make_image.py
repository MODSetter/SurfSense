"""Draw or edit a picture for the agent, kept in Studio under a name documents can place."""

import threading
import time
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.agent.previews.inline_images import inline_image
from modules.agent.tool_endpoint.failed_renders import (
    IMAGES,
    FailedRunError,
    note_queued,
    queued_runs,
    settle_queued,
    stop_after_three_failures,
)
from modules.agent.tool_endpoint.job_outcome import wait_for_outcome
from modules.agent.tool_endpoint.ready_version import read_ready
from modules.agent.tool_endpoint.refusal_sentence import refusal_sentence
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
from modules.artifacts.drawn_images.names import image_name
from modules.artifacts.drawn_images.service import create_drawn_image
from modules.artifacts.image_edits.editable import EDITABLE_FORMATS, has_picture
from modules.artifacts.image_edits.model import require_image_edit_model
from modules.artifacts.image_edits.service import create_image_edit_version
from modules.artifacts.models import Artifact, ArtifactFileRole
from modules.artifacts.script_documents.version import version_of
from modules.documents.models import Document, DocumentStatus
from modules.embedding.active import EmbeddingNotChosenError
from shared.config import get_storage_settings

TOOL_NAME = "make_image"

# Only for a runaway model: as in Studio, length is the prompt's to keep and a
# model's own refusal comes back as a failed picture. No real prompt comes near it.
PROMPT_CHARS = 32_000
# A remote picture answers well inside this; a local one on a processor takes
# minutes, past the tool call's hard limit, so the call answers without it.
WAIT_SECONDS = 150
CALL_SECONDS = TOOL_CALL_SECONDS - 10
_ENDED = (DocumentStatus.READY, DocumentStatus.FAILED, DocumentStatus.CANCELLED)

_starting = threading.Lock()

LISTING: dict[str, Any] = {
    "name": TOOL_NAME,
    "description": (
        "Draw a picture or an infographic with the user's image model, or edit one "
        "you made in this chat, and keep it in Studio. Only when the user asks for "
        "one: each is billed, or takes minutes on their computer, so confirm before "
        "making more than one. Read any sources first and write the whole prompt "
        "yourself. Draw no data chart: numbers belong in a real chart. Words that "
        "must be exact belong in the document around the picture, since image models "
        "garble lettering. Write one self-contained prompt, as short as it can be "
        "while still saying what to draw. Returns the picture's name, to place it in a document or "
        "a web page, and the picture itself to check."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": (
                    "What to draw, or how to change the picture. Goes to the image "
                    "model as written."
                ),
            },
            "title": {
                "type": "string",
                "description": (
                    "The picture's title, as Studio lists it. Needed for a new picture."
                ),
            },
            "style": {
                "type": "string",
                "enum": sorted(EDITABLE_FORMATS),
                "description": (
                    "infographic to give the prompt's facts Studio's sketchnote "
                    "style; image, the default, to draw the prompt alone."
                ),
            },
            "artifact_id": {
                "type": "integer",
                "description": (
                    "To change a picture you made in this chat: its artifact id. "
                    "The result is its next version. Leave out for a new picture."
                ),
            },
        },
        "required": ["prompt"],
    },
}


@dataclass(frozen=True)
class _Request:
    prompt: str
    title: str | None
    style: str
    base_artifact_id: int | None


def make(
    session: Session, scope: TurnScope, arguments: dict[str, Any]
) -> str | ToolResult:
    """Create the picture's version in one short transaction, wait for its job, and show it."""
    began = time.monotonic()
    deadline = began + CALL_SECONDS
    scope.require_known()
    request = _request(arguments)
    # opencode runs a step's calls together: each must see the row the last one made,
    # or two with one title would bill two pictures.
    with _starting:
        if request.base_artifact_id is None:
            assert request.title is not None  # _request asked for it
            refuse_same_title(session, scope.thread_id, request.title, request.style)
        made = _start(session, scope, request)

    outcome = wait_for_outcome(
        session, made.id, min(WAIT_SECONDS, deadline - time.monotonic())
    )
    if outcome is None:
        raise ToolCallError(f"Artifact {made.id} was deleted before it was ready.")
    if outcome.status is DocumentStatus.READY:
        return _shown(session, scope, made, deadline)
    if outcome.status is DocumentStatus.FAILED:
        raise FailedRunError(
            f'The picture "{made.title}" (artifact {made.id}) failed: '
            f"{outcome.error_message or 'no reason given'}\n\n"
            "Tell the user what failed. Try once more only if the reason says it "
            "may help: each try may be billed."
        )
    if outcome.status is DocumentStatus.CANCELLED:
        raise ToolCallError(
            f"Artifact {made.id} was cancelled in Studio. Ask the user before making "
            "it again."
        )
    note_queued(IMAGES, scope.thread_id, made.id)
    name = image_name(made.id)
    return (
        f"{queued_line(made)}\n"
        f"The picture is still being made after {time.monotonic() - began:.0f} s. Do "
        "not make it again: it appears in Studio when it is ready. Its name is "
        f"{name}, and a document or page can place it once it is ready: if one says "
        "it is still being drawn, tell the user so and stop."
    )


def _request(arguments: dict[str, Any]) -> _Request:
    """The call's arguments, refused in a sentence naming the one to fix."""
    prompt, title = arguments.get("prompt"), arguments.get("title")
    # Null is how many models leave an optional field out.
    style = arguments.get("style") or "image"
    base = arguments.get("artifact_id")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ToolCallError("Give the prompt: what to draw, or how to change it.")
    if len(prompt.strip()) > PROMPT_CHARS:
        raise ToolCallError(
            f"The prompt is {len(prompt.strip()):,} characters; the limit is "
            f"{PROMPT_CHARS:,}. Shorten it and call this tool again."
        )
    if style not in EDITABLE_FORMATS:
        raise ToolCallError(
            f"style must be one of: {', '.join(sorted(EDITABLE_FORMATS))}."
        )
    if base is not None and (not isinstance(base, int) or isinstance(base, bool)):
        raise ToolCallError(
            "artifact_id must be the number of a picture you made, or left out."
        )
    if base is None and (not isinstance(title, str) or not title.strip()):
        raise ToolCallError("Give the picture a title.")
    return _Request(
        prompt.strip(), title.strip() if isinstance(title, str) else None, style, base
    )


def _start(session: Session, scope: TurnScope, request: _Request) -> RenderedArtifact:
    """The pending version and its queued job, committed so the worker finds them."""
    try:
        artifact = (
            _new_picture(session, scope, request)
            if request.base_artifact_id is None
            else _edited_picture(
                session, scope, request.base_artifact_id, request.prompt
            )
        )
    except EmbeddingNotChosenError as error:
        session.rollback()
        raise ToolCallError(
            "Studio is not ready on this computer: no embedding model is chosen yet."
        ) from error
    except HTTPException as refused:
        session.rollback()
        raise ToolCallError(
            f"Studio could not make the picture: {refusal_sentence(refused.detail)}"
        ) from refused
    except ToolCallError:
        session.rollback()
        raise
    version = version_of(artifact.artifact_metadata)
    return RenderedArtifact(
        artifact.id,
        " ".join(artifact.document.title.split()),
        version.number if version is not None else 1,
    )


def _new_picture(session: Session, scope: TurnScope, request: _Request) -> Artifact:
    assert request.title is not None  # _request asked for it
    return create_drawn_image(
        session,
        scope.workspace_id,
        title=request.title,
        prompt=request.prompt,
        format=request.style,
        chat_thread_id=scope.thread_id,
    )


def _edited_picture(
    session: Session, scope: TurnScope, base_id: int, instruction: str
) -> Artifact:
    """Only a picture of this chat: the edit service checks no workspace or thread."""
    base = session.get(Artifact, base_id)
    if (
        base is None
        or base.workspace_id != scope.workspace_id
        or base.chat_thread_id != scope.thread_id
    ):
        raise ToolCallError(
            f"This chat made no picture with artifact id {base_id}: name one "
            f"{TOOL_NAME} gave in this chat."
        )
    require_image_edit_model(session)
    return create_image_edit_version(session, base_id, instruction)


def _shown(
    session: Session, scope: TurnScope, made: RenderedArtifact, deadline: float
) -> str | ToolResult:
    read = read_ready(session, made.id, deadline)
    if read is None:
        return (
            f"{first_line(made)}\nIt is ready in Studio. It could not be read while "
            "Studio was busy: tell the user it is ready, and do not make it again."
        )
    artifact, _, _ = read
    placeable = has_picture(artifact)
    primary = next(f for f in artifact.files if f.role is ArtifactFileRole.PRIMARY)
    storage_key = primary.storage_key
    editable = _edit_model_chosen(session)
    session.commit()
    lines = [
        first_line(made),
        _how_to_use(made.id, editable) if placeable else _NOT_PLACEABLE,
    ]
    images: tuple[InlineImage, ...] = ()
    if placeable:
        if scope.reads_images():
            images = _picture(storage_key, editable, lines)
        else:
            lines.append(_UNSEEN)
    text = "\n".join(lines)
    return ToolResult(text, images) if images else text


_NOT_PLACEABLE = (
    "The image model gave a format documents cannot place. It is in Studio for the "
    "user to open: tell them so."
)
# A redraw would bill another picture the user did not ask for.
_NO_EDIT_MODEL = (
    "No image editing model is chosen, so you cannot alter this picture: do not draw "
    "it again unless the user asks. If it is wrong, tell the user what is wrong, and "
    "that they can choose a model in Settings > Image edit."
)
_UNSEEN = (
    "You cannot see it: the selected model cannot read images. Do not describe it "
    "beyond what you asked for."
)


def _edit_model_chosen(session: Session) -> bool:
    """Whether an edit could run: one offered without a model could only be refused."""
    try:
        require_image_edit_model(session)
    except HTTPException:
        return False
    return True


def _how_to_use(artifact_id: int, editable: bool) -> str:
    name = image_name(artifact_id)
    place = (
        f"Its name is {name}. To place it, pass {name} in a render's images, or in "
        f'a web page write src="surfsense-image:{name}".'
    )
    if editable:
        return f"{place} To change it, call this tool again with artifact_id {artifact_id}."
    return f"{place} {_NO_EDIT_MODEL}"


def _picture(
    storage_key: str, editable: bool, lines: list[str]
) -> tuple[InlineImage, ...]:
    path = get_storage_settings().data_dir / storage_key
    try:
        shown = inline_image(path)
    except (OSError, ValueError, Image.DecompressionBombError):
        lines.append("It could not be shown to you, though it is in Studio.")
        return ()
    lines.append(
        "Look at it before you answer: image models get lettering, hands and counts "
        "wrong. "
        + (
            "If it is wrong, change it or tell the user."
            if editable
            else "If it is wrong, tell the user, as above."
        )
    )
    return (shown,)


_stopped_after_three = stop_after_three_failures(make, IMAGES)


def _make_counting_late_failures(
    session: Session, scope: TurnScope, arguments: dict[str, Any]
) -> str | ToolResult:
    """A picture that failed after its call answered counts before the next starts."""
    _settle_queued_pictures(session, scope.thread_id)
    return _stopped_after_three(session, scope, arguments)


def _settle_queued_pictures(session: Session, thread_id: int) -> None:
    queued = queued_runs(IMAGES, thread_id)
    if not queued:
        return
    statuses = dict(
        session.execute(
            select(Artifact.id, Document.status)
            .join(Document, Artifact.document_id == Document.id)
            .where(Artifact.id.in_(queued))
        )
        .tuples()
        .all()
    )
    session.commit()
    for artifact_id in queued:
        status = statuses.get(artifact_id)
        # A deleted one has ended too, and no one saw it fail.
        if status is None or status in _ENDED:
            settle_queued(
                IMAGES, thread_id, artifact_id, status is DocumentStatus.FAILED
            )


MAKE_IMAGE = Tool(listing=LISTING, run=_make_counting_late_failures, waits=True)
