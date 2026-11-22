"""Refuse a drawing, or its Retry, that no chosen model can make."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from modules.llm.resolution import ModelResolutionError, resolve_image_generation


def require_image_model(session: Session) -> None:
    """Nothing fills the `image_gen` slot, or what fills it is gone."""
    try:
        resolve_image_generation(session)
    except ModelResolutionError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"message": "Needs an image model", "code": "needs_image"},
        ) from error
