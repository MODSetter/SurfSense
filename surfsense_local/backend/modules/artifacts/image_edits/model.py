"""Refuse an edit, or its Retry, that no chosen model can make."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from modules.llm.resolution import ModelResolutionError, resolve_image_edit


def require_image_edit_model(session: Session) -> None:
    """Nothing fills the `image_edit` slot, or what fills it is gone; mirrors Refine's `needs_chat`."""
    try:
        resolve_image_edit(session)
    except ModelResolutionError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"message": "Needs an image editing model", "code": "needs_image_edit"},
        ) from error
