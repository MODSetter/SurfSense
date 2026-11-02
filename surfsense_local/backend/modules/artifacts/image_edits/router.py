from fastapi import APIRouter, status

from api.dependencies import SessionDep
from modules.artifacts.image_edits.model import require_image_edit_model
from modules.artifacts.image_edits.service import (
    create_image_edit_version,
    editable_base,
)
from modules.artifacts.schemas import ArtifactRead, RefineRequest

router = APIRouter(tags=["studio"])


@router.post(
    "/artifacts/{artifact_id}/image-edit",
    response_model=ArtifactRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Edit an image's or infographic's picture into its next version",
)
def edit_image(
    artifact_id: int, payload: RefineRequest, session: SessionDep
) -> ArtifactRead:
    # The version first, so a summary is not refused for want of a model.
    editable_base(session, artifact_id)
    require_image_edit_model(session)
    return ArtifactRead.of(
        create_image_edit_version(session, artifact_id, payload.instruction)
    )
