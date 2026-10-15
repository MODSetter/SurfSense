"""Refuse a rewrite the selected model's window cannot hold: a Refine, or a Retry of one."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.dependencies import transact
from modules.agent.model_window import selected_model_window
from modules.artifacts.studio_documents.recipe import Refinement
from modules.artifacts.studio_documents.service import figure_captions
from modules.artifacts.studio_documents.window import (
    figure_list_chars,
    too_long_reason,
)
from modules.llm.resolution import ModelResolutionError


async def require_rewrite_fits(
    session: Session, artifact_id: int, rewrite: Refinement
) -> None:
    """Checked against the model selected now, which may not be the one that refined."""
    figures_chars = await transact(session, _figures_chars, artifact_id)
    try:
        # A local model's window is what llama-server loads it with, so it may load.
        model, window = await selected_model_window(session)
    except ModelResolutionError as error:
        # With its code, as a refused create sends it, so the interface translates it.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"message": "Needs a chat model", "code": "needs_chat"},
        ) from error
    reason = too_long_reason(
        rewrite.base.text, rewrite.instruction, model, window, figures_chars
    )
    if reason is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, reason)


def _figures_chars(session: Session, artifact_id: int) -> int:
    """How long the prompt's list of the figures the document may place is."""
    return figure_list_chars(figure_captions(session, artifact_id))
