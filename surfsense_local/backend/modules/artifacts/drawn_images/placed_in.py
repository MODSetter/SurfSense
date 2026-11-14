"""Refuse deleting a picture while a document of its chat places it.

A script names its pictures rather than copying them, so its Retry would have none.
"""

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.artifacts.drawn_images.names import image_name
from modules.artifacts.image_edits.editable import EDITABLE_FORMATS
from modules.artifacts.models import Artifact
from modules.artifacts.refused import refused
from modules.artifacts.script_documents.spec import DOCUMENT_FORMATS, document_script


def refuse_deleting_a_placed_picture(session: Session, picture: Artifact) -> None:
    if picture.format not in EDITABLE_FORMATS or picture.chat_thread_id is None:
        return
    name = image_name(picture.id)
    specs = session.scalars(
        select(Artifact.artifact_metadata).where(
            Artifact.chat_thread_id == picture.chat_thread_id,
            Artifact.format.in_(DOCUMENT_FORMATS),
        )
    )
    for metadata in specs:
        script = document_script(metadata)
        if script is not None and name in script.images:
            raise refused(
                status.HTTP_409_CONFLICT,
                "A document places this picture: delete that document first.",
                "placed_in_document",
            )
