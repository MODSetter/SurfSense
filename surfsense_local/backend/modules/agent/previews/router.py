"""The routes Electron polls for Word and PowerPoint snapshots and posts each printed PDF to."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from modules.agent.previews import docx_snapshots
from modules.agent.previews.docx_snapshots import SnapshotFormat, SnapshotRequest
from modules.agent.previews.snapshot_key import require_snapshot_key
from modules.agent.tool_endpoint.allowed_callers import refuse_web_pages

# Four pages of a document script's output are far below this; a body past it
# is not a snapshot.
PDF_BYTES = 50 * 1024 * 1024

PREFIX = "/agent/previews/docx-snapshots"
# A source is printed only from its own .docx or .pptx original.
_MIME: dict[str, str] = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}

router = APIRouter(
    prefix=PREFIX,
    tags=["agent"],
    # A page sharing loopback sends an Origin; another local process sends
    # none, and only Electron holds the key.
    dependencies=[Depends(refuse_web_pages), Depends(require_snapshot_key)],
)
# The print window fetches the file itself, as it fetches an artifact's: with
# an Origin and no key. The request id, which only the key's holder is handed,
# is what lets it in, and only while that request is being printed.
file_router = APIRouter(prefix=PREFIX, tags=["agent"])


class SnapshotRequestRead(BaseModel):
    id: str
    # Relative to the API: the artifact's file as the in-app viewer loads it,
    # or a source's original under this request's own file route.
    file_url: str
    # How to lay the file out: docx-preview for docx, pptx-renderer for pptx.
    format: SnapshotFormat
    # printToPDF's pageRanges, such as "1-4" or "2,5"; the PDF holds them in order.
    pages: str


class SnapshotFailure(BaseModel):
    reason: Annotated[str, Field(min_length=1, max_length=500)]


@router.get(
    "/next",
    response_model=SnapshotRequestRead,
    responses={204: {"description": "Nothing to print"}},
    summary="Take the oldest Word document or deck waiting to be printed",
)
async def next_snapshot() -> SnapshotRequestRead | Response:
    request = docx_snapshots.snapshots.next_request()
    if request is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return SnapshotRequestRead(
        id=request.id,
        file_url=_file_url(request),
        format=request.format,
        pages=request.pages,
    )


def _file_url(request: SnapshotRequest) -> str:
    if request.artifact_id is not None:
        return f"/artifacts/{request.artifact_id}/files/primary"
    return f"{PREFIX}/{request.id}/file"


@file_router.get(
    "/{request_id}/file",
    response_class=FileResponse,
    summary="The source file a snapshot request prints",
)
def read_snapshot_file(request_id: str) -> FileResponse:
    path = docx_snapshots.snapshots.source_file(request_id)
    if path is None or not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no file is being printed here")
    return FileResponse(path, media_type=_MIME[path.suffix.lower().lstrip(".")])


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
