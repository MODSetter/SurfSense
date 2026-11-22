"""Refuse an edit, or its Retry, only when no image model is chosen at all: a
model that takes pictures edits, and any other image model draws it again."""

from sqlalchemy.orm import Session

from modules.artifacts.drawn_images.model import require_image_model
from modules.llm.pictures_in import model as pictures_in


def require_image_edit_model(session: Session) -> None:
    if pictures_in.picture_source(session) is None:
        require_image_model(session)
