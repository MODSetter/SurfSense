from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from api.dependencies import SessionDep, transact
from modules.agent.model_window import selected_model_window
from modules.artifacts.schemas import ArtifactRead, RefineRequest
from modules.artifacts.script_documents.spec import DocumentSpec
from modules.artifacts.studio_documents.service import (
    create_refine_version,
    figure_captions,
    refinable_spec,
)
from modules.artifacts.studio_documents.window import (
    figure_list_chars,
    too_long_reason,
)
from modules.llm.resolution import ModelResolutionError

router = APIRouter(tags=["studio"])


@router.post(
    "/artifacts/{artifact_id}/refine",
    response_model=ArtifactRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Rewrite a Word document's or PDF's spec into its next version",
)
async def refine_artifact(
    artifact_id: int, payload: RefineRequest, session: SessionDep
) -> ArtifactRead:
    spec, figures_chars = await transact(session, _what_refine_reads, artifact_id)
    try:
        # A local model's window is what llama-server loads it with, so it may load.
        model, window = await selected_model_window(session)
    except ModelResolutionError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, "Needs a chat model") from error
    reason = too_long_reason(
        spec.text, payload.instruction, model, window, figures_chars
    )
    if reason is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, reason)
    return await transact(session, _refine, artifact_id, payload.instruction)


def _what_refine_reads(session: Session, artifact_id: int) -> tuple[DocumentSpec, int]:
    """The spec to rewrite and how long the prompt's list of figures will be."""
    spec = refinable_spec(session, artifact_id)
    return spec, figure_list_chars(figure_captions(session, artifact_id))


def _refine(session: Session, artifact_id: int, instruction: str) -> ArtifactRead:
    return ArtifactRead.of(create_refine_version(session, artifact_id, instruction))
