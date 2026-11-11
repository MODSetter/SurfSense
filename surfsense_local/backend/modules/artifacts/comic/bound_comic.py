"""Create the agent's comic: a pending `comic` artifact that binds pictures drawn in its chat.

Commits before enqueueing: the worker is another process and must find the row.
"""

import logging

from sqlalchemy.orm import Session

from modules.artifacts.comic.binding_recipe import (
    ComicBinding,
    ComicPage,
    comic_bound,
)
from modules.artifacts.comic.kinds import MAX_PAGES
from modules.artifacts.comic.reading import Direction, Layout
from modules.artifacts.drawn_images.names import (
    ImageStillDrawingError,
    is_image_name,
    kept_picture,
)
from modules.artifacts.models import Artifact
from modules.artifacts.queued_job import queue_job
from modules.artifacts.script_documents.version import (
    ArtifactVersion,
    next_version_number,
    version_of,
)
from modules.artifacts.studio_documents.recipe import RECIPE_KEY
from modules.artifacts.waiting_renders.settle import settle_waiting_renders
from modules.artifacts.waiting_renders.waits import KEY as WAITS_FOR
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.embedding.active import EmbeddingNotChosenError, require_active_index

logger = logging.getLogger(__name__)

TITLE_CHARS = 200
FORMAT = "comic"


class ComicRefusedError(ValueError):
    """Why the comic cannot be bound, in a sentence the agent can act on."""


def create_bound_comic(
    session: Session,
    workspace_id: int,
    chat_thread_id: int,
    *,
    title: str,
    pages: list[tuple[str, tuple[str, ...]]],
    layout: Layout,
    direction: Direction,
    base_artifact_id: int | None,
) -> Artifact:
    """`pages` are picture names in reading order, each with the lines set under it."""
    title = title.strip()
    if not 1 <= len(title) <= TITLE_CHARS:
        raise ComicRefusedError(
            f"Give the comic a title of 1 to {TITLE_CHARS} characters."
        )
    if not 1 <= len(pages) <= MAX_PAGES:
        raise ComicRefusedError(
            f"Bind 1 to {MAX_PAGES} pages: at most {MAX_PAGES} pages."
        )
    try:
        require_active_index(session)
    except EmbeddingNotChosenError as error:
        raise ComicRefusedError(
            "Studio is not ready on this computer: no embedding model is chosen yet."
        ) from error

    waiting: list[int] = []
    for name, _ in pages:
        try:
            kept_picture(session, workspace_id, chat_thread_id, name)
        except ImageStillDrawingError:
            waiting.append(int(name.removeprefix("image-")))
        except LookupError as error:
            raise ComicRefusedError(
                f'This chat has no picture named "{name}" to bind: use a name '
                "surfsense_make_image gave in this chat."
            ) from error
    base = (
        None
        if base_artifact_id is None
        else _base_version(session, workspace_id, chat_thread_id, base_artifact_id)
    )

    document = Document(
        workspace_id=workspace_id,
        title=title,
        document_type=DocumentType.ARTIFACT,
        status=DocumentStatus.PENDING,
    )
    session.add(document)
    session.flush()
    artifact = Artifact(
        document_id=document.id,
        workspace_id=workspace_id,
        format=FORMAT,
        chat_thread_id=chat_thread_id,
    )
    session.add(artifact)
    session.flush()
    version = (
        ArtifactVersion(root=artifact.id, number=1, parent=None)
        if base is None
        else ArtifactVersion(
            root=base.root,
            number=next_version_number(session, workspace_id, base.root),
            parent=base_artifact_id,
        )
    )
    binding = ComicBinding(
        pages=tuple(ComicPage(picture_id(name), lines) for name, lines in pages),
        layout=layout,
        direction=direction,
    )
    artifact.artifact_metadata = {
        RECIPE_KEY: comic_bound(binding),
        "version": version.as_metadata(),
        "source_document_ids": [],
        "prompt": None,
        **({WAITS_FOR: list(dict.fromkeys(waiting))} if waiting else {}),
    }
    if waiting:
        session.commit()
        # A picture may have ended between the check and the commit.
        settle_waiting_renders(session, render_id=artifact.id)
    else:
        queue_job(session, artifact)
    logger.info(
        "studio: enqueued bound comic %s of %s pages, root=%s v%s",
        artifact.id,
        len(pages),
        version.root,
        version.number,
    )
    return artifact


def picture_id(name: str) -> int:
    """The artifact id in a picture's name; ComicRefusedError for any other name."""
    if not is_image_name(name):
        raise ComicRefusedError(
            f'"{name}" is not a picture\'s name: use a name surfsense_make_image gave.'
        )
    return int(name.removeprefix("image-"))


def _base_version(
    session: Session, workspace_id: int, chat_thread_id: int, base_id: int
) -> ArtifactVersion:
    base = session.get(Artifact, base_id)
    if (
        base is None
        or base.workspace_id != workspace_id
        or base.chat_thread_id != chat_thread_id
        or base.format != FORMAT
    ):
        raise ComicRefusedError(
            f"This chat bound no comic with artifact id {base_id}: name one "
            "surfsense_bind_comic gave in this chat."
        )
    version = version_of(base.artifact_metadata)
    if version is None:
        raise ComicRefusedError(
            f"Comic {base_id} was made in Studio and keeps no pages to bind again: "
            "bind a new comic without artifact_id."
        )
    return version
