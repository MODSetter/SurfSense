"""
API route for fetching the available LLM models catalogue.

Serves a dynamically-updated list sourced from the OpenRouter public API,
with a local JSON fallback when the API is unreachable.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.db import User
from app.services.model_list_service import get_model_list
from app.users import current_active_user

router = APIRouter()
logger = logging.getLogger(__name__)


class ModelListItem(BaseModel):
    value: str
    label: str
    provider: str
    context_window: str | None = None


@router.get("/models", response_model=list[ModelListItem])
async def list_available_models(
    user: User = Depends(current_active_user),
):
    """
    Return all available LLM models grouped by provider.

    The list is sourced from the OpenRouter public API and cached for 1 hour.
    If the API is unreachable, a local fallback file is used instead.
    """
    try:
        return await get_model_list()
    except Exception as e:
        logger.exception("Failed to fetch model list")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch model list: {e!s}"
        ) from e
