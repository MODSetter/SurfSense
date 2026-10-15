from fastapi import APIRouter, status
from sqlalchemy.orm import Session

from api.dependencies import SessionDep, transact
from modules.artifacts.schemas import ArtifactRead, RefineRequest
from modules.artifacts.studio_documents.fits import require_rewrite_fits
from modules.artifacts.studio_documents.recipe import Refinement
from modules.artifacts.studio_documents.service import (
    create_refine_version,
    refinable_spec,
)

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
    spec = await transact(session, refinable_spec, artifact_id)
    await require_rewrite_fits(
        session, artifact_id, Refinement(payload.instruction, spec)
    )
    return await transact(session, _refine, artifact_id, payload.instruction)


def _refine(session: Session, artifact_id: int, instruction: str) -> ArtifactRead:
    return ArtifactRead.of(create_refine_version(session, artifact_id, instruction))
