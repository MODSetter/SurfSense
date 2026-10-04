"""The routes Electron polls for Word snapshots and posts each printed PDF to."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from modules.agent.previews import docx_snapshots
from modules.agent.tool_endpoint.allowed_callers import refuse_web_pages

# Four pages of a document script's output are far below this; a body past it
# is not a snapshot.
PDF_BYTES = 50 * 1024 * 1024

router = APIRouter(
    prefix="/agent/previews/docx-snapshots",
    tags=["agent"],
    # Electron's main process sends no Origin; a page sharing loopback does.
    dependencies=[Depends(refuse_web_pages)],
)


class SnapshotRequestRead(BaseModel):
    id: str
    # Relative to the API: the artifact's Word file, as the in-app viewer loads it.
    file_url: str


class SnapshotFailure(BaseModel):
    reason: Annotated[str, Field(min_length=1, max_length=500)]


@router.get(
    "/next",
    response_model=SnapshotRequestRead,
    responses={204: {"description": "Nothing to print"}},
    summary="Take the oldest Word document waiting to be printed",
)
async def next_snapshot() -> SnapshotRequestRead | Response:
    request = docx_snapshots.snapshots.next_request()
    if request is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return SnapshotRequestRead(
        id=request.id, file_url=f"/artifacts/{request.artifact_id}/files/primary"
    )


@router.post(
    "/{request_id}/pdf",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Hand back the printed PDF",
)
async def deliver_snapshot(request_id: str, request: Request) -> None:
    pdf = await request.body()
    if len(pdf) > PDF_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "the PDF is too large")
    if not pdf.startswith(b"%PDF-"):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "the body is not a PDF"
        )
    if not docx_snapshots.snapshots.deliver(request_id, pdf):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no one waits for this snapshot")


@router.post(
    "/{request_id}/failure",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Say why the document could not be printed",
)
async def report_failure(
    request_id: str, failure: Annotated[SnapshotFailure, Body()]
) -> None:
    if not docx_snapshots.snapshots.fail(request_id, failure.reason):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no one waits for this snapshot")
