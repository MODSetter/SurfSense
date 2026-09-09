import shutil
from collections.abc import Sequence

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from api.dependencies import SessionDep
from modules.artifacts.dependencies import ArtifactDep
from modules.artifacts.models import Artifact, ArtifactFileRole
from modules.artifacts.schemas import (
    ArtifactDetail,
    ArtifactRead,
    FormatRead,
    StudioJobCreate,
)
from modules.artifacts.service import create_artifact_job, list_formats
from modules.documents.models import Document, DocumentType
from modules.workspaces.dependencies import WorkspaceDep
from shared.config import get_storage_settings

router = APIRouter(tags=["studio"])

# Served inline so the viewer can render or stream; markup is forced to download
# so a generated page never runs its script on the API origin.
_INLINE_UNSAFE = {"text/html", "image/svg+xml"}


@router.get(
    "/workspaces/{workspace_id}/studio/formats",
    response_model=list[FormatRead],
    summary="List the Studio formats and whether each is usable",
)
def studio_formats(workspace: WorkspaceDep, session: SessionDep) -> list[FormatRead]:
    return list_formats(session)


@router.post(
    "/workspaces/{workspace_id}/studio/jobs",
    response_model=ArtifactRead,
    status_code=status.HTTP_201_CREATED,
    summary="Generate an artifact from documents",
)
def create_studio_job(
    workspace: WorkspaceDep, payload: StudioJobCreate, session: SessionDep
) -> ArtifactRead:
    artifact = create_artifact_job(session, workspace, payload)
    return ArtifactRead.of(artifact)


@router.get(
    "/workspaces/{workspace_id}/artifacts",
    response_model=list[ArtifactRead],
    summary="List a workspace's artifacts",
)
def list_artifacts(
    workspace: WorkspaceDep, session: SessionDep
) -> Sequence[ArtifactRead]:
    artifacts = session.scalars(
        select(Artifact)
        .join(Document, Document.id == Artifact.document_id)
        .where(
            Artifact.workspace_id == workspace.id,
            Document.document_type == DocumentType.ARTIFACT,
        )
        .order_by(Artifact.created_at.desc())
    ).all()
    return [ArtifactRead.of(artifact) for artifact in artifacts]


@router.get(
    "/artifacts/{artifact_id}",
    response_model=ArtifactDetail,
    summary="Read an artifact, its body and its files",
)
def read_artifact(artifact: ArtifactDep) -> ArtifactDetail:
    return ArtifactDetail.of(artifact)


@router.get(
    "/artifacts/{artifact_id}/files/{role}",
    response_class=FileResponse,
    summary="Download or stream an artifact's file",
)
def read_artifact_file(artifact: ArtifactDep, role: ArtifactFileRole) -> FileResponse:
    file = next((f for f in artifact.files if f.role is role), None)
    if file is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such file for this artifact")

    path = get_storage_settings().data_dir / file.storage_key
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "the file is no longer on disk")

    inline = file.mime_type not in _INLINE_UNSAFE
    return FileResponse(
        path,
        filename=file.original_filename,
        media_type=file.mime_type,
        content_disposition_type="inline" if inline else "attachment",
    )


@router.delete(
    "/artifacts/{artifact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an artifact",
)
def delete_artifact(artifact: ArtifactDep, session: SessionDep) -> Response:
    # The ARTIFACT document is the root: deleting it cascades the sidecar, its
    # files and its chunks. Only the blobs live beyond the database.
    directory = get_storage_settings().artifact_dir(artifact.workspace_id, artifact.id)
    document = artifact.document

    session.delete(document)
    session.commit()

    shutil.rmtree(directory, ignore_errors=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
